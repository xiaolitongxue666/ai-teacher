#!/usr/bin/env python3
"""下载管道的命令行入口。

四个子命令：
  plan    只算体积与数量，不下载。用于开工前确认预算。
  run     实际执行，按 --only 选阶段。
  status  读 progress.json 打一行摘要，供频繁轮询。
  report  生成人类可读的 downloads/_state/REPORT.md。

为什么 status 要单独做成极轻量的命令：
  长任务后台跑的时候，监控方可能每几十秒轮询一次。如果每次都去扫目录、
  读 manifest，轮询本身就会变成负载。status 只读一个 JSON 文件。

为什么 run 要加单实例锁：
  两个进程同时写 progress.json 会互相覆盖；同时克隆同一个仓库会让 git 抢锁失败。
"""

from __future__ import annotations

import argparse
import json
import pathlib

from . import bilibili, common, github, quark

# 720P 体积预估：中位数 53.5 MB/小时、均值 124.6 MB/小时，取中间偏保守的 90 MB/小时。
# 只用于 plan 的总量提示，下载期的守卫用的是更宽的 ESTIMATED_BYTES_PER_SECOND。
VIDEO_BYTES_PER_HOUR = 90 * 1024**2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetch_resources",
        description="把 resources.json 里的 GitHub / B站 / 网盘三类资源下载到 downloads/",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="只估算体积与数量，不下载")
    plan_parser.add_argument("--all-videos", action="store_true",
                             help="含非核心版本的 B站合集（默认只算小学核心五组）")

    run_parser = subparsers.add_parser("run", help="执行下载")
    run_parser.add_argument("--only", choices=["github", "video", "netdisk"],
                            help="只跑某一阶段；省略则按 github -> video -> netdisk 顺序全跑")
    run_parser.add_argument("--manifest-only", action="store_true",
                            help="网盘阶段只产清单不下载（无 Cookie 时自动启用）")
    run_parser.add_argument("--all-videos", action="store_true",
                            help="视频阶段含非核心版本")

    subparsers.add_parser("status", help="打印当前进度（读 progress.json）")
    subparsers.add_parser("report", help="生成 downloads/_state/REPORT.md")
    return parser


def command_plan(arguments: argparse.Namespace) -> int:
    common.reconfigure_stdout()
    rows: list[tuple[str, int, int]] = []

    repos = github.plan_repos()
    repo_bytes = sum(item["size_kb"] for item in repos) * 1024
    rows.append(("github 仓库", len(repos), repo_bytes))

    videos = bilibili.plan_videos(only_core=not arguments.all_videos)
    video_hours = sum(item["duration_seconds"] for item in videos) / 3600
    video_bytes = int(video_hours * VIDEO_BYTES_PER_HOUR)
    rows.append(("B站视频集", len(videos), video_bytes))

    netdisk = quark.plan_netdisk()
    unavailable = [item for item in netdisk if item["status"] == "no_quark_source"]
    rows.append(("网盘小学条目", len(netdisk) - len(unavailable), 0))

    print(f"{'阶段':<14}{'数量':>6}{'预估体积':>14}")
    print("-" * 36)
    total = 0
    for label, count, size in rows:
        total += size
        size_text = common.format_bytes(size) if size else "需实探"
        print(f"{label:<14}{count:>6}{size_text:>14}")
    print("-" * 36)
    print(f"{'合计（不含网盘实探）':<14}{'':>6}{common.format_bytes(total):>14}")

    print()
    print(f"视频口径：{'全部 ' + str(len(videos)) + ' 个合集' if arguments.all_videos else '小学核心五组 ' + str(len(videos)) + ' 个合集'}"
          f"，{sum(item['pages'] for item in videos)} P，{video_hours:.0f} 小时")
    print(f"视频码率假设：{VIDEO_BYTES_PER_HOUR / 1024**2:.0f} MB/小时（实测中位数 53.5、均值 124.6）")
    print(f"盘上剩余：{common.format_bytes(common.free_bytes())}")
    print(f"最低保留量：{common.format_bytes(common.MIN_FREE_BYTES)}")

    if unavailable:
        print(f"\n无夸克源、本阶段跳过：{', '.join(item['id'] for item in unavailable)}")

    credentials = common.read_credentials()
    if not credentials.get("NETDISK_QUARK_COOKIE"):
        print("\n提示：NETDISK_QUARK_COOKIE 未配置，网盘阶段只会产清单，不会下载。")

    print("\n网盘条目体积需实探（每条要翻几百次目录），run --only netdisk 时逐条统计。")
    return 0


