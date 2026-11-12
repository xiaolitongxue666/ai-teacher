"""把分享已不存在的旧命名文件移到 _legacy/，让新分享按新结构干净下载。

背景：该夸克分享被分享方整体重命名过（旧名 `100、【L6】（圆的运动问题).mp4`，
新名 `101_100、【L6】（圆的运动问题).mp4` 这种「新序号_原序号、」形式），
但绝大多数是全新条目，磁盘上 617 个旧名文件在新分享里一个都找不到。
这些文件本身仍有效，所以搬到 `_legacy/` 保留，而不是删除。

同时把能对上的（归一名字 + 体积一致）直接改名复用，省一次下载。
"""
from __future__ import annotations

import collections
import re
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from downloads import common, library_layout, quark  # noqa: E402

PREFIX_PATTERN = re.compile(r"^\d+_\d+[、.]")
LEGACY_DIRNAME = "_legacy"


def normalize(name: str) -> str:
    stripped = PREFIX_PATTERN.sub("", name)
    return stripped or name


def main() -> int:
    apply_changes = "--apply" in sys.argv
    item = {planned["id"]: planned for planned in quark.plan_netdisk()}["fan_geometry_900"]
    target = quark.target_dir_for(item)
    opener = quark._opener_with_cookie(common.read_credentials()["NETDISK_QUARK_COOKIE"])
    inventory = quark.walk_share(item["share_id"], item["passcode"], opener=opener)
    entries = inventory["entries"]
    # 必须用下载器的同一套路径计算：它会剥掉分享里那层长标题目录，
    # 直接用 rel_path 会把文件搬到 `<长标题>/文件名` 这种错位置。
    share_root = quark.share_root_prefix(entries)

    legacy_root = target / LEGACY_DIRNAME
    disk_files = [path for path in target.rglob("*")
                  if path.is_file()
                  and not path.name.endswith(".part")
                  and legacy_root not in path.parents]

    wanted: dict[tuple[str, int], list[pathlib.Path]] = collections.defaultdict(list)
    for entry in entries:
        relative = quark.relative_after_root(entry, share_root)
        destination = library_layout.destination_for(item["id"], relative)
        wanted[(destination.name, entry["size"])].append(destination)

    reusable = []
    leftovers = []
    for path in disk_files:
        key = (path.name, path.stat().st_size)
        candidates = wanted.get(key) or []
        if candidates:
            destination = candidates.pop(0)
            if path != destination:
                reusable.append((path, destination))
        else:
            leftovers.append(path)

    print(f"分享 {len(entries)} 个；磁盘待整理 {len(disk_files)} 个")
    print(f"  可改名对齐: {len(reusable)}")
    print(f"  旧命名归档: {len(leftovers)}")
    if not apply_changes:
        for source, destination in reusable[:4]:
            print(f"  复用 {source.relative_to(target)}")
            print(f"    -> {destination.relative_to(target)}")
        for path in leftovers[:4]:
            print(f"  归档 {path.name[:52]}")
        print("\n（预览模式，加 --apply 执行）")
        return 0

    for source, destination in reusable:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            source.replace(destination)
        else:
            # 目标已存在同体积文件，源是重复副本
            source.unlink()

    moved = 0
    for path in leftovers:
        if not path.exists():
            continue
        destination = legacy_root / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = path
        suffix = 1
        while destination.exists():
            destination = legacy_root / f"{path.stem}({suffix}){path.suffix}"
            suffix += 1
        source.replace(destination)
        moved += 1

    for directory in sorted(target.rglob("*"), key=lambda p: -len(p.parts)):
        if directory.is_dir() and directory != legacy_root and not any(directory.iterdir()):
            directory.rmdir()

    print(f"\n已对齐 {len(reusable)} 个，归档 {moved} 个到 {LEGACY_DIRNAME}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
