#!/usr/bin/env python3
"""修复被误改名的网盘产物：从清单重建 `序号_标题` 形式的正确文件名。

背景：`migrate_netdisk_layout.py` 第一版把
`<分享标题>_01_1、【L5、6】（拉窗帘模型…）.mp4`
改成了 `1、【L5、6】（拉窗帘模型…）.mp4`（把 `_序号_` 当成前缀分隔符吞掉了）。
正确目标是 `01_1、【L5、6】（拉窗帘模型…）.mp4`。

本脚本拿线上清单（`walk_share`）做权威来源，按「标题部分」把磁盘上的错名
匹配回正确名：
  - 清单里的正确名 = 剥掉分享根目录后的 rel_path
  - 磁盘上的错名   = 正确名里 `_序号_` 之后的标题部分
体积一致才改名，避免张冠李戴。

用法：
    python scripts/repair_netdisk_names.py --dry-run
    python scripts/repair_netdisk_names.py
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from downloads import common, quark

# 两种形态：
#   A. `101_100、【L6】…`（正确名，`外序号_内序号、标题`）
#   B. `100、【L6】…`（被误改名后只剩内序号）
SEQUENCE_PREFIX = re.compile(r"^\d+_(\d+[、.].+)$")
LOOSE_PREFIX = re.compile(r"^(\d+[、.].+)$")


def title_key(name: str) -> str:
    """把文件名归一成「只含标题」的键，用于跨命名形态匹配。

    两种形态归一后必须相同：
      `101_100、【L6】（圆的运动问题).mp4` -> `L6圆的运动问题`
      `100、【L6】（圆的运动问题).mp4`     -> `L6圆的运动问题`

    注意别把 `1.1一一对应` 的 `1.1` 当成两个数字：
    `1.1` 本身是资料内的编号，属于标题的一部分，只剥掉第一段 `N、`/`N.`。
    """
    stem = pathlib.Path(name).stem
    match = SEQUENCE_PREFIX.match(stem)
    if match:
        stem = match.group(1)
    # 统一剥掉开头的 `数字、` 或 `数字.`，只留标题
    stem = re.sub(r"^\d+[、.]", "", stem)
    # 去掉分隔符与空白，只留文字与数字，抹平全角/半角括号差异
    return re.sub(r"[\s_、，,。.（）()【】\[\]、《》“”\"'：:]", "", stem)


def repair_item(item_dir: pathlib.Path, entries: list[dict], root: str,
                dry_run: bool) -> dict:
    by_key: dict[str, tuple[str, int]] = {}
    for entry in entries:
        relative = quark.relative_after_root(entry, root)
        name = pathlib.Path(relative).name
        by_key.setdefault(title_key(name), (name, int(entry.get("size") or 0)))

    renamed = unmatched = conflict = 0
    for path in sorted(item_dir.glob("*.mp4")):
        if SEQUENCE_PREFIX.match(path.stem):
            continue                      # 已是正确形态（`N_N、标题`）
        target = by_key.get(title_key(path.name))
        if target is None:
            unmatched += 1
            continue
        name, expected_size = target
        destination = item_dir / common.sanitize_segment(name, fallback="未命名")
        if destination.suffix.lower() != ".mp4":
            destination = destination.with_suffix(".mp4")
        if destination.exists():
            if destination.stat().st_size == path.stat().st_size:
                if not dry_run:
                    path.unlink()
                renamed += 1
            else:
                conflict += 1
            continue
        if expected_size and path.stat().st_size != expected_size:
            conflict += 1
            continue
        if not dry_run:
            path.replace(destination)
        renamed += 1
    return {"renamed": renamed, "unmatched": unmatched, "conflict": conflict}


def main() -> int:
    common.reconfigure_stdout()
    parser = argparse.ArgumentParser(description="按清单修复网盘文件名")
    parser.add_argument("--dry-run", action="store_true", help="只统计不改名")
    parser.add_argument("--share-id", default="668920790b03",
                        help="要修复的分享 id（默认范老师几何课）")
    parser.add_argument("--target", default="fan_geometry_900",
                        help="产物目录名前缀")
    arguments = parser.parse_args()

    cookie = common.read_credentials().get("NETDISK_QUARK_COOKIE", "")
    if not cookie:
        print("缺少 NETDISK_QUARK_COOKIE，无法取权威清单")
        return 1

    opener = quark._opener_with_cookie(cookie)
    inventory = quark.walk_share(arguments.share_id, "", None, opener=opener)
    entries = inventory["entries"]
    root = quark.share_root_prefix(entries)
    print(f"清单 {len(entries)} 条，分享根目录：{root[:40]}…")

    base = common.DOWNLOADS_ROOT / "netdisk" / "quark" / "小学"
    targets = [path for path in base.iterdir() if path.is_dir() and path.name.startswith(arguments.target)]
    if not targets:
        print(f"没找到以 {arguments.target} 开头的产物目录：{base}")
        return 1

    for item_dir in targets:
        result = repair_item(item_dir, entries, root, arguments.dry_run)
        print(f"[{'预演' if arguments.dry_run else '修复'}] {item_dir.name}: "
              f"改名 {result['renamed']} / 未匹配 {result['unmatched']} / 体积不符 {result['conflict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
