"""只读探测剩余条目的文件数与总体积，用于估算剩余下载时长。

只调用 sharepage/token 与 sharepage/detail，不做 save，因此不会转存、
不占网盘容量、不触发转存风控。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from downloads import common, quark  # noqa: E402

REMAINING = ["p_eng", "p_morality", "p_sci", "j_curriculum"]


def main() -> int:
    planned = {item["id"]: item for item in quark.plan_netdisk()}
    out: list[dict] = []
    for item_id in REMAINING:
        item = planned.get(item_id)
        if not item or not item.get("share_id"):
            out.append({"id": item_id, "status": "no_share"})
            print(f"{item_id}: no share", flush=True)
            continue
        started = time.monotonic()
        try:
            inventory = quark.walk_share(item["share_id"], item["passcode"], None)
        except Exception as unexpected:  # noqa: BLE001
            out.append({"id": item_id, "status": "error",
                        "error": f"{type(unexpected).__name__}: {unexpected}"[:120]})
            print(f"{item_id}: ERROR {unexpected}", flush=True)
            continue
        record = {
            "id": item_id,
            "status": "ok",
            "files": len(inventory["entries"]),
            "bytes": inventory["bytes"],
            "truncated": inventory["truncated"],
            "elapsed_seconds": round(time.monotonic() - started, 1),
        }
        out.append(record)
        print(f"{item_id}: files={record['files']} "
              f"gb={record['bytes'] / 1024 ** 3:.2f} "
              f"truncated={record['truncated']} "
              f"walk={record['elapsed_seconds']}s", flush=True)

    total_bytes = sum(int(r.get("bytes") or 0) for r in out)
    total_files = sum(int(r.get("files") or 0) for r in out)
    payload = {"probed_at": common.now_iso(), "items": out,
               "total_files": total_files, "total_bytes": total_bytes}
    path = common.STATE_DIR / "remaining_estimate.json"
    common.write_json_atomic(path, payload)
    print(f"TOTAL files={total_files} gb={total_bytes / 1024 ** 3:.2f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
