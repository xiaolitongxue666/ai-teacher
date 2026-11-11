#!/usr/bin/env python3
"""下载管道的公共设施：路径清洗、进度记账、磁盘守卫。

为什么单独成模块，而不是散在各阶段里：
  1. Windows 文件名规则是全局约束（保留名、非法字符、尾部点/空格、260 字符上限），
     视频标题里出现 `|` 或 `?` 的概率很高，清洗必须只有一份实现；
  2. progress.json 是外部轮询的唯一入口，写入必须原子，否则轮询方会读到半截 JSON；
  3. 磁盘守卫要在每个子任务开工前判断，而不是只在启动时判断一次 —— 下载过程中
     体积会涨，启动时的判断很快过期。

路径约定：所有产物落在项目内 downloads/ 下。不使用 /tmp，因为 MSYS bash 的
/tmp 解析为 C:\msys64\tmp，而 Windows Python 的 /tmp 解析为 C:\tmp，跨端会丢文件。
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import shutil
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DOWNLOADS_ROOT = REPO_ROOT / "downloads"
STATE_DIR = DOWNLOADS_ROOT / "_state"
RESOURCES_PATH = REPO_ROOT / "data" / "resources.json"
CREDENTIALS_PATH = REPO_ROOT / ".credentials" / "netdisk.env"

PROGRESS_PATH = STATE_DIR / "progress.json"
REPORT_PATH = STATE_DIR / "REPORT.md"
# 单实例锁按阶段分文件，见 SingleInstance 的说明
CLAIM_PATH = STATE_DIR / "RUNNING.lock"
# 每个阶段各写一个进度文件。两个阶段并行时共用一个 progress.json 会互相覆盖，
# 轮询方看到的是「最后写入者」的状态，不是真实进度。progress.json 保留为
# 汇总视图，由 status 从各阶段文件合成。
STAGE_PROGRESS_GLOB = "progress.*.json"
# 开工前必须留出的余量。低于它就停下，而不是把盘写满 ——
# 写满会让 7z/ffmpeg 合并中途失败，产生半个文件，比不下载更糟。
MIN_FREE_BYTES = 20 * 1024**3

# 原子替换目标 JSON 的重试参数。Windows 上目标被外部进程打开时 os.replace
# 抛 PermissionError（WinError 5），占用通常只持续毫秒级，重试即可跨过去。
# 退避按 attempt 线性增长，6 次约 0.75s；实测 1.5s 的独占打开仍会失败，
# 所以放到 10 次（约 4.5s）。轮询方读一次只有毫秒级，正常不会走到这么深。
REPLACE_ATTEMPTS = 10
REPLACE_BACKOFF_SECONDS = 0.1

# Windows 文件名禁用字符（保留 `/` 与 `\` 用于路径分隔，清洗时替换）
WINDOWS_FORBIDDEN_CHARS = '<>:"/\\|?*'
# Windows 设备保留名，任何扩展名下都不能作为文件名主干
WINDOWS_RESERVED_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6",
     "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6",
     "LPT7", "LPT8", "LPT9"]
)
# 单个路径段的长度上限。Windows API 走 MAX_PATH 时整路径 260，
# 但 NTFS 单段本身允许 255 —— 这里用 120 给父目录留足余量。
MAX_SEGMENT_LENGTH = 120


def reconfigure_stdout() -> None:
    """Python 在 Windows 默认按 GBK 输出，中文标题会直接抛 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sanitize_segment(raw: str, fallback: str = "未命名") -> str:
    """把一个字符串清洗成合法的单层路径段。

    处理顺序有讲究：
      1. 先替换非法字符（含控制字符），否则后续正则可能被控制字符干扰；
      2. 再压缩空白，避免标题里的连续空格撑爆路径长度；
      3. 去掉首尾的点与空格 —— Windows 会静默丢弃尾部点，导致
         「写入 A. 读取 A」这种诡异失败；
      4. 最后查保留名，因为 `CON.mp4` 也是非法的。
    """
    text = str(raw or "").strip()
    for char in WINDOWS_FORBIDDEN_CHARS:
        text = text.replace(char, "_")
    # 控制字符（\x00-\x1f）在文件名里非法且肉眼不可见。
    # 必须先替换成空格再压缩空白：直接删掉会让 "a\nb" 粘成 "ab"，
    # 实测把 "a    b\n\tc" 处理成了 "a bc"（单词粘连），是单元测试抓到的。
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip(" .")
    if not text:
        return fallback
    if text.upper() in WINDOWS_RESERVED_NAMES:
        text = f"_{text}"
    if len(text) > MAX_SEGMENT_LENGTH:
        # 截断时保留扩展名判断留给调用方，这里只保证长度合法
        text = text[:MAX_SEGMENT_LENGTH].strip(" .")
    return text or fallback


