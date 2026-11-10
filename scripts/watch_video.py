#!/usr/bin/env python3
"""视频下载的旁观式进度采集。

为什么需要这个脚本：
  视频阶段可能由「上一轮会话启动的进程」在跑，那个进程用的是当时的代码，
  不一定写 progress.video.json。此时 `fetch_resources.py status` 看不到视频进度，
  轮询方只能看到 GitHub 与网盘两个阶段。

  本脚本不去干预下载进程，只按磁盘实际文件数合成一份符合既有 schema 的
  progress.video.json，让 status / report 重新能如实反映视频进度。

用法（后台起，别占前台）：
    python scripts/watch_video.py

退出条件：累计 1994 P 下完，或连续 40 次（约 200 分钟）没有新增。
"""

from __future__ import annotations

import datetime as dt
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from downloads import bilibili, common

# 采样间隔（秒）。5 分钟足够，视频每 P 约 20 秒，粒度不会太粗。
SAMPLE_INTERVAL_SECONDS = 300
# 连续多少次无增量判定停滞（40 × 5 分钟 = 200 分钟）
STALL_SAMPLES = 40


def snapshot() -> tuple[int, dict[str, int]]:
    """数每个合集目录下的 mp4 数量，返回 (总数, {相对路径: 数量})。"""
    root = common.DOWNLOADS_ROOT / "videos" / "bilibili" / "小学"
    per_dir: dict[str, int] = {}
    if root.is_dir():
        for directory in root.glob("*/*/"):
            label = f"{directory.parent.name}/{directory.name}"
            per_dir[label] = len(list(directory.glob("*.mp4")))
    return sum(per_dir.values()), per_dir


def write_progress(total_done: int, planned_total: int, planned_pages: int,
                   per_dir: dict[str, int], finished: bool = False) -> None:
    """写 progress.video.json。字段与 common.Progress 保持一致。"""
    now = common.now_iso()
    payload = {
        "stage": "video",
        "item_done": sum(1 for item in bilibili.plan_videos() if _is_complete(item, per_dir)),
        "item_total": planned_total,
        "page_done": total_done,
        "page_total": planned_pages,
        "bytes_done": _videos_bytes(),
        "eta_minutes": None,
        "last_error": "",
        "started_at": common.read_json(common.STATE_DIR / "progress.video.json", {}).get("started_at") or now,
        "updated_at": now,
        "finished": finished,
        "current": "由 watch_video.py 旁路采集（下载进程未写进度）",
        "note": "旁观式采集：数据来自磁盘文件计数，不是下载进程自报",
        "per_collection": per_dir,
    }
    common.write_json_atomic(common.STATE_DIR / "progress.video.json", payload)


def _is_complete(item: dict, per_dir: dict[str, int]) -> bool:
    """判断某个合集是否已下满。用目录名末两段匹配 per_dir 的键。"""
    target = pathlib.Path(item["target_dir"])
    label = f"{target.parent.name}/{target.name}"
    return per_dir.get(label, 0) >= item["pages"] > 0


def _videos_bytes() -> int:
    root = common.DOWNLOADS_ROOT / "videos"
    total = 0
    for path in root.rglob("*.mp4"):
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def main() -> int:
    common.reconfigure_stdout()
    planned = bilibili.plan_videos(only_core=True)
    planned_total = len(planned)
    planned_pages = sum(item["pages"] for item in planned)

    previous = -1
    stalled = 0
    while True:
        total_done, per_dir = snapshot()
        finished = total_done >= planned_pages > 0
        write_progress(total_done, planned_total, planned_pages, per_dir, finished)
        print(f"{dt.datetime.now():%H:%M:%S} 视频 {total_done}/{planned_pages} P", flush=True)

        if finished:
            print("全部合集已下满", flush=True)
            return 0
        stalled = stalled + 1 if total_done == previous else 0
        if stalled >= STALL_SAMPLES:
            print(f"连续 {STALL_SAMPLES} 次采样无增量，判定停滞", flush=True)
            return 1
        previous = total_done
        time.sleep(SAMPLE_INTERVAL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
