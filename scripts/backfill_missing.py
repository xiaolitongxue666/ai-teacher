"""补下某条目里未落盘的文件。

背景：`download_with_login` 对单文件失败只记 last_error 继续下一个，早期版本
还会把整条分享记成 `ok`。2026-11-11 实测 p_math 缺 1882 个、p_eng 缺 615 个，
都是在跑完之后才发现的。管道已改为有失败就记 `incomplete` 并落 `_missing.json`，
但对已经残缺的条目仍需这里回补。

做法：重新 walk 分享拿最新 stoken 与 fid，逐个比对磁盘，只下缺的那些。
已完成且体积一致的文件跳过，不会重复下载。

用法：
    python scripts/backfill_missing.py p_math p_eng
    python scripts/backfill_missing.py p_math --dry-run
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from downloads import common, quark  # noqa: E402


def collect_missing(item: dict, opener, inventory: dict) -> list[dict]:
    """返回该分享里未落盘或体积不符的条目。"""
    base = quark.target_dir_for(item)
    root_prefix = quark.share_root_prefix(inventory["entries"])
    missing: list[dict] = []
    for entry in inventory["entries"]:
        relative = quark.relative_after_root(entry, root_prefix)
        destination = base / common.sanitize_relative_path(relative)
        if destination.is_file() and destination.stat().st_size == entry["size"]:
            continue
        missing.append({**entry, "relative": relative})
    return missing


def backfill(item_id: str, dry_run: bool) -> int:
    planned = {item["id"]: item for item in quark.plan_netdisk()}
    item = planned.get(item_id)
    if not item or not item.get("share_id"):
        print(f"{item_id}: 无夸克源，跳过", flush=True)
        return 0

    cookie = common.read_credentials().get("NETDISK_QUARK_COOKIE", "")
    logged_in, note = quark.login_state(cookie)
    print(f"{item_id}: login={logged_in} {note[:40]}", flush=True)
    if not logged_in:
        return 1

    opener = quark._opener_with_cookie(cookie)
    inventory = quark.walk_share(item["share_id"], item["passcode"], None,
                                 opener=opener)
    missing = collect_missing(item, opener, inventory)
    total_bytes = sum(int(entry.get("size") or 0) for entry in missing)
    print(f"{item_id}: 分享 {len(inventory['entries'])} 个，缺 {len(missing)} 个 "
          f"/ {common.format_bytes(total_bytes)}", flush=True)
    if not missing:
        return 0
    if dry_run:
        for entry in missing[:10]:
            print(f"  缺 {entry['relative'][-60:]} "
                  f"{common.format_bytes(entry.get('size') or 0)}", flush=True)
        return 0

    base = quark.target_dir_for(item)
    base.mkdir(parents=True, exist_ok=True)
    remaining = 0
    failed = 0
    for index, entry in enumerate(missing, start=1):
        destination = base / common.sanitize_relative_path(entry["relative"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            # 复用下载闭包，转存封禁的退避逻辑与主流程一致
            quark._download_entry_with_ban_backoff(
                opener, item["share_id"], inventory["stoken"],
                entry, destination, None)
            remaining += 1
        except Exception as unexpected:  # noqa: BLE001 - 单文件失败不中断补漏
            failed += 1
            print(f"  [{index}/{len(missing)}] 失败 {entry['relative'][-50:]}: "
                  f"{type(unexpected).__name__}: {unexpected}"[:160], flush=True)
        if index % 50 == 0:
            print(f"  进度 {index}/{len(missing)}", flush=True)

    print(f"{item_id}: 补下 {remaining} 个，失败 {failed} 个", flush=True)
    if failed:
        payload = {
            "item_id": item_id,
            "name": item.get("name"),
            "share_id": item.get("share_id"),
            "passcode": item.get("passcode") or "",
            "recorded_at": common.now_iso(),
            "missing": [entry["relative"] for entry in missing],
        }
        common.write_json_atomic(base / "_missing.json", payload)
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="补下未落盘文件")
    parser.add_argument("items", nargs="+", help="条目 id，如 p_math p_eng")
    parser.add_argument("--dry-run", action="store_true", help="只统计不下载")
    arguments = parser.parse_args(argv)
    code = 0
    for item_id in arguments.items:
        code |= backfill(item_id, arguments.dry_run)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
