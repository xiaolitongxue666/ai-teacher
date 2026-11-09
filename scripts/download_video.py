#!/usr/bin/env python3
"""用 yt-dlp 下载视频，并把结果登记到 data/resources.json。

为什么要有这层包装，而不是直接敲 yt-dlp：
  1. yt-dlp 的参数很多，教育场景常用的组合固定（最高 1080p、字幕、章节、
     不覆盖已有文件），每次手敲容易漏；
  2. 下载下来的文件需要能被后续流程找到（OCR、转写、归档），
     需要一个稳定的落盘目录与清单；
  3. yt-dlp 不支持任何国内网盘（实测 1755 个提取器里夸克/百度/阿里/115
     命中 0），这一点必须在使用前讲清楚，而不是让用户试错。

用法：
    python scripts/download_video.py <URL> [--output DIR] [--audio-only]
    python scripts/download_video.py --check          # 自检环境

依赖：yt-dlp。优先用 uvx（版本最新），回退到 PATH 里的全局 yt-dlp。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "downloads"
MANIFEST_NAME = "manifest.jsonl"

# 教育场景的默认参数。改动前先想清楚为什么要改。
DEFAULT_FORMAT = "bv*[height<=1080]+ba/b[height<=1080]/b"
AUDIO_FORMAT = "ba/b"

# 这些域名对应的网盘分享，yt-dlp 一律无法直接下载
UNSUPPORTED_HOSTS = {
    "pan.quark.cn": "夸克网盘",
    "pan.baidu.com": "百度网盘",
    "www.aliyundrive.com": "阿里云盘",
    "www.alipan.com": "阿里云盘",
    "115.com": "115 网盘",
    "115cdn.com": "115 网盘",
    "cloud.189.cn": "天翼云盘",
    "caiyun.139.com": "移动云盘",
}


def find_ytdlp() -> tuple[list[str], str]:
    """返回 (启动命令, 版本说明)。优先 uvx，回退全局。"""
    if shutil.which("uvx"):
        return ["uvx", "yt-dlp"], "uvx（每次拉最新版）"
    if shutil.which("yt-dlp"):
        return ["yt-dlp"], "PATH 中的全局 yt-dlp"
    raise SystemExit(
        "找不到 yt-dlp。二选一：\n"
        "  uv tool install yt-dlp        # 推荐，后续用 uvx yt-dlp\n"
        "  pip install -U yt-dlp"
    )


def guard_unsupported_host(url: str) -> None:
    """网盘分享链接直接拒绝，省得用户以为是自己用错了参数。"""
    lowered = url.lower()
    for host, label in UNSUPPORTED_HOSTS.items():
        if host in lowered:
            raise SystemExit(
                f"{label}的分享链接 yt-dlp 下不了。\n"
                f"yt-dlp 没有任何国内网盘提取器（实测 1755 个提取器里命中 0）。\n"
                f"要拿网盘里的 mp4，先用网盘自己的客户端把文件落到本地磁盘，\n"
                f"或者用 BaiduPCS-Go 下载（百度），再把本地文件喂给下游流程。"
            )


def build_command(
    ytdlp_cmd: list[str],
    url: str,
    output_dir: pathlib.Path,
    audio_only: bool,
) -> list[str]:
    """拼出 yt-dlp 命令。

    --no-overwrites    重跑不重复下载
    --write-subs       要字幕：教育视频常配字幕，转写成文本很有用
    --sub-langs        只要中英，避免拉一堆无关语言
    --embed-metadata   带上标题/作者，方便后续归档
    --download-archive 记录已下过的 id，避免同一课程重复拉
    """
    command = [
        *ytdlp_cmd,
        "--format", AUDIO_FORMAT if audio_only else DEFAULT_FORMAT,
        "--output", str(output_dir / "%(uploader)s" / "%(title).120B [%(id)s].%(ext)s"),
        "--no-overwrites",
        "--embed-metadata",
        "--download-archive", str(output_dir / ".archive.txt"),
        "--print", "after_move:filepath",
    ]
    if not audio_only:
        command += [
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", "zh.*,en.*",
            "--convert-subs", "srt",
        ]
    command.append(url)
    return command


def append_manifest(output_dir: pathlib.Path, record: dict) -> None:
    """追加一行到 manifest.jsonl。用 JSONL 而不是单个 JSON，
    因为下载是流式的，中途崩溃也不会破坏已写入的记录。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / MANIFEST_NAME).open("a", encoding="utf-8") as manifest:
        manifest.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_self_check() -> int:
    ytdlp_cmd, source = find_ytdlp()
    version = subprocess.run([*ytdlp_cmd, "--version"], capture_output=True, text=True)
    print(f"yt-dlp 来源: {source}")
    print(f"yt-dlp 版本: {version.stdout.strip() or version.stderr.strip()}")

    listing = subprocess.run([*ytdlp_cmd, "--list-extractors"], capture_output=True, text=True)
    extractor_count = len(listing.stdout.splitlines())
    print(f"提取器数量: {extractor_count}")

    unsupported_hits = [host for host in UNSUPPORTED_HOSTS if host in listing.stdout.lower()]
    print(f"国内网盘提取器: {unsupported_hits or '无（符合预期，yt-dlp 不支持国内网盘）'}")

    print(f"默认输出目录: {DEFAULT_OUTPUT_DIR}")
    print("\n注意：Windows 上 --cookies-from-browser chrome 已不可用。")
    print("Chrome 127+ 用 App-Bound Encryption，密钥绑定 Chrome 进程，外部工具解不开；")
    print("且 Chrome 运行时会独占锁住 Cookie 数据库。yt-dlp 官方已移除该支持。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="用 yt-dlp 下载视频并登记清单")
    parser.add_argument("url", nargs="?", help="视频页面地址")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="输出目录")
    parser.add_argument("--audio-only", action="store_true", help="只下音频")
    parser.add_argument("--check", action="store_true", help="自检环境后退出")
    arguments = parser.parse_args()

    if arguments.check:
        return run_self_check()

    if not arguments.url:
        parser.error("需要 URL，或用 --check 自检")

    guard_unsupported_host(arguments.url)

    ytdlp_cmd, source = find_ytdlp()
    output_dir = pathlib.Path(arguments.output).expanduser().resolve()
    command = build_command(ytdlp_cmd, arguments.url, output_dir, arguments.audio_only)

    print(f"使用 {source}")
    print("命令:", " ".join(command))
    print()

    completed = subprocess.run(command)
    if completed.returncode != 0:
        print(f"\nyt-dlp 退出码 {completed.returncode}，未登记清单", file=sys.stderr)
        return completed.returncode

    append_manifest(output_dir, {
        "url": arguments.url,
        "audio_only": arguments.audio_only,
        "output_dir": str(output_dir),
        "yt_dlp_source": source,
    })
    print(f"\n清单已追加到 {output_dir / MANIFEST_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
