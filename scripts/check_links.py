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
  python scripts/check_links.py --only quark_tree   # 只读夸克分享目录
"""

from __future__ import annotations

import argparse
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


def quark_share_token(share_id: str, passcode: str = "") -> tuple[str, str]:
    """取分享的 stoken。无需登录。返回 (stoken, 错误说明)。"""
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
        return "", f"HTTP {http_error.code}"
    except Exception as unexpected_error:  # noqa: BLE001 - 同 probe_single_url
        return "", f"{type(unexpected_error).__name__}: {unexpected_error}"[:100]

    stoken = ((body.get("data") or {}).get("stoken") or "")
    if stoken:
        return stoken, ""
    if body.get("code") == QUARK_PASSCODE_REQUIRED_CODE:
        return "", "需要提取码"
    return "", str(body.get("message") or "未知错误")[:60]


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
    _, empty_code_error = quark_share_token(share_id, "")
    needs_passcode = "提取码" in empty_code_error

    stoken, token_error = quark_share_token(share_id, passcode)
    if not stoken:
        return {
            "status": "blocked" if "提取码" in token_error else "unreachable",
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


def collect_targets(resources: dict, only_sections: set[str] | None) -> list[dict]:
    """把 JSON 里所有需要探测的 URL 摊平成任务列表。"""
    targets: list[dict] = []

    def should_run(section_name: str) -> bool:
        return only_sections is None or section_name in only_sections

    if should_run("websites"):
        for item in resources.get("websites", []):
            if item.get("verified") in MANUAL_STATUSES:
                continue
            targets.append({"section": "websites", "group": "websites", "id": item["id"], "url": item["url"]})

    if should_run("repos"):
        for item in resources.get("repos", []):
            targets.append({"section": "repos", "group": "repos", "id": item["id"], "url": item["url"]})

    if should_run("collections"):
        for item in resources.get("collections", []):
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

    for item in resources.get("collections", []):
        if item.get("verified") in MANUAL_STATUSES:
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
        if item.get("verified") in MANUAL_STATUSES
    )
    if manual_count:
        print(f"\n另有 {manual_count} 条为人工判定状态（mismatch），脚本已跳过，需人工复核。")


def main() -> int:
    # Windows 控制台默认 GBK，中文报告会乱码
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="校验 ai-teacher 仓库内的所有链接")
    parser.add_argument("--write", action="store_true", help="把结果回写到 data/resources.json")
    parser.add_argument(
        "--only",
        default="websites,repos,collections,markdown,quark_tree",
        help="只跑指定分区，逗号分隔：websites,repos,collections,markdown,quark_tree",
    )
    arguments = parser.parse_args()

    if not RESOURCES_PATH.is_file():
        print(f"找不到 {RESOURCES_PATH}", file=sys.stderr)
        return 1

    resources = json.loads(RESOURCES_PATH.read_text(encoding="utf-8"))
    only_sections = {name.strip() for name in arguments.only.split(",") if name.strip()}

    quark_targets = collect_quark_targets(resources) if "quark_tree" in only_sections else []
    targets = collect_targets(resources, only_sections)

    if not targets and not quark_targets:
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

    if arguments.write:
        checked_at_iso = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        updated_count = write_results_back(resources, results, checked_at_iso)
        quark_updated = write_quark_results_back(resources, quark_results, checked_at_iso)
        RESOURCES_PATH.write_text(
            json.dumps(resources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\n已回写 {updated_count} 条链接记录、{quark_updated} 条夸克目录记录，checked_at = {checked_at_iso}")

    dead_or_unreachable = [row for row in results if row["status"] in ("dead", "unreachable")]
    return 1 if dead_or_unreachable else 0


if __name__ == "__main__":
    raise SystemExit(main())
