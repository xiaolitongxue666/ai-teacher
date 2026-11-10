#!/usr/bin/env python3
"""GitHub 仓库浅克隆阶段。

为什么用 --depth=1 --single-branch：
  22 个仓合计 19 GB 是 .size 报的压缩后体积，含全部历史。浅克隆只取默认分支
  最新一棵树，实测能砍掉大头（awesome-english-ebooks 的 15.3 GB 主要是历史里
  反复替换的 PDF）。需要历史时再 `git fetch --unshallow` 即可。

为什么按体积升序：
  小仓几分钟就能下完，能立刻验证管道是否通；如果先啃 15 GB 的大仓，
  一旦克隆脚本有 bug，要等半小时才发现。

为什么保留 .git：
  后续要 pull 更新、要看某本书的提交历史，都需要它。删掉 .git 只是省一点空间，
  却把仓库退化成一次性快照。
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import time

from . import common

# 单仓克隆失败后的重试次数。GitHub 对短时间大量克隆会限速，
# 指数退避比固定间隔更有效（实测 2s/4s/8s 三次能救回大部分超时）。
CLONE_RETRIES = 3
CLONE_BACKOFF_SECONDS = 2.0
# 单仓克隆的硬超时（秒）。15 GB 的仓在 100 Mbps 下约 20 分钟，
# 给到 4 小时足够，同时避免僵死进程挂一整天。
CLONE_TIMEOUT_SECONDS = 4 * 60 * 60
# 停滞超时（秒）：连续这么久没有任何进度输出就判定连接已死并重试。
# 实测 BodyVista 的 pack 文件停在 296.8 MB 十分钟不动，进程仍活着，
# 只看退出码永远发现不了 —— 必须靠「多久没输出」判断。
CLONE_STALL_SECONDS = 180


def repo_dir_name(full_name: str) -> str:
    """`owner/repo` -> `owner__repo`。

    用双下划线而不是斜杠，是因为要平铺在同一个目录下；
    用双下划线而不是单下划线，避免 `a/b_c` 与 `a_b/c` 撞名。
    """
    owner, _, repo = str(full_name).partition("/")
    return common.sanitize_segment(f"{owner}__{repo or 'repo'}")


def plan_repos() -> list[dict]:
    """读 resources.json 的 repos 分区，按 GitHub 上报体积升序排。

    体积取 `gh api repos/<slug> --jq .size`（单位 KB）。取不到时按 0 处理
    并排在前面 —— 让它先失败，比让它排在最后悄悄失败要好。
    """
    resources = common.load_resources()
    planned: list[dict] = []
    for record in resources.get("repos", []):
        slug = str(record.get("name") or "").strip()
        if not slug:
            continue
        planned.append({
            "id": record.get("id") or slug,
            "slug": slug,
            "url": record.get("url") or f"https://github.com/{slug}",
            "stars": record.get("stars"),
            "size_kb": _remote_size_kb(slug),
        })
    planned.sort(key=lambda item: item["size_kb"])
    return planned


def _remote_size_kb(slug: str) -> int:
    completed = subprocess.run(
        ["gh", "api", f"repos/{slug}", "--jq", ".size"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    try:
        return int((completed.stdout or "").strip() or 0)
    except ValueError:
        return 0


def clone_one(item: dict, target_root: pathlib.Path, progress: common.Progress | None = None) -> dict:
    """克隆单个仓库，返回结果字典。

    已存在且 .git 目录完整则跳过 —— 断点续跑时不该重复下 19 GB。
    只检查 .git 是否存在不够，因为中途被杀可能留下没有 HEAD 的半成品，
    所以额外要求目录非空。
    """
    destination = target_root / repo_dir_name(item["slug"])
    if _looks_complete(destination):
        return {"id": item["id"], "slug": item["slug"], "status": "skipped", "path": str(destination)}

    if destination.exists() and not _looks_complete(destination):
        # 半成品直接删掉重来。git clone 不支持向已有非空目录克隆。
        _remove_tree(destination)

    common.assert_disk_headroom(item["size_kb"] * 1024, f"克隆 {item['slug']}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "git", "clone",
        "--progress",
        "--depth", "1",
        "--single-branch",
        "--no-tags",
        item["url"],
        str(destination),
    ]
    last_error = ""
    for attempt in range(1, CLONE_RETRIES + 1):
        if progress:
            progress.set_current(f"github: {item['slug']} (第 {attempt} 次尝试)")
        completed_code, last_error = _run_streaming(command, item, progress)
        if completed_code == 0:
            size = _directory_size(destination)
            return {
                "id": item["id"], "slug": item["slug"], "status": "ok",
                "path": str(destination), "bytes": size,
            }
        if attempt < CLONE_RETRIES:
            time.sleep(CLONE_BACKOFF_SECONDS * (2 ** (attempt - 1)))
            if destination.exists():
                _remove_tree(destination)

    return {
        "id": item["id"], "slug": item["slug"], "status": "failed",
        "path": str(destination), "error": last_error,
    }


# git clone --progress 往 stderr 打的进度行形如：
#   Receiving objects:  37% (1234/3333), 45.67 MiB | 2.31 MiB/s
GIT_PROGRESS_PATTERN = re.compile(r"Receiving objects:\s+\d+%[^,]*,\s+([\d.]+)\s+([KMG])iB")


def _run_streaming(command: list[str], item: dict,
                   progress: common.Progress | None) -> tuple[int, str]:
    """跑 git clone 并实时上报进度。

    为什么不用后台线程读 stderr：
      第一版用守护线程 `for line in process.stderr` 解析进度，进程退出后 join。
      实测在 designfuchen/word-atlas 上稳定死锁 —— git 派生的孙进程
      （index-pack、git-remote-https）仍持有管道写端时，即使父进程已退出，
      stderr 迭代也永不返回，主流程就卡在 join 上不记账。

    现方案：把 `--progress` 的 stderr 重定向到项目内的临时文件，主循环
    「sleep 5 秒 → 读文件新增部分 → 解析累计字节」。全程没有阻塞读，
    也不存在管道写端被孙进程持有的问题。

    返回 (退出码, 最后一段输出)。
    """
    progress_log = common.STATE_DIR / "git-progress.log"
    common.STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = progress_log.open("w", encoding="utf-8", errors="replace")

    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=log_handle,
        text=True,
    )
    deadline = time.monotonic() + CLONE_TIMEOUT_SECONDS
    last_activity = time.monotonic()
    read_offset = 0
    reported_bytes = 0
    stall_reason = ""
    tail_text = ""

    try:
        while process.poll() is None:
            time.sleep(5)
            try:
                with progress_log.open("r", encoding="utf-8", errors="replace") as reader:
                    reader.seek(read_offset)
                    chunk = reader.read()
                    read_offset = reader.tell()
            except OSError:
                chunk = ""
            if chunk:
                last_activity = time.monotonic()
                tail_text = (tail_text + chunk)[-2000:]
                if progress is not None:
                    for match in GIT_PROGRESS_PATTERN.finditer(chunk):
                        value = float(match.group(1))
                        multiplier = {"K": 1024, "M": 1024**2, "G": 1024**3}[match.group(2)]
                        current = int(value * multiplier)
                        if current > reported_bytes:
                            reported_bytes = current
                            # 用「已归档体积基线 + 当前仓库实时进度」覆盖 bytes_done。
                            # 直接累加会让 15 GB 的仓库下到一半仍显示上一个仓库的旧数字
                            # （实测进度显示 3.40 GB 而磁盘已 7.0 GB），轮询方看不出真实进展。
                            progress.state["bytes_done"] = (
                                int(progress.state.get("archived_bytes") or 0) + current)
                            progress.flush()

            if time.monotonic() > deadline:
                stall_reason = f"克隆超时（{CLONE_TIMEOUT_SECONDS}s）"
                break
            if time.monotonic() - last_activity > CLONE_STALL_SECONDS:
                stall_reason = f"连接停滞超过 {CLONE_STALL_SECONDS}s 无进度输出"
                break
    finally:
        if stall_reason:
            _kill_process_tree(process.pid)
        process.wait()
        log_handle.close()

    if stall_reason:
        return -1, stall_reason
    return process.returncode, tail_text[-500:]


def _kill_process_tree(pid: int) -> None:
    """杀掉整棵进程树。

    Windows 上用 taskkill /T：git clone 会派生 git-remote-https 与 index-pack，
    只杀父进程会留下持锁的子进程，目标目录就删不掉（实测遇到过）。
    POSIX 上没有等价物，退化到杀单个进程。
    """
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, text=True, errors="replace")
        return
    try:
        os.kill(pid, 9)
    except OSError:
        pass


def run(progress: common.Progress | None = None) -> list[dict]:
    """跑完整个 GitHub 阶段。单个仓失败只记账，不中断后续。"""
    target_root = common.DOWNLOADS_ROOT / "github"
    target_root.mkdir(parents=True, exist_ok=True)
    planned = plan_repos()
    if progress:
        progress.set_totals(item_total=len(planned))

    results: list[dict] = []
    consecutive_failures = 0
    for item in planned:
        try:
            result = clone_one(item, target_root, progress)
        except common.InsufficientDisk as disk_error:
            results.append({"id": item["id"], "slug": item["slug"], "status": "skipped_disk",
                            "error": str(disk_error)})
            if progress:
                progress.record_error(str(disk_error))
            break
        except subprocess.TimeoutExpired:
            result = {"id": item["id"], "slug": item["slug"], "status": "failed",
                      "error": f"克隆超时（{CLONE_TIMEOUT_SECONDS}s）"}
        except Exception as unexpected:  # noqa: BLE001 - 单仓异常不该带崩整轮
            result = {"id": item["id"], "slug": item["slug"], "status": "failed",
                      "error": f"{type(unexpected).__name__}: {unexpected}"}

        results.append(result)
        _append_manifest(target_root, result)
        if progress:
            progress.add_pages(
                count=1,
                item_done=1 if result["status"] in {"ok", "skipped"} else 0,
            )
            # 体积以「已完成仓库的实际占用」作为基线，供下一个仓库的实时进度叠加。
            # 用磁盘实际总量覆盖而不是累加：上一轮跑完的仓库本轮记 skipped、不带 bytes，
            # 累加会漏算；流式解析已加过 in-flight 增量，再累加会双算。
            finished_bytes = _directory_size(target_root)
            progress.state["archived_bytes"] = finished_bytes
            progress.state["bytes_done"] = finished_bytes
            progress.flush()
            if result["status"] == "failed":
                progress.record_error(f"{result['slug']}: {result.get('error', '')}")

        # 连续 5 次失败通常意味着网络或凭据出问题，继续跑只会浪费时间
        consecutive_failures = consecutive_failures + 1 if result["status"] == "failed" else 0
        if consecutive_failures >= 5:
            if progress:
                progress.record_error("连续 5 个仓库克隆失败，暂停 GitHub 阶段")
            break

    return results


def _append_manifest(target_root: pathlib.Path, record: dict) -> None:
    entry = {"recorded_at": common.now_iso(), **record}
    with (target_root / "_manifest.jsonl").open("a", encoding="utf-8") as manifest:
        manifest.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _looks_complete(destination: pathlib.Path) -> bool:
    """判断克隆是否真的完成。

    不能只看 .git/HEAD：git clone 一开始就建好 .git 与 HEAD，然后才开始 fetch，
    所以中途被杀会留下「有 HEAD 但工作区是空的」半成品。实测就是这样：
    BodyVista 的 .git/HEAD 存在，工作区却一个文件都没有。
    可靠判据是 .git/index —— 只有 checkout 完成后才会生成。
    """
    git_dir = destination / ".git"
    if not git_dir.is_dir() or not (git_dir / "HEAD").is_file():
        return False
    return (git_dir / "index").is_file()


def _remove_tree(destination: pathlib.Path) -> None:
    """删半成品。Windows 上 .git 里有只读文件，需要先清掉只读位。"""

    def _on_error(function, path, _exc_info):
        try:
            pathlib.Path(path).chmod(stat.S_IWRITE)
            function(path)
        except OSError:
            pass

    shutil.rmtree(destination, onerror=_on_error)


def _directory_size(root: pathlib.Path) -> int:
    total = 0
    for path in root.rglob("*"):
        if path.is_file():
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total