def command_run(arguments: argparse.Namespace) -> int:
    common.reconfigure_stdout()
    stages = [arguments.only] if arguments.only else ["github", "video", "netdisk"]

    results: list[dict] = []
    # 锁按阶段加：github 与 video 可并行（产物不冲突），同阶段重跑才要拦
    for stage in stages:
        results.extend(_run_stage(stage, arguments))

    report_path = write_report()
    print(f"\n报告：{report_path}")
    return 1 if any(result.get("status") == "failed" for result in results) else 0


def _run_stage(stage: str, arguments: argparse.Namespace) -> list[dict]:
    with common.SingleInstance(stage):
        print(f"=== 阶段：{stage} ===", flush=True)
        if stage == "github":
            progress = common.Progress("github", item_total=len(github.plan_repos()))
            results = github.run(progress)
        elif stage == "video":
            planned = bilibili.plan_videos(only_core=not arguments.all_videos)
            progress = common.Progress("video", item_total=len(planned),
                                       page_total=sum(item["pages"] for item in planned))
            results = bilibili.run(progress, only_core=not arguments.all_videos)
        else:
            planned = quark.plan_netdisk()
            progress = common.Progress("netdisk", item_total=len(planned))
            results = quark.run(progress, manifest_only=arguments.manifest_only)

        summary = _summarize_stage(results)
        print(summary, flush=True)
        progress.finish(note=summary)
        return results


