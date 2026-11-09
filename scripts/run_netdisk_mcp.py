#!/usr/bin/env python3
"""启动 netdisk MCP，凭据从 .credentials/netdisk.env 读取。

为什么不把 Cookie 直接写进 .cursor/mcp.json：
  1. mcp.json 一旦被 Cursor 读取就会带着明文凭据出现在进程环境里；
  2. 换 Cookie 时要改两处容易漏；
  3. 凭据文件可以单独 chmod / 单独忽略，审计面更小。

缺凭据也能启动：view（读公开分享）不需要 cookie，list/transfer 才需要。
缺的时候往 stderr 打一行提示，不影响 MCP 握手。

用法（由 .cursor/mcp.json 调用）：
    python scripts/run_netdisk_mcp.py
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = REPO_ROOT / ".credentials" / "netdisk.env"

# 凭据文件里的键名 -> 传给 MCP 子进程的环境变量名
CREDENTIAL_KEYS = {
    "NETDISK_QUARK_COOKIE": "NETDISK_QUARK_COOKIE",
    "NETDISK_BAIDU_COOKIE": "NETDISK_BAIDU_COOKIE",
}
# netdisk-mcp-server 只认夸克与 115；百度 Cookie 目前没有被这个包使用，
# 留着是为了同一份凭据文件能给 BaiduPCS-Go 复用。
MCP_CONSUMES = ("NETDISK_QUARK_COOKIE",)

MCP_PACKAGE = "@ptbsare/netdisk-mcp-server"


def load_credentials(path: pathlib.Path) -> dict[str, str]:
    """解析 KEY=VALUE 形式的环境文件。忽略注释、空行和不带值的行。"""
    if not path.is_file():
        return {}
    credentials: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        # Cookie 里可能出现引号包裹，但规范用法不加引号；这里只去掉成对的引号
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key in CREDENTIAL_KEYS and value:
            credentials[CREDENTIAL_KEYS[key]] = value
    return credentials


def main() -> int:
    credentials = load_credentials(CREDENTIALS_PATH)

    missing = [name for name in MCP_CONSUMES if not credentials.get(name)]
    if missing:
        print(
            f"[run_netdisk_mcp] 未配置 {', '.join(missing)}，"
            f"view 可用（读公开分享），list/transfer 会返回 401。"
            f"填 {CREDENTIALS_PATH} 后重启 MCP 生效。",
            file=sys.stderr,
        )

    child_environment = {**os.environ, **credentials}
    # npx 在 Windows 上是 .cmd，shell=True 才能解析；参数里不含用户输入，无注入面
    command = ["npx", "-y", MCP_PACKAGE]
    try:
        return subprocess.call(command, env=child_environment, cwd=str(REPO_ROOT), shell=(os.name == "nt"))
    except FileNotFoundError:
        print("[run_netdisk_mcp] 找不到 npx，请确认 Node.js 已安装且在 PATH 中", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