def sanitize_relative_path(*segments: str) -> pathlib.Path:
    """把若干层路径段清洗后拼成相对路径。

    传入的每一段都可以是含 `/` 的相对路径（网盘接口返回的就是这种），
    必须逐段拆开清洗，不能整段当作一个文件名 —— 整段清洗会把
    `a/b/文件.mp4` 里的 `/` 替换成 `_`，所有文件平铺到一层，
    文件名里还残留整条路径（实测网盘产物就是这样，
    每个文件都带 50 字符的分享标题前缀）。
    """
    parts: list[str] = []
    for segment in segments:
        text = str(segment or "").replace("\\", "/").strip()
        if not text:
            continue
        for piece in text.split("/"):
            piece = piece.strip()
            if piece and piece not in (".", ".."):
                parts.append(sanitize_segment(piece))
    return pathlib.Path(*parts) if parts else pathlib.Path("未命名")


def free_bytes(path: pathlib.Path = DOWNLOADS_ROOT) -> int:
    """返回指定盘剩余字节数。路径不存在时退到最近的已存在父目录。"""
    target = path
    while not target.exists() and target != target.parent:
        target = target.parent
    try:
        return shutil.disk_usage(str(target)).free
    except OSError:
        return 0


def assert_disk_headroom(needed_bytes: int, stage: str) -> None:
    """磁盘守卫。不足时抛异常，由 CLI 捕获后写进报告并停止该阶段。"""
    available = free_bytes()
    if available - needed_bytes < MIN_FREE_BYTES:
        raise InsufficientDisk(
            f"{stage} 预计需要 {format_bytes(needed_bytes)}，"
            f"盘上剩余 {format_bytes(available)}，"
            f"不足最低保留量 {format_bytes(MIN_FREE_BYTES)}"
        )


class InsufficientDisk(RuntimeError):
    """磁盘空间不足，需要人工介入。"""


def format_bytes(value: int | float) -> str:
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size) < 1024 or unit == "TB":
            return f"{size:.2f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.2f} TB"


