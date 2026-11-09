#!/usr/bin/env python3
"""校验 data/resources.json 与 collections/ 中所有链接的可达性。

只用标准库，无第三方依赖。三态输出：
  ok            HTTP 2xx
  blocked       站点反爬（403/429）
  dead          域名不存在或站点已关闭（DNS NXDOMAIN、重定向至关闭公告）
  unreachable   DNS 正常但本机连不上（常见于境外站点直连被拦）

用法：
  python scripts/check_links.py              # 只报告，不回写
  python scripts/check_links.py --write      # 回写 verified / checked_at / final_url
  python scripts/check_links.py --only websites
  python scripts/check_links.py --only tutoring       # 线上口语一对一平台的入口可达性
  python scripts/check_links.py --only quark_tree     # 全量翻完夸克分享目录
  python scripts/check_links.py --only quark_shallow  # 只读 2 层（大批量分享用）
  python scripts/check_links.py --only sheet_index    # 统计腾讯文档索引里内嵌的夸克链接
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures as futures
import datetime as dt
import json
import pathlib
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RESOURCES_PATH = REPO_ROOT / "data" / "resources.json"
COLLECTIONS_DIR = REPO_ROOT / "collections"

REQUEST_TIMEOUT_SECONDS = 20
MAX_WORKERS = 12
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HTTP_BLOCKED_STATUS_CODES = frozenset({401, 403, 405, 429, 999})
URL_PATTERN = re.compile(r"https?://[^\s<>\"'`()\[\]「」，。、；：！？]+")
# 站点 200 但已重定向至「关停公告」这类路径时，按 dead 处理
CLOSURE_REDIRECT_HINTS = ("-to-close", "wonderopolis-to-close", "site-closed")
# 人工判定的状态，脚本不覆盖（链接可达但页面内容与描述不符）
MANUAL_STATUSES = frozenset({"mismatch"})
# 单条链接上的人工结论标记。夸克分享被平台下架时，分享页本身仍返回 HTTP 200，
# 只有公开接口的 41010 能看出来，这种结论靠脚本重探会把 dead 冲成 ok，
# 因此用 status_manual 让该条跳过自动回写，并保留 note 里的实测说明。
MANUAL_STATUS_FLAG = "status_manual"

# ── 夸克分享目录探测 ──────────────────────────────────────────────
# 这两个接口无需登录即可调用；下载与转存才需要登录态。
QUARK_SHARE_PATTERN = re.compile(r"pan\.quark\.cn/s/([a-zA-Z0-9]+)")
QUARK_API_BASE = "https://drive-h.quark.cn"
QUARK_TOKEN_PATH = "/1/clouddrive/share/sharepage/token"
QUARK_DETAIL_PATH = "/1/clouddrive/share/sharepage/detail"
# 服务端硬限：传 1000 也只返回 100，必须翻页
QUARK_PAGE_SIZE = 100
# 单个分享最多翻多少页，防止异常数据导致无限循环
QUARK_MAX_PAGES = 200
# 单个分享最多发多少次请求。大分享（如初中全科）实测要 1534 次、约 11 分钟，
# 400 次会截断成 6899（真实 21943），所以默认放到 2000 并允许按分享覆盖。
QUARK_REQUEST_BUDGET = 2000
# 单次运行的总时间预算（秒）。超过就停，避免整轮探针跑上一小时。
QUARK_TOTAL_TIME_BUDGET_SECONDS = 1800
# 目录树最大递归深度
QUARK_MAX_DEPTH = 8
# 单页请求失败时的重试次数（网络抖动很常见，一次失败就放弃会漏数）
QUARK_PAGE_RETRIES = 3
# 夸克返回「需要提取码」的业务码
QUARK_PASSCODE_REQUIRED_CODE = 41008
# 分享被平台下架（内容违规）的业务码，接口直接返回 HTTP 404
QUARK_CONTENT_BLOCKED_CODE = 41010

# ── 夸克分享浅层探测 ──────────────────────────────────────────────
# 大批量教辅分享（每包几十个教辅目录、每个目录下再按年级分册）不适合全量：
# 44 个分享全量按 quark_misc 的量级（21943 文件 / 1534 请求 / 11 分钟）要跑数小时。
# 浅层口径固定翻到第 2 层，给出「第 2 层有几个目录、几个文件」这个结构量。
QUARK_SHALLOW_DEPTH = 2
# 回写进数据的目录名上限，防止几十个包把 JSON 撑爆
QUARK_SHALLOW_MAX_DIR_NAMES = 80
# 单个分享浅层探测的请求上限，超了就标 truncated
QUARK_SHALLOW_REQUEST_BUDGET = 200
# 第 3 层只做抽样：看几个子目录的目录名就够判断「内容还在更下面」，
# 全扫会把请求花在结构展示上，也让 truncated 失去意义
QUARK_SHALLOW_L3_SAMPLE_DIRS = 8

# ── 腾讯文档总索引探测 ────────────────────────────────────────────
SHEET_DOC_PATTERN = re.compile(r"docs\.qq\.com/sheet/([A-Za-z0-9]+)")
# 索引页把表格数据塞在 flyweight.texts 的 percent-encoded JSON 里，靠这个前缀定位
SHEET_FLYWEIGHT_MARKER = "%22flyweight%22"


def hostname_resolves(target_url: str) -> bool:
    """判断主机名是否能解析。用于区分「域名已不存在」与「网络连不上」。"""
    hostname = urllib.parse.urlparse(target_url).hostname
    if not hostname:
        return False
    try:
        socket.getaddrinfo(hostname, None)
        return True
    except socket.gaierror:
        return False


def probe_single_url(target_url: str) -> dict:
    """探测单个 URL，返回 {status, http_code, final_url, error}。"""
    request = urllib.request.Request(target_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            final_url = response.geturl()
            if any(hint in final_url for hint in CLOSURE_REDIRECT_HINTS):
                return {
                    "status": "dead",
                    "http_code": response.status,
                    "final_url": final_url,
                    "error": "站点已关闭（重定向至关停公告）",
                }
            return {
                "status": "ok",
                "http_code": response.status,
                "final_url": final_url,
                "error": "",
            }
    except urllib.error.HTTPError as http_error:
        if http_error.code in HTTP_BLOCKED_STATUS_CODES:
            return {
                "status": "blocked",
                "http_code": http_error.code,
                "final_url": target_url,
                "error": f"HTTP {http_error.code}",
            }
        return {
            "status": "dead",
            "http_code": http_error.code,
            "final_url": target_url,
            "error": f"HTTP {http_error.code}",
        }
    except urllib.error.URLError as url_error:
        reason_text = str(url_error.reason)
        if "CERTIFICATE_VERIFY_FAILED" in reason_text or "certificate" in reason_text.lower():
            return {
                "status": "unreachable",
                "http_code": None,
                "final_url": target_url,
                "error": "SSL 证书校验失败",
            }
        # Windows 下 DNS 失败被包装成 EAI_NONAME -> OSError(2)，需用独立解析判定
        if not hostname_resolves(target_url):
            return {
                "status": "dead",
                "http_code": None,
                "final_url": target_url,
                "error": "DNS 解析失败（域名不存在）",
            }
        return {
            "status": "unreachable",
            "http_code": None,
            "final_url": target_url,
            "error": f"无法连接：{reason_text[:80]}",
        }
    except TimeoutError:
        return {"status": "unreachable", "http_code": None, "final_url": target_url, "error": "超时"}
    except Exception as unexpected_error:  # noqa: BLE001 - 探测脚本需要兜住一切网络异常
        return {
            "status": "unreachable",
            "http_code": None,
            "final_url": target_url,
            "error": f"{type(unexpected_error).__name__}: {unexpected_error}"[:120],
        }


def quark_share_token(share_id: str, passcode: str = "") -> tuple[str, str, int]:
    """取分享的 stoken。无需登录。返回 (stoken, 错误说明, 业务码)。

    业务码用于区分「需要提取码」（41008，可补救）与「文件涉及违规内容」
    （41010，平台已下架，救不回来）：两者都不返回 stoken，但结论完全不同。
    """
    payload = json.dumps({"pwd_id": share_id, "passcode": passcode}).encode("utf-8")
    request = urllib.request.Request(
        QUARK_API_BASE + QUARK_TOKEN_PATH,
        data=payload,
        headers={"content-type": "application/json", "accept": "application/json",
                 "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as http_error:
        # 违规内容时接口返回 HTTP 404，业务码藏在响应体里，必须读出来
        body = {}
        try:
            body = json.loads(http_error.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 - 响应体不是 JSON 时只能退回状态码
            body = {}
        business_code = int(body.get("code") or 0)
        message = str(body.get("message") or "")
        if business_code == QUARK_CONTENT_BLOCKED_CODE:
            return "", f"文件涉及违规内容（code {business_code}）", business_code
        return "", f"HTTP {http_error.code}" + (f" {message}" if message else ""), business_code
    except Exception as unexpected_error:  # noqa: BLE001 - 同 probe_single_url
        return "", f"{type(unexpected_error).__name__}: {unexpected_error}"[:100], 0

    business_code = int(body.get("code") or 0)
    stoken = ((body.get("data") or {}).get("stoken") or "")
    if stoken:
        return stoken, "", business_code
    if business_code == QUARK_PASSCODE_REQUIRED_CODE:
        return "", "需要提取码", business_code
    return "", str(body.get("message") or "未知错误")[:60], business_code


def quark_share_page(share_id: str, stoken: str, pdir_fid: str, page: int) -> tuple[list[dict], bool]:
    """取分享目录的一页。服务端单页硬限 QUARK_PAGE_SIZE 条。

    返回 (条目列表, 是否成功)。

    必须区分「这一页真的没有数据」和「这一页请求失败了」：
    前者表示目录到底了，后者只表示这次没拿到。混为一谈会导致翻页提前
    终止、静默漏数（实测同一分享两次统计相差 40 个文件，就是超时被当成空页）。
    """
    query = urllib.parse.urlencode({
        "pwd_id": share_id,
        "stoken": stoken,
        "pdir_fid": pdir_fid,
        "page": str(page),
        "_page": str(page),
        "_size": str(QUARK_PAGE_SIZE),
        "_fetch_total": "1",
        "_sort": "file_type:asc,updated_at:desc",
    })
    request = urllib.request.Request(
        f"{QUARK_API_BASE}{QUARK_DETAIL_PATH}?{query}",
        headers={"accept": "application/json", "User-Agent": USER_AGENT},
    )
    # 网络抖动很常见：实测同一分享连续两次统计相差 40 个文件，
    # 原因就是一次超时被当成「目录到底了」。这里重试，仍失败才上报。
    for attempt in range(QUARK_PAGE_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                body = json.loads(response.read().decode("utf-8"))
            return (body.get("data") or {}).get("list") or [], True
        except Exception:  # noqa: BLE001 - 失败要如实上报，不能伪装成空页
            if attempt == QUARK_PAGE_RETRIES - 1:
                return [], False
            time.sleep(0.4 * (attempt + 1))
    return [], False


def quark_share_walk(
    share_id: str,
    stoken: str,
    budget: dict,
    pdir_fid: str = "0",
    depth: int = 0,
) -> list[dict]:
    """递归 + 翻页遍历分享目录，返回 [{name, size, is_dir}]。

    budget 是共享的可变计数器 {"remaining": int, "truncated": bool, "failed_pages": int}。
    大分享（单学科数千节）完整遍历要上千次请求，超出预算时停止并置 truncated，
    由调用方如实标注，而不是把半个目录当成完整结果。
    """
    if budget["remaining"] <= 0:
        budget["truncated"] = True
        return []
    if depth > QUARK_MAX_DEPTH:
        return []

    collected: list[dict] = []
    for page_number in range(1, QUARK_MAX_PAGES + 1):
        if budget["remaining"] <= 0:
            budget["truncated"] = True
            break
        budget["remaining"] -= 1
        entries, page_ok = quark_share_page(share_id, stoken, pdir_fid, page_number)
        if not page_ok:
            # 这一页失败：记一笔并停止翻这个目录，绝不当作「到底了」
            budget["failed_pages"] += 1
            break
        if not entries:
            break
        for entry in entries:
            entry_name = entry.get("file_name") or ""
            is_directory = entry.get("file_type") == 0
            collected.append({
                "name": entry_name,
                "size": entry.get("size") or 0,
                "is_dir": is_directory,
            })
            if is_directory:
                children = quark_share_walk(share_id, stoken, budget, entry.get("fid") or "0", depth + 1)
                collected.extend({**child, "name": f"{entry_name}/{child['name']}"} for child in children)
        if len(entries) < QUARK_PAGE_SIZE:
            break
    return collected


def probe_quark_share(share_id: str, passcode: str = "", request_budget: int | None = None) -> dict:
    """探测单个夸克分享：是否需要提取码、总文件数、按扩展名统计。

    是否「需要提取码」必须先用空码试一次才能判定：带码成功不等于不需要码。
    """
    _, empty_code_error, _ = quark_share_token(share_id, "")
    needs_passcode = "提取码" in empty_code_error

    stoken, token_error, token_code = quark_share_token(share_id, passcode)
    if not stoken:
        if token_code == QUARK_CONTENT_BLOCKED_CODE:
            status = "dead"
        else:
            status = "blocked" if "提取码" in token_error else "unreachable"
        return {
            "status": status,
            "needs_passcode": needs_passcode,
            "passcode_valid": False if passcode else None,
            "total_files": None,
            "truncated": False,
            "error": token_error,
        }

    budget_limit = request_budget if request_budget is not None else QUARK_REQUEST_BUDGET
    budget = {"remaining": budget_limit, "truncated": False, "failed_pages": 0}
    entries = quark_share_walk(share_id, stoken, budget)
    files = [entry for entry in entries if not entry["is_dir"]]
    suffix_counts: dict[str, int] = {}
    for entry in files:
        suffix = pathlib.PurePosixPath(entry["name"]).suffix.lower() or "(无扩展名)"
        suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1

    # 有失败页时，文件数是「至少这么多」，不能当完整值用
    incomplete = budget["truncated"] or budget["failed_pages"] > 0

    return {
        "status": "ok",
        "needs_passcode": needs_passcode,
        "passcode_valid": True if passcode else None,
        "total_files": len(files),
        "total_size_bytes": sum(entry["size"] for entry in files),
        "suffix_counts": dict(sorted(suffix_counts.items(), key=lambda pair: -pair[1])),
        "truncated": budget["truncated"],
        "failed_pages": budget["failed_pages"],
        "incomplete": incomplete,
        "requests_used": budget_limit - budget["remaining"],
        "error": "",
    }


def probe_quark_shallow(share_id: str, passcode: str = "") -> dict:
    """只读分享的前 QUARK_SHALLOW_DEPTH 层，返回目录结构与文件计数。

    与 probe_quark_share 的区别是**明确不做全量**：大批量教辅分享（每包几十个
    教辅目录，每个目录下再按年级/版本分册）全量遍历要跑数小时，而使用者真正
    需要的是「这一包收了哪些教辅」。因此这里只回答结构，文件数按层计。

    返回的 l2_file_count 只统计第 2 层的直接文件；目录里的文件未计入，
    所以它**不是**资料规模，不能当 share_total_files 用。
    """
    _, empty_code_error, _ = quark_share_token(share_id, "")
    needs_passcode = "提取码" in empty_code_error

    stoken, token_error, token_code = quark_share_token(share_id, passcode)
    if not stoken:
        if token_code == QUARK_CONTENT_BLOCKED_CODE:
            status = "dead"
        else:
            status = "blocked" if "提取码" in token_error else "unreachable"
        return {
            "status": status,
            "needs_passcode": needs_passcode,
            "passcode_valid": False if passcode else None,
            "top_name": "",
            "l2_entries": None,
            "l2_dirs": [],
            "l2_dir_count": None,
            "l2_file_count": None,
            "l3_dir_names": [],
            "truncated": False,
            "requests_used": 2,
            "error": token_error,
        }

    budget = {"remaining": QUARK_SHALLOW_REQUEST_BUDGET, "truncated": False, "failed_pages": 0}
    top_entries = quark_share_walk_level(share_id, stoken, budget, "0")
    top_name = top_entries[0]["name"] if top_entries else ""

    # 顶层常常只有 1 个同名总目录，要下钻一层才是各科教辅。
    # 「第 2 层」是使用者视角的教辅层，所以无论顶层有没有包裹目录，
    # 都要保证读到 QUARK_SHALLOW_DEPTH 这一层，否则单独一包教辅会读成空。
    level_two = top_entries
    current_depth = 1
    while (
        current_depth < QUARK_SHALLOW_DEPTH
        and len(level_two) == 1
        and level_two[0]["is_dir"]
    ):
        level_two = quark_share_walk_level(share_id, stoken, budget, level_two[0]["fid"])
        current_depth += 1

    level_two_dirs = [entry for entry in level_two if entry["is_dir"]]
    level_two_files = [entry for entry in level_two if not entry["is_dir"]]

    # 第 3 层只抽样：取前几个子目录看一层，用于说明「内容还在更下面」。
    # 抽样不是遍历，所以不置 truncated —— 截断标记只表示第 2 层本身没读全。
    level_three_names: list[str] = []
    for entry in level_two_dirs[:QUARK_SHALLOW_L3_SAMPLE_DIRS]:
        if budget["remaining"] <= 0 or len(level_three_names) >= QUARK_SHALLOW_MAX_DIR_NAMES:
            break
        grandchildren = quark_share_walk_level(share_id, stoken, budget, entry["fid"], max_pages=1)
        level_three_names.extend(
            f"{entry['name']}/{child['name']}" for child in grandchildren if child["is_dir"]
        )

    incomplete = budget["truncated"] or budget["failed_pages"] > 0
    return {
        "status": "ok",
        "needs_passcode": needs_passcode,
        "passcode_valid": True if passcode else None,
        "top_name": top_name,
        "l2_entries": len(level_two),
        "l2_dirs": [entry["name"] for entry in level_two_dirs][:QUARK_SHALLOW_MAX_DIR_NAMES],
        "l2_dir_count": len(level_two_dirs),
        "l2_file_count": len(level_two_files),
        "l3_dir_names": level_three_names[:QUARK_SHALLOW_MAX_DIR_NAMES],
        "truncated": budget["truncated"],
        "failed_pages": budget["failed_pages"],
        "incomplete": incomplete,
        "requests_used": QUARK_SHALLOW_REQUEST_BUDGET - budget["remaining"],
        "error": "",
    }


def quark_share_walk_level(
    share_id: str, stoken: str, budget: dict, pdir_fid: str, max_pages: int = QUARK_MAX_PAGES
) -> list[dict]:
    """翻完单个目录的所有页（最多 max_pages 页），不递归子目录。

    返回 [{fid, name, size, is_dir}]。与 quark_share_walk 的区别：只走一层，
    供浅层探测按层控制深度；max_pages 用于第 3 层抽样，只取第一页的目录名。
    请求失败仍然记 failed_pages，不当成「目录到底了」。
    """
    collected: list[dict] = []
    for page_number in range(1, max_pages + 1):
        if budget["remaining"] <= 0:
            budget["truncated"] = True
            break
        budget["remaining"] -= 1
        entries, page_ok = quark_share_page(share_id, stoken, pdir_fid, page_number)
        if not page_ok:
            budget["failed_pages"] += 1
            break
        if not entries:
            break
        for entry in entries:
            collected.append({
                "fid": entry.get("fid") or "0",
                "name": entry.get("file_name") or "",
                "size": entry.get("size") or 0,
                "is_dir": entry.get("file_type") == 0,
            })
        if len(entries) < QUARK_PAGE_SIZE:
            break
    return collected


def collect_quark_targets(resources: dict) -> list[dict]:
    """从 collections 里抽出所有夸克官方分享 id。

    有些条目原始入口是第三方短链，真实的夸克分享记在 *_redirected_to 里，
    也要一并纳入，否则会漏掉 learn_english_movies / word_posters / wordly_wise_3000。

    预算按条目可覆盖：数据里写 share_request_budget 就用它，
    用于「这个分享特别大，值得多花时间」的情况。
    """
    targets: list[dict] = []
    seen_share_ids: set[str] = set()
    for item in resources.get("collections", []):
        # 标了 shallow 的条目走 quark_shallow 分区，不能被全量遍历误抓：
        # 44 个教辅分享全量要跑数小时，这是刻意的隔离，不是遗漏
        if item.get("share_probe_depth") == "shallow":
            continue
        candidate_urls = [
            item.get("url_official") or "",
            item.get("url_official_redirected_to") or "",
            item.get("url_alt_redirected_to") or "",
        ]
        for candidate_url in candidate_urls:
            match = QUARK_SHARE_PATTERN.search(candidate_url)
            if not match:
                continue
            share_id = match.group(1)
            if share_id in seen_share_ids:
                continue
            seen_share_ids.add(share_id)
            targets.append({
                "section": "quark_tree",
                "group": "quark_tree",
                "id": item["id"],
                "share_id": share_id,
                "passcode": item.get("password") or "",
                "request_budget": item.get("share_request_budget"),
            })
    return targets


def collect_quark_shallow_targets(resources: dict) -> list[dict]:
    """抽出所有标了 share_probe_depth: shallow 的夸克分享。

    与 collect_quark_targets 互斥：同一个 share id 只会进其中一个列表，
    避免一次运行既跑全量又跑浅层。
    """
    targets: list[dict] = []
    seen_share_ids: set[str] = set()
    for item in resources.get("collections", []):
        if item.get("share_probe_depth") != "shallow":
            continue
        match = QUARK_SHARE_PATTERN.search(item.get("url_official") or "")
        if not match:
            continue
        share_id = match.group(1)
        if share_id in seen_share_ids:
            continue
        seen_share_ids.add(share_id)
        targets.append({
            "section": "quark_shallow",
            "group": "quark_shallow",
            "id": item["id"],
            "share_id": share_id,
            "passcode": item.get("password") or "",
        })
    return targets


def collect_sheet_index_targets(resources: dict) -> list[dict]:
    """抽出腾讯文档总索引条目。"""
    targets: list[dict] = []
    for item in resources.get("collections", []):
        url = item.get("url_official") or ""
        if not SHEET_DOC_PATTERN.search(url):
            continue
        targets.append({
            "section": "sheet_index",
            "group": "sheet_index",
            "id": item["id"],
            "url": url,
        })
    return targets


def collect_targets(resources: dict, only_sections: set[str] | None) -> list[dict]:
    """把 JSON 里所有需要探测的 URL 摊平成任务列表。"""
    targets: list[dict] = []

    def should_run(section_name: str) -> bool:
        return only_sections is None or section_name in only_sections

    if should_run("websites"):
        for item in resources.get("websites", []):
            if item.get("verified") in MANUAL_STATUSES or item.get(MANUAL_STATUS_FLAG):
                continue
            targets.append({"section": "websites", "group": "websites", "id": item["id"], "url": item["url"]})

    if should_run("tutoring"):
        # 只探入口可达性。alipay / fixed_teacher 是人工核对的结论，
        # 官网支付说明页返回 200 不代表支持支付宝，探针不能碰这些字段。
        for item in resources.get("tutoring", []):
            if item.get("verified") in MANUAL_STATUSES or item.get(MANUAL_STATUS_FLAG):
                continue
            targets.append(
                {
                    "section": "tutoring",
                    "group": "tutoring",
                    "id": item["id"],
                    "url": item["url"],
                    "field": "url",
                }
            )

    if should_run("repos"):
        for item in resources.get("repos", []):
            targets.append({"section": "repos", "group": "repos", "id": item["id"], "url": item["url"]})

    if should_run("videos"):
        # 只探 B站 播放页可达性。分P数、时长、播放量是 search_bilibili_courses.py
        # 调 view 接口拿的实测值，探针只做 HTTP 可达性确认，不改这些字段。
        for item in resources.get("videos", []):
            if not item.get("url"):
                continue
            targets.append(
                {
                    "section": "videos",
                    "group": "videos",
                    "id": item["id"],
                    "url": item["url"],
                    "field": "url",
                }
            )

    if should_run("collections"):
        for item in resources.get("collections", []):
            # 人工结论条目（违规下架 / 内容与描述不符）不探：分享页本身可能仍返回 200，
            # 探了会把 dead 冲成 ok，而接口层面的结论已经写进 note
            if item.get("verified") in MANUAL_STATUSES or item.get(MANUAL_STATUS_FLAG):
                continue
            for url_field in ("url_official", "url_alias", "url_alt"):
                if item.get(url_field):
                    targets.append(
                        {
                            "section": "collections",
                            "group": "collections",
                            "id": item["id"],
                            "url": item[url_field],
                            "field": url_field,
                        }
                    )

    if should_run("markdown"):
        already_covered = {target["url"] for target in targets}
        if COLLECTIONS_DIR.is_dir():
            for markdown_path in sorted(COLLECTIONS_DIR.glob("*.md")):
                text = markdown_path.read_text(encoding="utf-8")
                seen_in_file: set[str] = set()
                for found_url in URL_PATTERN.findall(text):
                    cleaned_url = found_url.rstrip(".,;:")
                    if cleaned_url in seen_in_file or cleaned_url in already_covered:
                        continue
                    seen_in_file.add(cleaned_url)
                    targets.append(
                        {
                            "section": "markdown",
                            "group": markdown_path.name,
                            "id": cleaned_url,
                            "url": cleaned_url,
                        }
                    )
    return targets


def run_probes(targets: list[dict]) -> list[dict]:
    results: list[dict] = []
    with futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_target = {executor.submit(probe_single_url, target["url"]): target for target in targets}
        for completed_future in futures.as_completed(future_to_target):
            target = future_to_target[completed_future]
            probe_result = completed_future.result()
            results.append({**target, **probe_result})
    results.sort(key=lambda row: (row["section"], row["group"], row["id"], row["url"]))
    return results


def run_quark_probes(targets: list[dict]) -> list[dict]:
    """夸克分享目录探测。逐条串行跑，避免对同一站点并发过高被限流。"""
    results: list[dict] = []
    for target in targets:
        probe_result = probe_quark_share(
            target["share_id"], target["passcode"], target.get("request_budget")
        )
        results.append({**target, **probe_result})
    results.sort(key=lambda row: row["id"])
    return results


def run_quark_shallow_probes(targets: list[dict]) -> list[dict]:
    """浅层探测同样串行。单包要 10-25 秒，并发会把夸克接口打出限流。"""
    results: list[dict] = []
    for target in targets:
        probe_result = probe_quark_shallow(target["share_id"], target["passcode"])
        results.append({**target, **probe_result})
    results.sort(key=lambda row: row["id"])
    return results


def write_quark_results_back(resources: dict, results: list[dict], checked_at_iso: str) -> int:
    """把夸克目录探测结果回写到 collections。

    只写结构化数值字段，不改已有的 actual / note 等人工复核过的文字描述。
    """
    by_id = {row["id"]: row for row in results}
    updated_count = 0
    for item in resources.get("collections", []):
        row = by_id.get(item["id"])
        if row is None:
            continue
        item["needs_passcode"] = row["needs_passcode"]
        if row.get("passcode_valid") is not None:
            item["passcode_valid"] = row["passcode_valid"]
        if row.get("total_files") is not None:
            item["share_total_files"] = row["total_files"]
            item["share_total_size_bytes"] = row["total_size_bytes"]
            item["share_suffix_counts"] = row["suffix_counts"]
            item["share_tree_truncated"] = row.get("truncated", False)
            item["share_tree_failed_pages"] = row.get("failed_pages", 0)
            item["share_tree_incomplete"] = row.get("incomplete", False)
            item["share_tree_requests"] = row.get("requests_used")
        if row.get("error"):
            item["share_tree_error"] = row["error"]
        else:
            item.pop("share_tree_error", None)
        item["tree_checked_at"] = checked_at_iso
        updated_count += 1
    return updated_count


def print_quark_report(results: list[dict]) -> None:
    for row in results:
        if row["status"] != "ok":
            reason = "需要提取码（未提供）" if row["needs_passcode"] else row["error"]
            print(f"[{'PASS' if row['needs_passcode'] else 'FAIL'}] quark_tree  {row['id']:24} {reason}")
            continue
        suffixes = "  ".join(f"{suffix}={count}" for suffix, count in list(row["suffix_counts"].items())[:4])
        truncated_note = "  [已截断：超出请求预算]" if row.get("truncated") else ""
        failed_note = f"  [{row['failed_pages']} 页请求失败，数字为下限]" if row.get("failed_pages") else ""
        passcode_note = "  [需提取码，已用记录的码通过]" if row["needs_passcode"] else ""
        print(f"[OK  ] quark_tree  {row['id']:24} {row['total_files']:5} 个文件  "
              f"({row.get('requests_used', 0)} 次请求)  {suffixes}{passcode_note}{truncated_note}{failed_note}")

    print()
    ok_count = sum(1 for row in results if row["status"] == "ok")
    passcode_count = sum(1 for row in results if row["needs_passcode"])
    # 带码成功读通的条目同时满足 ok 与 needs_passcode，失败数必须排除它们，否则会出现负数
    fail_count = sum(1 for row in results if row["status"] != "ok" and not row["needs_passcode"])
    incomplete_count = sum(1 for row in results if row["status"] == "ok" and (row.get("truncated") or row.get("failed_pages")))
    print(f"夸克分享 {len(results)} 条：已读目录={ok_count}（其中需提取码 {passcode_count} 条）"
          f"  未读={fail_count}"
          + (f"  数字不完整={incomplete_count}" if incomplete_count else ""))


def write_quark_shallow_results_back(resources: dict, results: list[dict], checked_at_iso: str) -> int:
    """把浅层探测结果回写到 collections。

    只写结构与计数，不碰 share_total_files —— 浅层的文件数按层计，
    不是资料规模，写进去会让人误以为是全量。
    """
    by_id = {row["id"]: row for row in results}
    updated_count = 0
    for item in resources.get("collections", []):
        row = by_id.get(item["id"])
        if row is None:
            continue
        item["share_probe_checked_at"] = checked_at_iso
        updated_count += 1
        if row["status"] != "ok":
            item["share_probe_error"] = row["error"]
            continue
        item.pop("share_probe_error", None)
        item["share_top_name"] = row["top_name"]
        item["share_l2_entries"] = row["l2_entries"]
        item["share_l2_dir_count"] = row["l2_dir_count"]
        item["share_l2_file_count"] = row["l2_file_count"]
        item["share_l2_dirs"] = row["l2_dirs"]
        item["share_l3_dir_names"] = row["l3_dir_names"]
        item["share_probe_truncated"] = row["truncated"]
        item["share_probe_requests"] = row["requests_used"]
        if row.get("passcode_valid") is not None:
            item["passcode_valid"] = row["passcode_valid"]
        item["needs_passcode"] = row["needs_passcode"]
    return updated_count


def print_quark_shallow_report(results: list[dict]) -> None:
    for row in results:
        if row["status"] != "ok":
            print(f"[{'FAIL' if row['status'] == 'dead' else 'SKIP'}] quark_shallow {row['id']:26} {row['error']}")
            continue
        truncated_note = "  [已截断：超出请求预算]" if row.get("truncated") else ""
        failed_note = f"  [{row['failed_pages']} 页请求失败]" if row.get("failed_pages") else ""
        print(f"[OK  ] quark_shallow {row['id']:26} 第2层 {row['l2_entries']:3} 项"
              f"（目录 {row['l2_dir_count']:3} / 文件 {row['l2_file_count']:3}）"
              f"  {row.get('requests_used', 0):3} 次请求{truncated_note}{failed_note}")
        if row["l2_dirs"]:
            head = "  ".join(row["l2_dirs"][:6])
            print(f"        {head}{'  …' if len(row['l2_dirs']) > 6 else ''}")

    print()
    ok_count = sum(1 for row in results if row["status"] == "ok")
    dead_count = sum(1 for row in results if row["status"] == "dead")
    other_count = len(results) - ok_count - dead_count
    print(f"浅层探测 {len(results)} 条：已读={ok_count}  已失效={dead_count}"
          + (f"  其它失败={other_count}" if other_count else ""))


def probe_sheet_index(target_url: str) -> dict:
    """读腾讯文档总索引，统计页面内嵌的夸克分享链接数。

    表格数据藏在 percent-encoded 的 flyweight.texts 里，因此先整体 unquote 再计数。
    只数不去重：同一个 share id 可能在不同科目分组下重复出现。
    """
    request = urllib.request.Request(target_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS * 2) as response:
            raw_text = response.read().decode("utf-8", errors="replace")
    except Exception as unexpected_error:  # noqa: BLE001 - 同 probe_single_url
        return {"status": "unreachable", "title": "", "quark_links": None,
                "quark_links_unique": None, "error": f"{type(unexpected_error).__name__}: {unexpected_error}"[:100]}

    decoded_text = urllib.parse.unquote(raw_text)
    quark_links = re.findall(r"pan\.quark\.cn/s/([a-zA-Z0-9]+)", decoded_text)

    # 标题不在明文里：页面把 clientVars 用 base64 塞进 basicClientVars，
    # 明文的 <title> 是通用的「腾讯文档」。解不出来就留空，不猜。
    title = ""
    encoded_match = re.search(r"basicClientVars=JSON\.parse\(decodeURIComponent\(escape\(atob\('([A-Za-z0-9+/=]+)'", decoded_text)
    if encoded_match:
        try:
            client_vars = json.loads(base64.b64decode(encoded_match.group(1)).decode("utf-8"))
            title = ((client_vars.get("docInfo") or {}).get("padInfo") or {}).get("padTitle") or ""
        except Exception:  # noqa: BLE001 - 标题只是展示用，解不出来不影响链接计数
            title = ""

    return {
        "status": "ok",
        "title": title,
        "quark_links": len(quark_links),
        "quark_links_unique": len(set(quark_links)),
        "error": "",
    }


def run_sheet_index_probes(targets: list[dict]) -> list[dict]:
    results: list[dict] = []
    for target in targets:
        results.append({**target, **probe_sheet_index(target["url"])})
    results.sort(key=lambda row: row["id"])
    return results


def write_sheet_index_results_back(resources: dict, results: list[dict], checked_at_iso: str) -> int:
    by_id = {row["id"]: row for row in results}
    updated_count = 0
    for item in resources.get("collections", []):
        row = by_id.get(item["id"])
        if row is None:
            continue
        item["verified"] = "ok" if row["status"] == "ok" else row["status"]
        item["checked_at"] = checked_at_iso
        if row["status"] == "ok":
            item["sheet_title"] = row["title"]
            item["sheet_embedded_quark_links"] = row["quark_links"]
            item["sheet_embedded_quark_links_unique"] = row["quark_links_unique"]
        updated_count += 1
    return updated_count


def print_sheet_index_report(results: list[dict]) -> None:
    for row in results:
        if row["status"] != "ok":
            print(f"[FAIL] sheet_index {row['id']:26} {row['error']}")
            continue
        print(f"[OK  ] sheet_index {row['id']:26} 「{row['title']}」"
              f"  内嵌夸克链接 {row['quark_links']} 条（去重 {row['quark_links_unique']} 条）")
    print()
    ok_count = sum(1 for row in results if row["status"] == "ok")
    print(f"腾讯文档索引 {len(results)} 条：已读={ok_count}  失败={len(results) - ok_count}")


def write_results_back(resources: dict, results: list[dict], checked_at_iso: str) -> int:
    """把探测结果回写到 JSON。返回更新条目数。"""
    by_key: dict[tuple[str, str, str], dict] = {}
    for row in results:
        field = row.get("field") or ("url_official" if row["section"] == "collections" else "url")
        by_key[(row["section"], row["id"], field)] = row

    updated_count = 0
    for item in resources.get("websites", []):
        row = by_key.get(("websites", item["id"], "url"))
        if row is None:
            continue
        item["verified"] = row["status"]
        item["checked_at"] = checked_at_iso
        if row["final_url"] and row["final_url"] != item["url"]:
            item["redirected_to"] = row["final_url"]
        else:
            item.pop("redirected_to", None)
        updated_count += 1

    for item in resources.get("tutoring", []):
        # 只写可达性字段。支付方式与固定老师是人工核对结论，
        # 探针把页面探通就顺手改 alipay，等于用「页面能打开」冒充「支持支付宝」。
        row = by_key.get(("tutoring", item["id"], "url"))
        if row is None:
            continue
        item["verified"] = row["status"]
        item["checked_at"] = checked_at_iso
        if row["final_url"] and row["final_url"] != item["url"]:
            item["redirected_to"] = row["final_url"]
        else:
            item.pop("redirected_to", None)
        updated_count += 1

    for item in resources.get("repos", []):
        row = by_key.get(("repos", item["id"], "url"))
        if row is None:
            continue
        item["verified"] = row["status"]
        item["checked_at"] = checked_at_iso
        if row["final_url"] and row["final_url"] != item["url"]:
            item["redirected_to"] = row["final_url"]
        else:
            item.pop("redirected_to", None)
        updated_count += 1

    for item in resources.get("videos", []):
        # 只写可达性字段。pages / duration_seconds / play 由
        # search_bilibili_courses.py 调 view 接口取，探针不改这些实测值。
        row = by_key.get(("videos", item["id"], "url"))
        if row is None:
            continue
        item["verified"] = row["status"]
        item["checked_at"] = checked_at_iso
        if row["final_url"] and row["final_url"] != item["url"]:
            item["redirected_to"] = row["final_url"]
        else:
            item.pop("redirected_to", None)
        updated_count += 1

    for item in resources.get("collections", []):
        if item.get("verified") in MANUAL_STATUSES or item.get(MANUAL_STATUS_FLAG):
            continue
        field_statuses: list[str] = []
        for url_field in ("url_official", "url_alias", "url_alt"):
            row = by_key.get(("collections", item["id"], url_field))
            if row is None:
                continue
            item[f"{url_field}_verified"] = row["status"]
            if row["final_url"] and row["final_url"] != item[url_field]:
                item[f"{url_field}_redirected_to"] = row["final_url"]
            else:
                item.pop(f"{url_field}_redirected_to", None)
            field_statuses.append(row["status"])
        if field_statuses:
            item["verified"] = "ok" if all(status == "ok" for status in field_statuses) else field_statuses[0]
            item["checked_at"] = checked_at_iso
            updated_count += 1

    resources["checked_at"] = checked_at_iso
    return updated_count


def print_report(results: list[dict], resources_ref: dict | None = None) -> None:
    status_symbols = {"ok": "[OK  ]", "blocked": "[403 ]", "dead": "[DEAD]", "unreachable": "[FAIL]"}
    for row in results:
        symbol = status_symbols.get(row["status"], "[????]")
        redirect_note = ""
        if row["final_url"] and row["final_url"] != row["url"]:
            redirect_note = f"  -> {row['final_url']}"
        error_note = f"  ({row['error']})" if row["error"] else ""
        print(f"{symbol} {row['section']:11} {row['id']:28} {row['url']}{redirect_note}{error_note}")

    print()
    counts: dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    summary = "  ".join(f"{status}={counts.get(status, 0)}" for status in ("ok", "blocked", "dead", "unreachable"))
    print(f"总计 {len(results)} 条：{summary}")
    problematic = [row for row in results if row["status"] in ("dead", "unreachable")]
    if problematic:
        print("\n需要处理：")
        for row in problematic:
            print(f"  - {row['section']}/{row['id']}: {row['url']} ({row['error']})")

    manual_count = sum(
        1 for section in ("websites", "collections")
        for item in (resources_ref or {}).get(section, [])
        if item.get("verified") in MANUAL_STATUSES or item.get(MANUAL_STATUS_FLAG)
    )
    if manual_count:
        print(f"\n另有 {manual_count} 条为人工判定状态（mismatch / status_manual），脚本已跳过，需人工复核。")


def main() -> int:
    # Windows 控制台默认 GBK，中文报告会乱码
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="校验 ai-teacher 仓库内的所有链接")
    parser.add_argument("--write", action="store_true", help="把结果回写到 data/resources.json")
    parser.add_argument(
        "--only",
        default="websites,tutoring,repos,videos,collections,markdown,quark_tree",
        help="只跑指定分区，逗号分隔：websites,tutoring,repos,videos,collections,markdown,quark_tree,quark_shallow,sheet_index",
    )
    arguments = parser.parse_args()

    if not RESOURCES_PATH.is_file():
        print(f"找不到 {RESOURCES_PATH}", file=sys.stderr)
        return 1

    resources = json.loads(RESOURCES_PATH.read_text(encoding="utf-8"))
    only_sections = {name.strip() for name in arguments.only.split(",") if name.strip()}

    quark_targets = collect_quark_targets(resources) if "quark_tree" in only_sections else []
    quark_shallow_targets = (
        collect_quark_shallow_targets(resources) if "quark_shallow" in only_sections else []
    )
    sheet_targets = collect_sheet_index_targets(resources) if "sheet_index" in only_sections else []
    targets = collect_targets(resources, only_sections)

    if not targets and not quark_targets and not quark_shallow_targets and not sheet_targets:
        print("没有需要探测的链接", file=sys.stderr)
        return 1

    results: list[dict] = []
    if targets:
        print(f"待探测 {len(targets)} 条链接（超时 {REQUEST_TIMEOUT_SECONDS}s，并发 {MAX_WORKERS}）\n")
        results = run_probes(targets)
        print_report(results, resources)

    quark_results: list[dict] = []
    if quark_targets:
        print(f"\n待读 {len(quark_targets)} 个夸克分享目录（公开接口，无需登录；单页上限 {QUARK_PAGE_SIZE}，自动翻页）\n")
        quark_results = run_quark_probes(quark_targets)
        print_quark_report(quark_results)

    quark_shallow_results: list[dict] = []
    if quark_shallow_targets:
        print(f"\n待读 {len(quark_shallow_targets)} 个夸克分享（浅层，只翻到第 {QUARK_SHALLOW_DEPTH} 层，"
              f"单条请求上限 {QUARK_SHALLOW_REQUEST_BUDGET}）\n")
        quark_shallow_results = run_quark_shallow_probes(quark_shallow_targets)
        print_quark_shallow_report(quark_shallow_results)

    sheet_results: list[dict] = []
    if sheet_targets:
        print(f"\n待读 {len(sheet_targets)} 个腾讯文档总索引\n")
        sheet_results = run_sheet_index_probes(sheet_targets)
        print_sheet_index_report(sheet_results)

    if arguments.write:
        checked_at_iso = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        updated_count = write_results_back(resources, results, checked_at_iso)
        quark_updated = write_quark_results_back(resources, quark_results, checked_at_iso)
        shallow_updated = write_quark_shallow_results_back(
            resources, quark_shallow_results, checked_at_iso
        )
        sheet_updated = write_sheet_index_results_back(resources, sheet_results, checked_at_iso)
        RESOURCES_PATH.write_text(
            json.dumps(resources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\n已回写 {updated_count} 条链接、{quark_updated} 条夸克目录、"
              f"{shallow_updated} 条浅层探测、{sheet_updated} 条腾讯文档索引，checked_at = {checked_at_iso}")

    dead_or_unreachable = [row for row in results if row["status"] in ("dead", "unreachable")]
    dead_or_unreachable += [row for row in sheet_results if row["status"] in ("dead", "unreachable")]
    return 1 if dead_or_unreachable else 0


if __name__ == "__main__":
    raise SystemExit(main())
