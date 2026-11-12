#!/usr/bin/env python3
"""把已落盘的网盘教辅和 B 站同步课搬进 downloads/library/。

默认只预览。两条闸门没过就拒绝 --apply：

- 未分类占比超过 5%（路径规则还没覆盖这批文件）
- 两个不同文件落到同一路径（无论字节是否相同，后写的都会盖掉先写的）

预览结果写到 downloads/_state/library_move_plan.json。同一次运行里
--apply 会先按同样的规则重算，不单独相信上次写下的计划文件。

用法：
    python scripts/migrate_library.py
    python scripts/migrate_library.py --apply
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from downloads import bilibili, common, library_layout  # noqa: E402

UNSORTED_RATIO_LIMIT = 0.05
# 260 是 MAX_PATH 含结尾 NUL 的上限。超过 250 的路径在不启用长路径时会失败。
PATH_LENGTH_LIMIT = 250
SKIP_NAMES = {"_inventory.json", "_missing.json", "desktop.ini", "Thumbs.db"}


def main(argv: list[str] | None = None) -> int:
    common.reconfigure_stdout()
    arguments = argv if argv is not None else sys.argv[1:]
    apply_changes = "--apply" in arguments
    moves, summary = build_plan()
    _print_summary(summary)
    plan_path = common.STATE_DIR / "library_move_plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    common.write_json_atomic(plan_path, {"summary": summary, "moves": moves})
    print(f"计划已写入 {plan_path}")

    blocked = _gate(summary)
    if blocked:
        for reason in blocked:
            print(f"停住：{reason}")
        return 1
    if not apply_changes:
        print("预览模式。确认闸门通过后加 --apply 执行搬迁。")
        return 0
    return apply_moves(moves)


def build_plan() -> tuple[list[dict], dict]:
    moves = list(_iter_moves())
    by_dest: dict[str, list[dict]] = {}
    for move in moves:
        by_dest.setdefault(move["dest"], []).append(move)

    conflicts = []
    duplicates = []
    for dest, group in by_dest.items():
        if len(group) < 2:
            continue
        sizes = {item["bytes"] for item in group}
        record = {
            "dest": dest,
            "sources": [item["src"] for item in group],
            "sizes": [item["bytes"] for item in group],
        }
        if len(sizes) > 1:
            conflicts.append(record)
        else:
            duplicates.append(record)

    long_paths = [move["dest"] for move in moves if len(move["dest"]) >= PATH_LENGTH_LIMIT]
    unsorted = [move for move in moves if move["unsorted"]]
    slot_counts: dict[str, int] = {}
    other_series: dict[str, int] = {}
    for move in moves:
        slot_counts[move["slot"]] = slot_counts.get(move["slot"], 0) + 1
        if move["role"] == "其他":
            other_series[move["series"]] = other_series.get(move["series"], 0) + 1

    file_count = len(moves)
    summary = {
        "files": file_count,
        "bytes": sum(move["bytes"] for move in moves),
        "unsorted": len(unsorted),
        "unsorted_ratio": (len(unsorted) / file_count) if file_count else 0,
        "conflicts": len(conflicts),
        "conflict_samples": conflicts[:20],
        "duplicates": len(duplicates),
        "duplicate_samples": duplicates[:10],
        "long_paths": len(long_paths),
        "long_path_samples": long_paths[:10],
        "unsorted_samples": [move["src"] for move in unsorted[:20]],
        "by_slot": dict(sorted(slot_counts.items(), key=lambda item: (-item[1], item[0]))),
        "other_series": dict(sorted(other_series.items(), key=lambda item: (-item[1], item[0]))[:40]),
    }
    return moves, summary


def apply_moves(moves: list[dict]) -> int:
    moved = 0
    skipped = 0
    failed: list[str] = []
    for index, move in enumerate(moves, start=1):
        source = pathlib.Path(move["src"])
        destination = pathlib.Path(move["dest"])
        try:
            if source.resolve() == destination.resolve():
                skipped += 1
            elif not source.is_file():
                if destination.is_file() and destination.stat().st_size == move["bytes"]:
                    skipped += 1
                else:
                    failed.append(f"源文件不在：{source}")
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.is_file():
                    if destination.stat().st_size == source.stat().st_size == move["bytes"]:
                        # 分享里同一份文件挂在两个目录下。目标已经就位，删掉这份重复源。
                        source.unlink()
                        skipped += 1
                    else:
                        failed.append(f"目标已存在且大小不同：{destination}")
                        continue
                else:
                    source.replace(destination)
                    moved += 1
        except OSError as error:
            failed.append(f"{source} -> {destination}: {error}")
        if index % 1000 == 0:
            print(f"进度 {index}/{len(moves)} 已搬 {moved}", flush=True)

    removed = _remove_empty_dirs()
    print(f"搬迁完成：移动 {moved}，已在目标 {skipped}，失败 {len(failed)}，删除空目录 {removed}")
    for line in failed[:20]:
        print(f"  {line}")
    return 1 if failed else 0


def _iter_moves():
    yield from _iter_netdisk()
    yield from _iter_videos()


def _iter_netdisk():
    root = common.DOWNLOADS_ROOT / "netdisk" / "quark" / "小学"
    if not root.is_dir():
        return
    for pack in sorted(path for path in root.iterdir() if path.is_dir()):
        source_id = pack.name.split("__", 1)[0]
        for path in pack.rglob("*"):
            if not path.is_file() or path.name in SKIP_NAMES or path.suffix == ".part":
                continue
            relative = path.relative_to(pack).as_posix()
            yield _move_record(path, source_id, relative)


def _iter_videos():
    root = common.DOWNLOADS_ROOT / "videos" / "bilibili" / "小学"
    if not root.is_dir():
        return
    index = _video_index()
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() != ".mp4":
            continue
        parts = path.relative_to(root).parts
        if len(parts) < 3:
            yield _move_record(path, "video_unmapped", path.name)
            continue
        subject_edition, grade_volume = parts[0], parts[1]
        if "-" not in subject_edition or "-" not in grade_volume:
            yield _move_record(path, "video_unmapped", path.name)
            continue
        subject, edition = subject_edition.split("-", 1)
        grade, volume = grade_volume.split("-", 1)
        source_id = index.get((subject, edition, grade, volume), "")
        if not source_id:
            yield _move_record(path, "video_unmapped", "/".join(parts))
            continue
        # 只把文件名放进同步课目录。旧的「学科-版本/年级-册」不再嵌一层。
        yield _move_record(path, source_id, path.name)


def _video_index() -> dict[tuple[str, str, str, str], str]:
    resources = common.load_resources()
    index: dict[tuple[str, str, str, str], str] = {}
    for record in resources.get("videos", []):
        if record.get("platform") != "bilibili":
            continue
        item_id = str(record.get("id") or "")
        key = (
            str(record.get("subject") or ""),
            bilibili.edition_of(item_id),
            str(record.get("grade") or ""),
            str(record.get("volume") or ""),
        )
        index[key] = item_id
    return index


def _move_record(path: pathlib.Path, source_id: str, relative: str) -> dict:
    placed = library_layout.place(source_id, relative)
    destination = common.DOWNLOADS_ROOT / library_layout.LIBRARY_DIRNAME / placed.relative
    slot = "/".join(
        part for part in (
            placed.stage, placed.subject, placed.edition,
            placed.grade or "跨年级", placed.volume or "全册", placed.role,
        ) if part
    )
    if placed.edition == "通用" and placed.role in {"思维专题", "自然拼读", "幼小衔接", "词汇"}:
        slot = "/".join((placed.stage, placed.subject, placed.edition, placed.role))
    return {
        "src": str(path),
        "dest": str(destination),
        "bytes": path.stat().st_size,
        "source_id": source_id,
        "unsorted": placed.unsorted,
        "slot": slot,
        "role": placed.role,
        "series": placed.series,
        "series_relative": placed.series_relative.as_posix(),
    }


def _gate(summary: dict) -> list[str]:
    reasons = []
    if summary["unsorted_ratio"] > UNSORTED_RATIO_LIMIT:
        reasons.append(
            f"未分类 {summary['unsorted']}/{summary['files']} "
            f"= {summary['unsorted_ratio']:.1%}，超过 {UNSORTED_RATIO_LIMIT:.0%}"
        )
    if summary["conflicts"]:
        reasons.append(f"目标路径冲突 {summary['conflicts']} 处")
    if summary["long_paths"]:
        reasons.append(f"路径长度达到 {PATH_LENGTH_LIMIT} 的有 {summary['long_paths']} 条")
    return reasons


def _print_summary(summary: dict) -> None:
    print(
        f"文件 {summary['files']}  体积 {common.format_bytes(summary['bytes'])}  "
        f"未分类 {summary['unsorted']} ({summary['unsorted_ratio']:.1%})  "
        f"冲突 {summary['conflicts']}  重复 {summary['duplicates']}  超长 {summary['long_paths']}"
    )
    print("槽位（前 25）：")
    for slot, count in list(summary["by_slot"].items())[:25]:
        print(f"  {count:5}  {slot}")
    if summary["other_series"]:
        print("用途未定的系列（前 20）：")
        for series, count in list(summary["other_series"].items())[:20]:
            print(f"  {count:5}  {series}")
    if summary["unsorted_samples"]:
        print("未分类样例：")
        for sample in summary["unsorted_samples"][:8]:
            print(f"  {sample}")
    if summary["conflict_samples"]:
        print("冲突样例：")
        for sample in summary["conflict_samples"][:5]:
            print(f"  {sample['dest']}")
            for source in sample["sources"][:3]:
                print(f"    <- {source}")


def _remove_empty_dirs() -> int:
    removed = 0
    roots = [
        common.DOWNLOADS_ROOT / "netdisk" / "quark" / "小学",
        common.DOWNLOADS_ROOT / "videos" / "bilibili" / "小学",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for directory in sorted(root.rglob("*"), key=lambda path: len(path.parts), reverse=True):
            if not directory.is_dir():
                continue
            try:
                directory.rmdir()
                removed += 1
            except OSError:
                continue
        try:
            root.rmdir()
            removed += 1
        except OSError:
            continue
    return removed


if __name__ == "__main__":
    raise SystemExit(main())
