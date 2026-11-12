#!/usr/bin/env python3
"""按学科、版本、年级、册次查本地资料库。

读 data/library_catalog.json。年级范围（如「一至六年级」）和未分册的
「跨年级」会算进所问的那一册；上册不会混进下册。

用法：
    python scripts/catalog_library.py
    python scripts/library_query.py --subject 英语 --edition 人教版 --grade 三年级 --volume 下册
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from downloads import common  # noqa: E402

CATALOG_PATH = common.REPO_ROOT / "data" / "library_catalog.json"
_CN = "一二三四五六"
_RANGE = re.compile(r"([一二三四五六])至([一二三四五六])年级")


def main(argv: list[str] | None = None) -> int:
    common.reconfigure_stdout()
    parser = argparse.ArgumentParser(description="按课程槽位查询本地资料库")
    parser.add_argument("--subject", default="", help="学科，如 英语")
    parser.add_argument("--edition", default="", help="版本，如 人教版")
    parser.add_argument("--grade", default="", help="年级，如 三年级")
    parser.add_argument("--volume", default="", help="册次：上册 或 下册")
    parser.add_argument("--role", default="", help="用途，如 同步课")
    arguments = parser.parse_args(argv)

    if not CATALOG_PATH.is_file():
        print("还没有目录。先跑：python scripts/catalog_library.py")
        return 1
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    matched = [
        record for record in payload.get("series", [])
        if _matches(record, arguments)
    ]
    if not matched:
        print("没有对上的系列。")
        return 0

    matched.sort(key=lambda record: (
        record.get("role") or "",
        record.get("grade") or "",
        record.get("volume") or "",
        record.get("series") or "",
    ))
    total_files = sum(int(record.get("files") or 0) for record in matched)
    total_bytes = sum(int(record.get("bytes") or 0) for record in matched)
    print(
        f"{len(matched)} 个系列  {total_files} 个文件  "
        f"{common.format_bytes(total_bytes)}  "
        f"（目录生成于 {payload.get('generated_at', '')}）"
    )
    for record in matched:
        grade = record.get("grade") or "不限年级"
        volume = record.get("volume") or "不限册"
        print(
            f"{record.get('role') or '其他':<6}  {record.get('edition') or '通用'}  "
            f"{grade}{volume}  {record.get('files')} 个  "
            f"{common.format_bytes(int(record.get('bytes') or 0)):>10}  "
            f"downloads/library/{record.get('path')}"
        )
    return 0


def _matches(record: dict, arguments: argparse.Namespace) -> bool:
    if arguments.subject and record.get("subject") != arguments.subject:
        return False
    if arguments.edition and record.get("edition") != arguments.edition:
        return False
    if arguments.role and record.get("role") != arguments.role:
        return False
    if not _grade_covers(str(record.get("grade") or ""), arguments.grade):
        return False
    if not _volume_covers(str(record.get("volume") or ""), arguments.volume):
        return False
    return True


def _grade_covers(slot: str, wanted: str) -> bool:
    if not wanted:
        return True
    if slot == wanted or slot == "":
        return True
    ranged = _RANGE.match(slot)
    if not ranged or not wanted.endswith("年级"):
        return False
    left = _CN.find(ranged.group(1))
    right = _CN.find(ranged.group(2))
    middle = _CN.find(wanted[0])
    if min(left, right, middle) < 0:
        return False
    return left <= middle <= right


def _volume_covers(slot: str, wanted: str) -> bool:
    if not wanted:
        return True
    if slot == wanted or slot in {"", "上下册"}:
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
