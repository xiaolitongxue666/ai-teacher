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
        default="websites,repos,collections,markdown",
        help="只跑指定分区，逗号分隔：websites,repos,collections,markdown",
    )
    arguments = parser.parse_args()

    if not RESOURCES_PATH.is_file():
        print(f"找不到 {RESOURCES_PATH}", file=sys.stderr)
        return 1

    resources = json.loads(RESOURCES_PATH.read_text(encoding="utf-8"))
    only_sections = {name.strip() for name in arguments.only.split(",") if name.strip()}
    targets = collect_targets(resources, only_sections)
    if not targets:
        print("没有需要探测的链接", file=sys.stderr)
        return 1

    print(f"待探测 {len(targets)} 条链接（超时 {REQUEST_TIMEOUT_SECONDS}s，并发 {MAX_WORKERS}）\n")
    results = run_probes(targets)
    print_report(results, resources)

    if arguments.write:
        checked_at_iso = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        updated_count = write_results_back(resources, results, checked_at_iso)
        RESOURCES_PATH.write_text(
            json.dumps(resources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\n已回写 {updated_count} 条记录，checked_at = {checked_at_iso}")

    dead_or_unreachable = [row for row in results if row["status"] in ("dead", "unreachable")]
    return 1 if dead_or_unreachable else 0


if __name__ == "__main__":
    raise SystemExit(main())