def _summarize_stage(results: list[dict]) -> str:
    if not results:
        return "无任务"
    counts: dict[str, int] = {}
    for result in results:
        status = str(result.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    total_bytes = sum(int(result.get("bytes") or 0) for result in results)
    detail = "、".join(f"{status} {count}" for status, count in sorted(counts.items()))
    return f"{detail}，累计 {common.format_bytes(total_bytes)}"


def command_status(_arguments: argparse.Namespace) -> int:
    common.reconfigure_stdout()
    states = common.read_all_progress()
    if not states:
        print("尚无进度记录：downloads/_state/progress.*.json 不存在")
        return 0

        # 先写汇总，保证 progress.json 这个单一入口始终是最新的
        common.write_json_atomic(common.PROGRESS_PATH, common.combine_progress())

    for state in states:
        items = f"{state.get('item_done', 0)}/{state.get('item_total', 0)}"
        eta = state.get("eta_minutes")
        eta_text = f"{eta} 分钟" if eta else "未知"
        flag = "已完成" if state.get("finished") else "进行中"
        # GitHub 与网盘阶段按条目计数、没有「分P」概念，page_total 为 0 时不该显示 21/0
        page_total = int(state.get("page_total") or 0)
        if page_total:
            progress_text = f"分P {state.get('page_done', 0)}/{page_total}"
        elif state.get("stage") == "netdisk":
            progress_text = "按分享"
        else:
            progress_text = "按仓库"
        print(f"[{state.get('stage')}] 条目 {items} / {progress_text} / "
              f"{common.format_bytes(int(state.get('bytes_done') or 0))} / "
              f"剩余 {eta_text} / {flag}")
        if state.get("current"):
            print(f"  当前 {state['current']}")
        if state.get("last_error"):
            print(f"  最近错误 {state['last_error']}")
        if state.get("note"):
            print(f"  备注 {state['note']}")
        print(f"  更新于 {state.get('updated_at')}")

    if len(states) > 1:
        combined = common.combine_progress()
        page_total = int(combined.get("page_total") or 0)
        pages_text = f"{combined.get('page_done')}/{page_total} P" if page_total else "—"
        print(f"合计：条目 {combined.get('item_done')}/{combined.get('item_total')}，"
              f"{pages_text}，"
              f"{common.format_bytes(int(combined.get('bytes_done') or 0))}")
    return 0


def command_report(_arguments: argparse.Namespace) -> int:
    common.reconfigure_stdout()
    path = write_report()
    print(f"已写出 {path}")
    return 0


def write_report() -> pathlib.Path:
    """把三份 manifest 汇总成一页人可读的报告。

    只读 manifest.jsonl，不重新探测网络 —— 报告要能离线生成。
    """
    common.reconfigure_stdout()
    lines: list[str] = ["# 资源下载报告", "", f"生成时间：{common.now_iso()}", ""]
    states = common.read_all_progress()
    if states:
        lines += ["## 最近一次运行", ""]
        for state in states:
            page_total = int(state.get("page_total") or 0)
            lines += [
                f"### {state.get('stage')}",
                "",
                f"- 条目：{state.get('item_done', 0)}/{state.get('item_total', 0)}",
            ]
            if page_total:
                lines.append(f"- 分P：{state.get('page_done', 0)}/{page_total}")
            lines += [
                f"- 体积：{common.format_bytes(int(state.get('bytes_done') or 0))}",
                f"- 更新时间：{state.get('updated_at')}",
                f"- 状态：{'已完成' if state.get('finished') else '进行中'}",
            ]
            if state.get("note"):
                lines.append(f"- 备注：{state['note']}")
            if state.get("last_error"):
                lines.append(f"- 最近错误：{state['last_error']}")
            lines.append("")

    for title, manifest_path in (
        ("GitHub 仓库", common.DOWNLOADS_ROOT / "github" / "_manifest.jsonl"),
        ("B站视频", common.DOWNLOADS_ROOT / "videos" / "_manifest.jsonl"),
        ("网盘", common.DOWNLOADS_ROOT / "netdisk" / "_manifest.jsonl"),
    ):
        lines += [f"## {title}", ""]
        records = _read_manifest(manifest_path)
        if not records:
            lines += ["（尚无记录）", ""]
            continue
        lines += ["| 条目 | 状态 | 分P/文件 | 体积 | 路径 |", "| --- | --- | --- | --- | --- |"]
        for record in records:
            pages = record.get("pages_done") or record.get("files") or ""
            size = common.format_bytes(int(record.get("bytes") or 0)) if record.get("bytes") else ""
            path = str(record.get("path") or record.get("target_dir") or "")
            lines.append(f"| {record.get('id', '')} | {record.get('status', '')} | {pages} | {size} | `{path}` |")
        lines.append("")

    netdisk_dir = common.DOWNLOADS_ROOT / "netdisk" / "quark" / "小学"
    if netdisk_dir.is_dir():
        manifests = sorted(netdisk_dir.glob("*/_inventory.json"))
        if manifests:
            lines += ["## 网盘待续传清单", "",
                      "以下分享已翻完目录，但当前无登录态，未下载。填入 NETDISK_QUARK_COOKIE 后重跑：",
                      "", "```", "python scripts/fetch_resources.py run --only netdisk", "```", ""]
            for manifest in manifests:
                payload = common.read_json(manifest, {})
                truncated = "（目录未翻完，数字为下界）" if payload.get("truncated") else ""
                lines.append(
                    f"- `{payload.get('item_id')}`：{payload.get('files')} 文件 / "
                    f"{common.format_bytes(int(payload.get('bytes') or 0))}{truncated}"
                )
            lines.append("")

    common.REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    common.REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return common.REPORT_PATH


def _read_manifest(path: pathlib.Path) -> list[dict]:
    if not path.is_file():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def main(argv: list[str] | None = None) -> int:
    common.reconfigure_stdout()
    arguments = build_parser().parse_args(argv)
    if arguments.command == "plan":
        return command_plan(arguments)
    if arguments.command == "run":
        return command_run(arguments)
    if arguments.command == "status":
        return command_status(arguments)
    return command_report(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
