"""检测本机 Chrome 的 Cookie 加密格式，判断能否被外部工具读取。

背景：这套检查是为了回答「为什么 --cookies-from-browser chrome 在这台机器上
永远失败」。答案分两层，两层都要探测才能说清楚：

  第一层：文件能不能读？
    Chrome 运行时独占锁 Network/Cookies，直接 open 会 PermissionError。
    但 VSS（卷影复制）能拿到快照 —— 需要管理员权限。

  第二层：拿到文件后能不能解密？
    Chrome 127+ 在 Windows 上用 App-Bound Encryption，Cookie 前缀 v20。
    密钥链是 SYSTEM DPAPI -> 用户 DPAPI -> 硬编码在 elevation_service.exe 的
    密钥，外部进程走不通。这是 Chrome 防 infostealer 的核心设计，不是配置问题。

本脚本只做检测与报告，不解密、不提权。

用法：
    python scripts/check_chrome_cookies.py
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wintypes
import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile

def _find_chrome_user_data() -> pathlib.Path:
    """定位 Chrome User Data 目录。

    不能只依赖 %LOCALAPPDATA%：在 MSYS bash 里启动的 Python 常常拿不到这个变量，
    直接 os.environ["LOCALAPPDATA"] 会抛 KeyError。
    """
    candidates = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append(pathlib.Path(local_app_data) / "Google/Chrome/User Data")
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        candidates.append(pathlib.Path(user_profile) / "AppData/Local/Google/Chrome/User Data")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0] if candidates else pathlib.Path("Google/Chrome/User Data")


CHROME_USER_DATA = _find_chrome_user_data()
LOCAL_STATE = CHROME_USER_DATA / "Local State"
COOKIE_DB = CHROME_USER_DATA / "Default/Network/Cookies"

# 关注的站点（本仓库实际要用的）
WATCHED_DOMAINS = ("pan.baidu.com", "pan.quark.cn", "baidu.com", "quark.cn")

V20_MARKER = "763230"  # hex("v20")
V10_MARKER = "763130"  # hex("v10")


class DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def dpapi_unprotect(payload: bytes) -> bytes | None:
    """用当前用户身份调 DPAPI 解密。失败返回 None。"""
    buffer = ctypes.create_string_buffer(payload, len(payload))
    in_blob = DataBlob(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    out_blob = DataBlob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)
    )
    if not ok:
        return None
    result = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    return result


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def try_direct_read() -> bool:
    try:
        with COOKIE_DB.open("rb") as handle:
            handle.read(16)
        return True
    except PermissionError:
        return False
    except OSError:
        return False


def copy_via_vss(destination: pathlib.Path) -> bool:
    """用卷影复制把锁定的 Cookie 库复制出来。

    \\?\GLOBALROOT\Device\... 这种设备路径 .NET 的 Test-Path / Copy-Item 会判不存在，
    必须用 Win32 CopyFileW。另外 MSYS 环境里 PowerShell 调 cmd 会解析错路径，
    所以这里全程不碰 cmd。
    """
    if not is_admin():
        return False

    create_script = (
        '$ErrorActionPreference = "Stop"\n'
        '$create = (Get-WmiObject -List Win32_ShadowCopy).Create("C:\\", "ClientAccessible")\n'
        'if (-not $create) { Write-Output "FAIL"; exit 1 }\n'
        '$sc = Get-WmiObject Win32_ShadowCopy | Where-Object { $_.ID -eq $create.ShadowID }\n'
        'Write-Output $sc.DeviceObject\n'
    )
    created = subprocess.run(
        ["powershell", "-NoProfile", "-Command", create_script],
        capture_output=True,
        text=True,
    )
    device = created.stdout.strip()
    if not device or device == "FAIL":
        return False

    relative = str(COOKIE_DB)[len("C:\\"):]
    source = device + "\\" + relative
    destination.parent.mkdir(parents=True, exist_ok=True)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    copied = bool(kernel32.CopyFileW(source, str(destination), False))

    cleanup = (
        'Get-WmiObject Win32_ShadowCopy | Where-Object { $_.DeviceObject -eq \''
        + device
        + '\' } | ForEach-Object { $_.Delete() }'
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", cleanup], capture_output=True, text=True)
    return copied


def inspect_cookies(db_path: pathlib.Path) -> tuple[dict[str, int], list[tuple[str, str, str]]]:
    """返回 (前缀分布, 关注站点的 cookie 列表)。"""
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        distribution = dict(
            connection.execute(
                "select substr(hex(encrypted_value),1,6), count(*) from cookies "
                "group by 1 order by 2 desc"
            ).fetchall()
        )
        watched = []
        for domain in WATCHED_DOMAINS:
            for host, name, prefix in connection.execute(
                "select host_key, name, substr(hex(encrypted_value),1,6) from cookies "
                "where host_key like ? and name in ('BDUSS','STOKEN','__pus','__kp','_uid')",
                (f"%{domain}%",),
            ):
                watched.append((host, name, prefix))
        return distribution, watched
    finally:
        connection.close()


def main() -> int:
    print("=== 环境 ===")
    print("Chrome profile:", CHROME_USER_DATA)
    print("管理员权限:", is_admin())
    if not COOKIE_DB.is_file():
        print("找不到 Cookie 数据库，Chrome 可能未使用过")
        return 1

    print("\n=== 第一层：文件可读性 ===")
    readable = try_direct_read()
    print("直接读取:", "成功" if readable else "失败（Chrome 独占锁）")

    db_path = COOKIE_DB
    if not readable:
        temp_copy = pathlib.Path(tempfile.gettempdir()) / "chrome_cookies_probe.db"
        if copy_via_vss(temp_copy):
            print("VSS 卷影复制: 成功")
            db_path = temp_copy
        else:
            print("VSS 卷影复制: 失败（需管理员权限）")
            print("\n结论：连文件都拿不到，后续步骤无意义。")
            return 1

    print("\n=== 第二层：加密格式 ===")
    distribution, watched = inspect_cookies(db_path)
    total = sum(distribution.values())
    print(f"Cookie 总数: {total}")
    for prefix, count in distribution.items():
        if prefix == V20_MARKER:
            print(f"  v20 (App-Bound) : {count} 条")
        elif prefix == V10_MARKER:
            print(f"  v10 (DPAPI)     : {count} 条")
        else:
            print(f"  {prefix}          : {count} 条")

    if watched:
        print("\n关注的站点:")
        for host, name, prefix in watched:
            kind = "v20" if prefix == V20_MARKER else ("v10" if prefix == V10_MARKER else prefix)
            print(f"  {host:20} {name:12} {kind}")

    print("\n=== 第三层：密钥可解性 ===")
    if LOCAL_STATE.is_file():
        state = json.loads(LOCAL_STATE.read_text(encoding="utf-8"))
        os_crypt = state.get("os_crypt") or {}
        v10_key = os_crypt.get("encrypted_key")
        v20_key = os_crypt.get("app_bound_encrypted_key")
        if v10_key:
            raw = base64.b64decode(v10_key)
            unlocked = dpapi_unprotect(raw[5:]) if raw[:5] == b"DPAPI" else None
            print(f"v10 主密钥（用户 DPAPI）: {'可解，' + str(len(unlocked)) + ' 字节' if unlocked else '不可解'}")
        if v20_key:
            raw = base64.b64decode(v20_key)
            unlocked = dpapi_unprotect(raw[4:]) if raw[:4] == b"APPB" else None
            print(f"v20 主密钥（用户 DPAPI）: {'可解' if unlocked else '不可解（需 SYSTEM 层 DPAPI）'}")

    if db_path != COOKIE_DB:
        db_path.unlink(missing_ok=True)
        print("\n已删除临时副本")

    print("\n=== 结论 ===")
    if distribution.get(V20_MARKER):
        print("所有 Cookie 都是 v20，外部工具无法解密。")
        print("这是 Chrome 127+ 的 App-Bound Encryption 设计：密钥绑定 Chrome 进程，")
        print("yt-dlp 等工具在 Windows 上永久失效（官方 issue #15401 已声明不修）。")
        print("\n可行路径：")
        print("  1. 手动从 DevTools 复制 Cookie（30 秒，最省事）")
        print("  2. 用浏览器扩展导出 cookies.txt")
        print("  3. 改用 Firefox，--cookies-from-browser firefox 无此限制")
    else:
        print("存在 v10 Cookie，可尝试用 v10 主密钥解密。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
