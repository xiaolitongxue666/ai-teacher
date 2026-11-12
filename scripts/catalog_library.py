#!/usr/bin/env python3
"""扫描 downloads/library/，写出 data/library_catalog.json。

一条记录是一个系列目录（课标是单个 PDF）。文件数和字节数只从磁盘来，
不要手改 JSON。

用法：
    python scripts/catalog_library.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from downloads import common, library_layout  # noqa: E402

CATALOG_PATH = common.REPO_ROOT / "data" / "library_catalog.json"
SPECIAL_ROLES = {"思维专题", "自然拼读", "幼小衔接", "词汇"}
_CURRICULUM_SUBJECTS = (
    "道德与法治", "思想政治", "信息科技", "信息技术", "通用技术", "生物学",
    "语文", "数学", "英语", "科学", "物理", "化学", "生物", "历史", "地理",
    "体育", "艺术", "劳动", "俄语", "日语", "政治", "音乐", "美术", "课程方案",
)


def main() -> int:
    common.reconfigure_stdout()
    root = common.DOWNLOADS_ROOT / library_layout.LIBRARY_DIRNAME
    if not root.is_dir():
        print(f"没有资料库目录：{root}")
        return 1
    grouped: dict[str, dict] = {}
    file_count = 0
    total_bytes = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        file_count += 1
        size = path.stat().st_size
        total_bytes += size
        relative = path.relative_to(root)
        key, described = _describe(relative)
        bucket = grouped.get(key)
        if bucket is None:
            bucket = {**described, "path": key, "files": 0, "bytes": 0}
            grouped[key] = bucket
        bucket["files"] += 1
        bucket["bytes"] += size

    series = sorted(grouped.values(), key=lambda item: item["path"])
    payload = {
        "generated_at": common.now_iso(),
        "root": "downloads/library",
        "files": file_count,
        "bytes": total_bytes,
        "series_count": len(series),
        "series": series,
    }
    common.write_json_atomic(CATALOG_PATH, payload)
    print(
        f"系列 {len(series)}  文件 {file_count}  "
        f"体积 {common.format_bytes(total_bytes)}  → {CATALOG_PATH}"
    )
    return 0


def _describe(relative: pathlib.Path) -> tuple[str, dict]:
    parts = relative.parts
    if parts[0] == "课标":
        filename = parts[-1]
        key = relative.as_posix()
        return key, {
            "stage": "课标",
            "subject": _curriculum_subject(filename),
            "edition": "",
            "grade": "",
            "volume": "",
            "role": "课标",
            "series": filename,
            "source_id": "j_curriculum",
        }
    if parts[0] == "_unsorted":
        source_id = parts[1] if len(parts) > 1 else ""
        key = pathlib.Path("_unsorted", source_id).as_posix() if source_id else "_unsorted"
        return key, _blank(source_id)
    if len(parts) >= 5 and parts[2] == "通用" and parts[3] in SPECIAL_ROLES:
        key = pathlib.Path(*parts[:5]).as_posix()
        return key, {
            "stage": "小学",
            "subject": parts[1],
            "edition": "通用",
            "grade": "",
            "volume": "",
            "role": parts[3],
            "series": parts[4],
            "source_id": _source_id(parts),
        }
    if len(parts) < 7:
        key = relative.parent.as_posix()
        return key, _blank("")
    key = pathlib.Path(*parts[:7]).as_posix()
    grade = "" if parts[3] == "跨年级" else parts[3]
    return key, {
        "stage": parts[0],
        "subject": parts[1],
        "edition": parts[2],
        "grade": grade,
        "volume": "" if parts[4] == "全册" else parts[4],
        "role": parts[5],
        "series": parts[6],
        "source_id": _source_id(parts),
    }


def _blank(source_id: str) -> dict:
    return {
        "stage": "", "subject": "", "edition": "", "grade": "", "volume": "",
        "role": "", "series": "", "source_id": source_id,
    }


def _source_id(parts: tuple[str, ...]) -> str:
    if "同步课" in parts:
        index = parts.index("同步课")
        if index + 1 < len(parts):
            return parts[index + 1]
    if len(parts) > 3 and parts[2] == "通用":
        role = parts[3]
        if role == "思维专题":
            return "fan_geometry_900"
        if role in {"自然拼读", "幼小衔接"}:
            return "phonics_270"
        if role == "词汇":
            return "primary_1000_words"
    subject = parts[1] if len(parts) > 1 else ""
    return {
        "语文": "p_chn",
        "数学": "p_math",
        "英语": "p_eng",
        "道法": "p_morality",
        "科学": "p_sci",
    }.get(subject, "")


def _curriculum_subject(filename: str) -> str:
    for name in _CURRICULUM_SUBJECTS:
        if name in filename:
            return "道法" if name == "道德与法治" else name
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