def write_json_atomic(path: pathlib.Path, payload: dict) -> None:
    """原子写 JSON：先写 .tmp 再 os.replace。

    同名 .replace 在同一卷上是原子操作，轮询方要么读到旧文件、要么读到新文件，
    不会读到写了一半的内容。直接 open("w") 会让轮询方 json.loads 失败。

    Windows 上 os.replace 会在目标文件正被其它进程打开时抛 PermissionError
    （WinError 5，实测发生在外部脚本读取 progress.netdisk.json 的瞬间）。
    这个占用是毫秒级的，重试即可；早期版本不重试，导致一次采样就把整个
    下载阶段打成崩溃 —— 错误处理路径上的 flush 一抛异常，外层没有兜底。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(REPLACE_BACKOFF_SECONDS * (attempt + 1))


def read_json(path: pathlib.Path, default: dict | None = None) -> dict:
    if not path.is_file():
        return dict(default or {})
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(default or {})


class Progress:
    """progress.json 的读写封装。

    外部轮询者只认这个文件，所以每次状态变更都必须立即落盘，
    不能攒在内存里最后一次性写 —— 长任务中途被杀就什么都不剩了。
    """

    def __init__(self, stage: str, item_total: int = 0, page_total: int = 0) -> None:
        self.stage = stage
        # 每阶段独立文件，避免并行阶段互相覆盖
        self.path = STATE_DIR / f"progress.{stage}.json"
        self.state = read_json(self.path, {})
        self.state.update({
            "stage": stage,
            "item_done": 0,
            "item_total": item_total,
            "page_done": 0,
            "page_total": page_total,
            "bytes_done": 0,
            "eta_minutes": None,
            "last_error": "",
            "started_at": now_iso(),
            "updated_at": now_iso(),
            "finished": False,
        })
        self._started = dt.datetime.now()
        self.flush()

    def flush(self) -> None:
        self.state["updated_at"] = now_iso()
        write_json_atomic(self.path, self.state)

    def set_totals(self, item_total: int | None = None, page_total: int | None = None) -> None:
        if item_total is not None:
            self.state["item_total"] = item_total
        if page_total is not None:
            self.state["page_total"] = page_total
        self.flush()

    def add_pages(self, count: int = 1, byte_delta: int = 0, item_done: int = 0) -> None:
        self.state["page_done"] = int(self.state.get("page_done") or 0) + count
        self.state["bytes_done"] = int(self.state.get("bytes_done") or 0) + int(byte_delta)
        if item_done:
            self.state["item_done"] = int(self.state.get("item_done") or 0) + item_done
        self.state["eta_minutes"] = self._estimate_eta()
        self.flush()

    def set_current(self, label: str) -> None:
        self.state["current"] = label
        self.flush()

    def record_error(self, message: str) -> None:
        # 只保留最近一条，避免 progress.json 无限膨胀；完整错误在 run.log
        self.state["last_error"] = str(message)[:400]
        self.flush()

    def finish(self, note: str = "") -> None:
        self.state["finished"] = True
        self.state["finished_at"] = now_iso()
        if note:
            self.state["note"] = note
        self.flush()

    def _estimate_eta(self) -> float | None:
        elapsed = (dt.datetime.now() - self._started).total_seconds()
        done = int(self.state.get("page_done") or 0)
        total = int(self.state.get("page_total") or 0)
        if done <= 0 or total <= done or elapsed <= 0:
            return None
        per_page = elapsed / done
        return round(per_page * (total - done) / 60, 1)


def read_all_progress() -> list[dict]:
    """读所有阶段的进度文件，按 stage 排序。

    兼容只有一个 progress.json 的旧格式：早期版本所有阶段共用一个文件，
    若此时正有旧进程在跑，它的进度只写在那里，不回退就读不到。
    """
    states = []
    for path in sorted(STATE_DIR.glob(STAGE_PROGRESS_GLOB)):
        state = read_json(path, {})
        if state:
            states.append(state)
    if not states:
        legacy = read_json(PROGRESS_PATH, {})
        if legacy and not legacy.get("stages"):
            states.append(legacy)
    return states


def combine_progress() -> dict:
    """把各阶段进度合成一份汇总，写成 progress.json 供外部单一入口轮询。

    汇总口径：分P与字节直接相加；条目取各阶段 (done, total) 之和；
    任一阶段未完成则整体视为进行中。

    `persist=False` 用于单元测试：测试会替换 read_all_progress 返回假数据，
    若此时写盘就会把真实的 progress.json 覆盖成测试样例（实测发生过，
    progress.json 被写成了 stage "a+b" 的假数据）。
    """
    states = read_all_progress()
    if not states:
        return read_json(PROGRESS_PATH, {})
    if len(states) == 1:
        combined = dict(states[0])
    else:
        combined = {
            "stage": "+".join(state.get("stage", "?") for state in states),
            "item_done": sum(int(state.get("item_done") or 0) for state in states),
            "item_total": sum(int(state.get("item_total") or 0) for state in states),
            "page_done": sum(int(state.get("page_done") or 0) for state in states),
            "page_total": sum(int(state.get("page_total") or 0) for state in states),
            "bytes_done": sum(int(state.get("bytes_done") or 0) for state in states),
            "eta_minutes": None,
            "last_error": next((s["last_error"] for s in states if s.get("last_error")), ""),
            "updated_at": max(str(state.get("updated_at") or "") for state in states),
            "finished": all(bool(state.get("finished")) for state in states),
            "stages": [
                {key: state.get(key) for key in
                 ("stage", "item_done", "item_total", "page_done", "page_total",
                  "bytes_done", "current", "finished", "updated_at")}
                for state in states
            ],
        }
    return combined


def read_credentials() -> dict[str, str]:
    """读 .credentials/netdisk.env 的 KEY=VALUE。与 run_netdisk_mcp.py 同格式。"""
    if not CREDENTIALS_PATH.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in CREDENTIALS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load_resources() -> dict:
    return json.loads(RESOURCES_PATH.read_text(encoding="utf-8"))


class SingleInstance:
    """单实例锁，按阶段隔离。

    之所以按阶段：github 与 video 可以并行跑（一个吃带宽、一个吃带宽但产物
    不冲突），用全局锁会把并行变成串行。真正的冲突只发生在同一阶段被起两次。

    判活用 pid：Windows 上没有 fcntl，而 pid 在进程存活时一定被占用。
    """

    def __init__(self, stage: str) -> None:
        self.path = STATE_DIR / f"RUNNING.{stage}.lock"
        self.acquired = False

    def __enter__(self) -> "SingleInstance":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_file():
            existing = read_json(self.path, {})
            pid = int(existing.get("pid") or 0)
            if pid and _pid_alive(pid):
                raise RuntimeError(
                    f"阶段 {self.path.stem} 已有进程在跑（pid {pid}，"
                    f"开始于 {existing.get('started_at')}）。"
                    f"确认要重开就删掉 {self.path}"
                )
        write_json_atomic(self.path, {"pid": os.getpid(), "started_at": now_iso()})
        self.acquired = True
        return self

    def __exit__(self, *_exc_info) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except OSError:
                pass


def _pid_alive(pid: int) -> bool:
    """判断进程是否存活。

    Windows 上 os.kill(pid, 0) 对已退出的 pid 会抛 SystemError 而非 OSError
    （CPython 的行为差异），第一版只捕 OSError，结果锁判活直接崩在半路。
    两种异常都要接住并视为「已退出」。
    """
    try:
        os.kill(pid, 0)
    except (OSError, SystemError):
        return False
    except Exception:  # noqa: BLE001 - 判活失败时保守认为已退出，允许重跑
        return False
    return True
