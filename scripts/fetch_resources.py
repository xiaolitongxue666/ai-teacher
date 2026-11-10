#!/usr/bin/env python3
"""三类资源统一下载的入口。

实现都在 scripts/downloads/ 里，这里只做路径注入与转发 ——
放在 scripts/ 顶层是为了让它和 check_links.py、download_video.py 处于同一层，
调用方式一致，不用记包路径。

用法：
    python scripts/fetch_resources.py plan
    python scripts/fetch_resources.py run --only video
    python scripts/fetch_resources.py status
    python scripts/fetch_resources.py report

长任务请后台起，再轮询 status：
    nohup python -X utf8 scripts/fetch_resources.py run --only video \
        > downloads/_state/run.log 2>&1 &
"""

from __future__ import annotations

import pathlib
import sys

# 让 `python scripts/fetch_resources.py` 能找到同级的 downloads 包
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from downloads import cli  # noqa: E402 - 必须先插入 sys.path

if __name__ == "__main__":
    raise SystemExit(cli.main())
