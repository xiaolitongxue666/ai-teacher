"""统计各网盘条目的完成度：已落盘且体积一致的文件数 / 总体积。"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from downloads import common  # noqa: E402


def main() -> int:
    base = common.DOWNLOADS_ROOT / "netdisk" / "quark" / "小学"
    total_done = 0
    total_all = 0
    rows = []
    for inventory in sorted(base.glob("*/_inventory.json")):
        payload = json.loads(inventory.read_text(encoding="utf-8"))
        target = inventory.parent
        done = 0
        done_bytes = 0
        for entry in payload["entries"]:
            path = target / common.sanitize_relative_path(entry["rel_path"])
            if path.is_file() and path.stat().st_size == entry["size"]:
                done += 1
                done_bytes += entry["size"]
        total_done += done_bytes
        total_all += payload["bytes"]
        rows.append((payload["item_id"], done, payload["files"],
                     done_bytes, payload["bytes"]))
    print(f"{'item':24} {'完成':>9} {'已下':>12} {'总量':>12} {'进度':>7}")
    for item_id, done, files, done_bytes, all_bytes in rows:
        ratio = done_bytes / all_bytes * 100 if all_bytes else 0
        print(f"{item_id:24} {done:>4}/{files:<5}{common.format_bytes(done_bytes):>12} "
              f"{common.format_bytes(all_bytes):>12} {ratio:>6.1f}%")
    ratio = total_done / total_all * 100 if total_all else 0
    print(f"\n合计 {common.format_bytes(total_done)} / {common.format_bytes(total_all)} "
          f"= {ratio:.1f}%  未完成 {common.format_bytes(total_all - total_done)}")
    print(f"磁盘剩余 {common.format_bytes(common.free_bytes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
