#!/usr/bin/env python3
"""把网盘旧命名产物迁移到新命名规则，避免重新下载几十 GB。

背景：早期版本的 `sanitize_relative_path` 把 `标题/子/file.mp4` 整段当成
一个路径段，`/` 被替换成 `_`，结果是
`<target_dir>/<分享标题>_<子路径>.mp4` 全部平铺在一层。
修复后正确产出 `<target_dir>/<子路径>/file.mp4`，但旧文件不在新位置上，
下载器会认为「缺失」而全部重下（实测已在重下 fan_geometry_900）。

本脚本按 `_inventory.json` 的 rel_path 建立「新旧路径」映射：
  - 旧路径 = 分享根目录剥除后，整段用 `_` 连接（旧实现的产物形态）
  - 新路径 = 剥根后逐段拆分
体积一致才 rename，不一致保留旧文件并报告（可能内容真的不同）。

用法：
    python scripts/migrate_netdisk_layout.py --dry-run   # 只看匹配情况
    python scripts/migrate_netdisk_layout.py             # 实际迁移
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from downloads import common, quark


def inventory_paths(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(root.rglob("_inventory.json"))


def legacy_name(relative_path: str, root_name: str) -> str:
    """旧实现产出的文件名：剥根后把整段路径的 `/` 换成 `_`。"""
    stripped = quark.relative_after_root({"rel_path": relative_path}, root_name)
    # 旧实现走的是 sanitize_segment，它把 `/` 换成 `_`，并把整体截到 120 字符
    return common.sanitize_segment(stripped)


def migrate_by_scan(item_dir: pathlib.Path, dry_run: bool) -> dict:
    """剥掉旧文件名里的分享标题前缀，保留剩余部分。

    旧实现的产物形态：
      `<分享标题>_01_1、【L5、6】（拉窗帘模型…）.mp4`
    新实现（剥根 + 逐段 sanitize）期望：
      `01_1、【L5、6】（拉窗帘模型…）.mp4`

    **不能像第一版那样按 `_数字_` 切分**：`01_1、` 里的 `_序号_`
    是原始文件名的一部分，切掉会让所有文件都变成「缺号」而被重下
    （实测 617 个文件被误改名，随后整批重下）。

    正确做法：以 `<分享标题>_` 为前缀，且分享标题本身以 `｜` 分隔出资料名
    —— 只剥这一层前缀。没有该前缀的文件原样保留。
    """
    # 分享标题的可靠特征：含 `｜`（全角竖线），且被 `_` 与剩余部分隔开
    prefix_pattern = re.compile(r"^[^_]*｜[^_]*_(.+)$")
    migrated = conflict = unknown = 0
    for path in sorted(item_dir.glob("*.mp4")):
        match = prefix_pattern.match(path.stem)
        if not match:
            unknown += 1
            continue
        target_stem = match.group(1)
        destination = item_dir / f"{common.sanitize_segment(target_stem)}.mp4"
        if destination == path:
            continue
        if destination.exists():
            if destination.stat().st_size == path.stat().st_size:
                if not dry_run:
                    path.unlink()
                migrated += 1
            else:
                conflict += 1
            continue
        if not dry_run:
            path.replace(destination)
        migrated += 1
    return {"migrated": migrated, "unknown": unknown, "conflict": conflict}


def migrate_one(item_dir: pathlib.Path, dry_run: bool) -> dict:
    inventory_file = item_dir / "_inventory.json"
    if not inventory_file.is_file():
        # 下载模式不写清单，退化为按文件名扫描
        result = migrate_by_scan(item_dir, dry_run)
        return {"migrated": result["migrated"], "missing": 0,
                "conflict": result["conflict"],
                "skipped": f"无清单，按文件名扫描（未识别 {result['unknown']}）"}

    payload = common.read_json(inventory_file, {})
    entries = payload.get("entries") or []
    if not entries:
        return {"migrated": 0, "missing": 0, "conflict": 0, "skipped": "empty inventory"}

    root_name = quark.share_root_prefix(entries)
    migrated = missing = conflict = 0
    for entry in entries:
        relative_path = str(entry.get("rel_path") or "")
        expected_size = int(entry.get("size") or 0)
        stripped = quark.relative_after_root(entry, root_name)
        destination = item_dir / common.sanitize_relative_path(stripped)
        if destination.is_file() and destination.stat().st_size == expected_size:
            continue

        candidates = [
            item_dir / legacy_name(relative_path, root_name),
            item_dir / common.sanitize_segment(relative_path),
        ]
        source = next((path for path in candidates if path.is_file()), None)
        if source is None:
            missing += 1
            continue
        if expected_size and source.stat().st_size != expected_size:
            conflict += 1
            continue
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
        migrated += 1

    return {"migrated": migrated, "missing": missing, "conflict": conflict, "skipped": ""}


def main() -> int:
    common.reconfigure_stdout()
    parser = argparse.ArgumentParser(description="迁移网盘产物到新命名规则")
    parser.add_argument("--dry-run", action="store_true", help="只统计不实际改名")
    parser.add_argument("--root", default=str(common.DOWNLOADS_ROOT / "netdisk"),
                        help="网盘产物根目录")
    arguments = parser.parse_args()

    root = pathlib.Path(arguments.root)
    if not root.is_dir():
        print(f"目录不存在：{root}")
        return 1

    totals = {"migrated": 0, "missing": 0, "conflict": 0}
    # 条目目录 = 含 mp4 或清单的目录；不能只看 _inventory.json，
    # 下载模式不写清单，产物目录里只有 mp4
    candidates = [
        path for path in root.rglob("*")
        if path.is_dir() and (
            (path / "_inventory.json").is_file()
            or any(child.suffix == ".mp4" for child in path.iterdir() if child.is_file())
        )
    ]
    if not candidates:
        print(f"在 {root} 下没找到含 mp4 的条目目录")
        return 0

    for item_dir in sorted(candidates):
        result = migrate_one(item_dir, arguments.dry_run)
        marker = f"（{result['skipped']}）" if result["skipped"] else ""
        print(f"[{'预演' if arguments.dry_run else '迁移'}] {item_dir.name}: "
              f"改名 {result['migrated']} / 缺失 {result['missing']} / "
              f"体积不符 {result['conflict']}{marker}")
        for key in totals:
            totals[key] += result[key]

    print(f"\n合计：改名 {totals['migrated']} / 缺失 {totals['missing']} / 体积不符 {totals['conflict']}")
    if arguments.dry_run:
        print("这是预演，未改动任何文件。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
