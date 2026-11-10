"""三类资源的统一下载管道：GitHub 仓库、B站视频、网盘分享。

入口是 scripts/fetch_resources.py，本包只提供各阶段实现。
"""

from __future__ import annotations

__all__ = ["common", "github", "bilibili", "quark", "cli"]
