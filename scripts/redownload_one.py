"""单独补下夸克分享里的指定文件，不动正在跑的整体阶段。

用途：整体阶段对单文件失败只记 last_error 并继续下一个，跑完后这些文件就
永久缺失。这里复用阶段内的同一套接口（token -> detail 取 fid -> 转存 -> 直链
-> 分片下载 -> 删转存件），只针对一个文件重试。

用法：
    python scripts/redownload_one.py <item_id> <rel_path_after_root>
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from downloads import common, library_layout, quark  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] in {"-h", "--help"}:
        # 显式 --help 属于正常请求，返回 0。早期把「参数个数不对」一律返回 2，
        # 导致 --help 也被当成错误，用脚本化探测时会误判成导入失败。
        print(__doc__)
        return 0
    if len(argv) != 3:
        print(__doc__)
        return 2
    item_id, wanted = argv[1], argv[2]

    planned = {item["id"]: item for item in quark.plan_netdisk()}
    item = planned.get(item_id)
    if not item or not item.get("share_id"):
        print(f"条目不可用：{item_id}")
        return 1

    cookie = common.read_credentials().get("NETDISK_QUARK_COOKIE", "")
    logged_in, note = quark.login_state(cookie)
    print("LOGIN", logged_in, note[:60])
    if not logged_in:
        return 1

    opener = quark._opener_with_cookie(cookie)
    inventory = quark.walk_share(item["share_id"], item["passcode"], None,
                                 opener=opener)
    root_prefix = quark.share_root_prefix(inventory["entries"])
    matches = [
        entry for entry in inventory["entries"]
        if quark.relative_after_root(entry, root_prefix).replace("\\", "/") == wanted
    ]
    print("SHARE_FILES", len(inventory["entries"]), "MATCHES", len(matches))
    if not matches:
        for entry in inventory["entries"]:
            rel = quark.relative_after_root(entry, root_prefix).replace("\\", "/")
            if pathlib.PurePath(rel).name == pathlib.PurePath(wanted).name:
                print("NEAR", rel)
        return 1

    entry = matches[0]
    target = library_layout.destination_for(item_id, wanted)
    print("TARGET", target)
    print("EXPECTED_MB", round(int(entry["size"]) / 1024 ** 2, 2))
    target.parent.mkdir(parents=True, exist_ok=True)

    quark.download_entry(opener, item["share_id"], inventory["stoken"], entry,
                         target, None)
    written = target.stat().st_size if target.is_file() else 0
    print("WRITTEN_MB", round(written / 1024 ** 2, 2))
    print("SIZE_OK", written == int(entry["size"]))
    return 0 if written == int(entry["size"]) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
