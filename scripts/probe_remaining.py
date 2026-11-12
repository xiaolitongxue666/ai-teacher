"""只读探测条目的文件数与总体积，用于估算剩余下载量。

只调用 sharepage/token 与 sharepage/detail，不做 save，因此不会转存、
不占网盘容量、不触发转存风控。

默认探测「还没下完」的条目：按 `data/resources.json` 的 `share_total_size_bytes`
与落盘体积对比，缺任何文件的都算在内。也可以显式点名。

用法：
    python scripts/probe_remaining.py                  # 自动挑出未完成的条目
    python scripts/probe_remaining.py p_sci            # 只测指定条目
    python scripts/probe_remaining.py --all            # 全部 9 条都测
    python scripts/probe_remaining.py -h               # 只看用法，不发请求
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from downloads import common, library_layout, quark  # noqa: E402


def _landed_bytes(item: dict, entries: list[dict] | None = None) -> int:
    """该条目已落盘体积。

    有分享清单时按课程槽位逐个对路径，不按旧的包目录求和——文件已经不在
    `<id>__标题/` 下面。不排除 `_` 前缀：网盘里有 `_5 3全优卷….zip` 这种真文件。
    """
    if not entries:
        target = quark.target_dir_for(item)
        if not target.is_dir():
            return 0
        return sum(path.stat().st_size for path in target.rglob("*") if path.is_file())
    root_prefix = quark.share_root_prefix(entries)
    total = 0
    for entry in entries:
        relative = quark.relative_after_root(entry, root_prefix)
        destination = library_layout.destination_for(str(item.get("id") or ""), relative)
        if destination.is_file():
            total += destination.stat().st_size
    return total


def _unfinished_ids(items: list[dict]) -> list[str]:
    """挑出还没下完的条目。

    判据用 `_manifest.jsonl` 里该条目**最后一条**记录的 status 与 failed，
    不用 `data/resources.json` 的 `share_total_size_bytes`：后者只有 4 条
    分享写了体积，其余为 0，拿它比对会把已完成的条目全判成未完成（实测）。

    `incomplete` / `failed` / `unavailable` 都算未完成；`ok` 且 `failed == 0`
    算完成。目录里存在 `_missing.json` 的也视为未完成（那是补漏清单）。
    """
    manifest_path = common.DOWNLOADS_ROOT / "netdisk" / "_manifest.jsonl"
    latest: dict[str, dict] = {}
    if manifest_path.is_file():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            item_id = str(record.get("id") or "")
            if item_id:
                latest[item_id] = record  # 后出现的覆盖前面的，即取最后一条

    unfinished = []
    for item in items:
        item_id = item["id"]
        if not item.get("share_id"):
            continue
        record = latest.get(item_id)
        target = quark.target_dir_for(item)
        if (target / "_missing.json").is_file():
            unfinished.append(item_id)
            continue
        if record is None:
            unfinished.append(item_id)
            continue
        if record.get("status") != "ok" or int(record.get("failed") or 0) > 0:
            unfinished.append(item_id)
    return unfinished


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="只读探测条目的文件数与体积（不转存、不占容量）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("items", nargs="*", help="条目 id；省略则自动挑出未完成的")
    parser.add_argument("--all", action="store_true", help="探测全部条目")
    arguments = parser.parse_args(argv)

    planned = {item["id"]: item for item in quark.plan_netdisk()}
    if arguments.all:
        wanted = [item_id for item_id, item in planned.items() if item.get("share_id")]
    elif arguments.items:
        wanted = list(arguments.items)
    else:
        wanted = _unfinished_ids(list(planned.values()))
    if not wanted:
        print("没有未完成的条目")
        return 0
    print(f"探测 {len(wanted)} 条：{', '.join(wanted)}", flush=True)

    out: list[dict] = []
    for item_id in wanted:
        item = planned.get(item_id)
        if not item or not item.get("share_id"):
            out.append({"id": item_id, "status": "no_share"})
            print(f"{item_id}: 无夸克源", flush=True)
            continue
        started = time.monotonic()
        try:
            inventory = quark.walk_share(item["share_id"], item["passcode"], None)
        except Exception as unexpected:  # noqa: BLE001 - 单条失败不中断其余
            out.append({"id": item_id, "status": "error",
                        "error": f"{type(unexpected).__name__}: {unexpected}"[:120]})
            print(f"{item_id}: ERROR {unexpected}", flush=True)
            continue
        record = {
            "id": item_id,
            "status": "ok",
            "files": len(inventory["entries"]),
            "bytes": inventory["bytes"],
            "landed_bytes": _landed_bytes(item, inventory["entries"]),
            "truncated": inventory["truncated"],
            "elapsed_seconds": round(time.monotonic() - started, 1),
        }
        out.append(record)
        remaining = record["bytes"] - record["landed_bytes"]
        print(f"{item_id}: files={record['files']} "
              f"gb={record['bytes'] / 1024 ** 3:.2f} "
              f"remaining_gb={max(remaining, 0) / 1024 ** 3:.2f} "
              f"truncated={record['truncated']} "
              f"walk={record['elapsed_seconds']}s", flush=True)

    total_bytes = sum(int(r.get("bytes") or 0) for r in out)
    total_files = sum(int(r.get("files") or 0) for r in out)
    total_remaining = sum(max(int(r.get("bytes") or 0) - int(r.get("landed_bytes") or 0), 0)
                          for r in out)
    payload = {"probed_at": common.now_iso(), "items": out,
               "total_files": total_files, "total_bytes": total_bytes,
               "total_remaining_bytes": total_remaining}
    common.write_json_atomic(common.STATE_DIR / "remaining_estimate.json", payload)
    print(f"TOTAL files={total_files} gb={total_bytes / 1024 ** 3:.2f} "
          f"remaining_gb={total_remaining / 1024 ** 3:.2f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
