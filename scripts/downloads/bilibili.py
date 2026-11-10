#!/usr/bin/env python3
"""B站视频下载阶段，走 BBDown 而不是 yt-dlp。

为什么必须用 BBDown：
  yt-dlp 走网页播放接口，匿名态最高只有 480P（实测 `30032+30280|480`），
  720P/1080P 被标成大会员专属，它会静默回退 480P 而不报错。
  BBDown 的 `--use-tv-api` 走 TV 端接口，匿名就能拿 720P：
  实测 `BV1NyyDBhExG` P1 产出 h264 / 1280x720 / 27.1 MB / 14分46秒。

为什么按 P 而不是按合集记账：
  一个合集 100 P，中途被杀只完成 37 P。若按合集记「未完成」，
  重跑会从头再来；按 P 记账才能精确续传。

为什么加 --delay-per-page：
  单合集连续几百个请求会触发 B 站风控（实测过快时返回空 playurl）。
  4 秒间隔对 100 P 的合集只多花 7 分钟，换来的是不被打断。
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess

from . import common

# 实测确认可用的匿名 720P 组合。改这些参数前请先跑 --only-show-info 复核清晰度。
BBDOWN_VIDEO_ENCODING_PRIORITY = "avc"     # h264 兼容性最好，教育场景要投屏到老旧设备
BBDOWN_QUALITY_PRIORITY = "720P"           # TV 接口匿名上限；1080P 需要大会员
BBDOWN_PAGE_DELAY_SECONDS = 4

# 720P 的码率假设，用于下载前的磁盘守卫。
# 9 个样本实测：中位数 53.5 MB/小时，均值 124.6 MB/小时，单合集最高 774 MB/小时。
# 守卫取 300 MB/小时（约 85 KB/s）：高于中位数 5 倍，既不会误拦，
# 也能在真正的大码率合集上及时发现空间不足。守卫只需量级正确，不需要精确。
ESTIMATED_BYTES_PER_SECOND = 85 * 1024
# 单合集下载的硬超时：100 P × 15 分钟平均时长，按 1 MB/s 估算约 90 分钟，
# 给到 6 小时覆盖慢速与大合集。
CONTAINER_TIMEOUT_SECONDS = 6 * 60 * 60
# 单个合集失败后的重试次数
CONTAINER_RETRIES = 2

# id 前缀 -> 教材版本中文名。白名单内的合集落盘，其余版本暂不下。
EDITION_BY_PREFIX = {
    "tongbian": "统编版",
    "renjiao": "人教版",
    "beishida": "北师大版",
    "waiyanshe": "外研社版",
    "waiyan_xinjiaoji": "外研新交际版",
}
# 本次要下的合集前缀：小学核心五组（统编语文 + 人教数学 + 人教英语 + 北师数学 + 外研三起点英语）。
# 必须写全 `beishida_math` 而不是 `beishida`，否则会把北师英语也带进来；
# 用 `waiyanshe_english` 而不是 `waiyan`，以排除地方教材 `waiyan_xinjiaoji_english`。
CORE_PREFIXES = (
    "tongbian_chinese",
    "renjiao_math",
    "renjiao_english",
    "beishida_math",
    "waiyanshe_english",
)

# BBDown 的默认 BBDown.exe 位置。允许用环境变量覆盖，避免把绝对路径写死。
DEFAULT_BBDOWN = r"E:\Code\my_code\Tools\BBDownload\BBDownExe\BBDown.exe"
# 文件命名模板。
#
# 用 `<pageNumberWithZero>` 而不是 `<pageNumber>`：后者完全不带前导零，
# 目录里排序会变成 P1, P10, P100, P2...，播放器顺序全乱。
#
# 但 `<pageNumberWithZero>` 的补零位数由 BBDown 内部推断，实测会漂：
# 同一个 100P 合集，全量下载得到 `[P001]`..`[P100]`（3 位），
# 而 `-p 1,2` 只得到 `[P1]`、`[P2]`（1 位）。
# 一旦用 `-p` 补下单个分P，目录里就会出现 `[P1]` 与 `[P001]` 两份同名内容。
# 因此下载后必须跑 normalize_page_numbers() 归一化，见该函数说明。
PAGE_NAME_PATTERN = "[P<pageNumberWithZero>] <pageTitle>"
# 文件名里 `[P123]` 这类前缀的正则，用于归一化时定位与改写
PAGE_PREFIX_PATTERN = re.compile(r"^\[P(\d+)\]")


def find_bbdown() -> pathlib.Path:
    override = os.environ.get("BBDOWN_PATH")
    candidate = pathlib.Path(override) if override else pathlib.Path(DEFAULT_BBDOWN)
    if not candidate.is_file():
        raise SystemExit(
            f"找不到 BBDown：{candidate}\n"
            f"用 BBDOWN_PATH 环境变量指定，或把 BBDown.exe 放到该路径。"
        )
    return candidate


def edition_of(item_id: str) -> str:
    """从 id 前缀推断教材版本。未知前缀归到「其他版」。"""
    for prefix, label in EDITION_BY_PREFIX.items():
        if str(item_id).startswith(prefix):
            return label
    return "其他版"


def target_dir_for(record: dict) -> pathlib.Path:
    """视频落盘目录：videos/bilibili/小学/<学科>-<版本>/<年级>-<册>

    只用小学这一层，是因为本次范围限定在小学核心五组。
    年级与册直接取 resources.json 的 grade / volume 字段，避免从标题里猜。
    """
    subject = common.sanitize_segment(record.get("subject") or "未知学科")
    edition = common.sanitize_segment(edition_of(record.get("id") or ""))
    grade = common.sanitize_segment(record.get("grade") or "未知年级")
    volume = common.sanitize_segment(record.get("volume") or "全册")
    return common.DOWNLOADS_ROOT / "videos" / "bilibili" / "小学" / f"{subject}-{edition}" / f"{grade}-{volume}"


def plan_videos(only_core: bool = True) -> list[dict]:
    """列出待下载合集，按学科-年级排序，便于逐年级推进。"""
    resources = common.load_resources()
    planned: list[dict] = []
    for record in resources.get("videos", []):
        if record.get("platform") != "bilibili":
            continue
        item_id = str(record.get("id") or "")
        if only_core and not item_id.startswith(CORE_PREFIXES):
            continue
        planned.append({
            "id": item_id,
            "bvid": record.get("bvid") or "",
            "url": record.get("url") or f"https://www.bilibili.com/video/{record.get('bvid')}",
            "title": record.get("title") or "",
            "subject": record.get("subject") or "",
            "grade": record.get("grade") or "",
            "volume": record.get("volume") or "",
            "pages": int(record.get("pages") or 0),
            "duration_seconds": int(record.get("duration_seconds") or 0),
            "target_dir": str(target_dir_for(record)),
        })
    # 学科顺序固定为 语文 -> 数学 -> 英语，同科内按年级与册排
    subject_order = {"语文": 0, "数学": 1, "英语": 2}
    grade_order = {"一年级": 1, "二年级": 2, "三年级": 3, "四年级": 4,
                   "五年级": 5, "六年级": 6}
    planned.sort(key=lambda item: (
        subject_order.get(item["subject"], 9),
        grade_order.get(item["grade"], 9),
        0 if item["volume"] == "上册" else 1,
    ))
    return planned


def page_number_width(total_pages: int) -> int:
    """按合集总 P 数决定 `[P###]` 的补零位数。

    56 P -> 2 位（P01..P56），100 P -> 3 位（P001..P100）。
    """
    if total_pages >= 1000:
        return 4
    if total_pages >= 100:
        return 3
    if total_pages >= 10:
        return 2
    return 1


def normalize_page_numbers(target_dir: pathlib.Path, total_pages: int) -> dict:
    """把目录里所有 `[P<n>]` 前缀统一成合集总 P 数对应的位数。

    BBDown 的 `<pageNumberWithZero>` 补零位数取决于**本次请求的 P 范围**，
    不是合集总 P 数。实测 100P 的合集全量下载得到 `[P001]`..`[P100]`，
    但 `-p 1,2` 只得到 `[P1]`、`[P2]`。用 `-p` 补下几个分P后，
    目录里就同时存在 `[P1] 标题.mp4` 与 `[P001] 标题.mp4` 两份。

    这里在每轮下载后统一前缀位数：
      - 目标文件名已存在且体积相同 -> 删掉这一份多余的
      - 目标文件名已存在但体积不同 -> 保留两份并记警告（可能内容真的不同）
      - 目标不存在 -> 重命名

    返回 {"renamed": n, "deduped": n, "conflicts": [names]}
    """
    width = page_number_width(total_pages)
    renamed = 0
    deduped = 0
    conflicts: list[str] = []
    if not target_dir.is_dir():
        return {"renamed": 0, "deduped": 0, "conflicts": []}

    for path in sorted(target_dir.glob("*.mp4")):
        match = PAGE_PREFIX_PATTERN.match(path.name)
        if not match:
            continue
        number = int(match.group(1))
        canonical = f"[P{number:0{width}d}]{path.name[match.end():]}"
        if canonical == path.name:
            continue
        destination = path.with_name(canonical)
        try:
            if destination.exists():
                if destination.stat().st_size == path.stat().st_size:
                    path.unlink()
                    deduped += 1
                else:
                    conflicts.append(path.name)
            else:
                path.rename(destination)
                renamed += 1
        except OSError:
            conflicts.append(path.name)
    return {"renamed": renamed, "deduped": deduped, "conflicts": conflicts}


def count_existing_pages(target_dir: pathlib.Path) -> int:
    """数该目录下已完成的 mp4。用于续传时算还差多少 P。

    只数顶层的 .mp4：BBDown 会在 work-dir 下建一个以 cid 命名的子目录
    存放封面缓存（如 `117114530759751/117114530759751.jpg`），
    递归数会把子目录里的东西也算进来，虽然扩展名不同不会误计，
    但顶层限定语义更清楚。
    """
    if not target_dir.is_dir():
        return 0
    return sum(1 for path in target_dir.glob("*.mp4") if path.stat().st_size > 0)


def cleanup_cover_cache(target_dir: pathlib.Path) -> None:
    """删掉 BBDown 留下的纯数字封面缓存目录。

    实测 BBDown 会在 work-dir 下建 `<cid>/` 目录，里面同时放：
      - `<cid>.jpg` 封面
      - `00000_<cid>.P<n>.<...>.vclip` 正在下载的分片
    所以判据必须严格：目录里**只有图片**才删。第一版判据只看扩展名白名单，
    结果把正在下载的 .vclip 分片也当成残留删了 —— 那些文件被进程占用，
    删除失败才没造成实际损失，但逻辑是错的。
    任何非图片文件的存在都说明这个目录正在被使用，必须跳过。
    """
    if not target_dir.is_dir():
        return
    image_suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    for child in target_dir.iterdir():
        if not child.is_dir() or not child.name.isdigit():
            continue
        files = [path for path in child.rglob("*") if path.is_file()]
        if not files:
            continue
        if all(path.suffix.lower() in image_suffixes for path in files):
            for path in files:
                try:
                    path.unlink()
                except OSError:
                    return          # 删不掉说明还在用，整个目录留着
            try:
                child.rmdir()
            except OSError:
                pass


def download_collection(item: dict, progress: common.Progress | None = None) -> dict:
    """下载一个合集的全部 P。已完成的 P 由 BBDown 自身跳过（它检查目标文件存在）。"""
    target_dir = pathlib.Path(item["target_dir"])
    target_dir.mkdir(parents=True, exist_ok=True)
    already = count_existing_pages(target_dir)
    if already >= item["pages"] > 0:
        return {
            "id": item["id"], "status": "skipped", "pages_done": already,
            "path": str(target_dir), "bytes": _dir_bytes(target_dir),
        }

    remaining_pages = max(item["pages"] - already, 1)
    # 用统一的码率假设换算剩余体积，再交给磁盘守卫判断
    avg_seconds = item["duration_seconds"] / item["pages"] if item["pages"] else 900
    estimated_bytes = int(remaining_pages * avg_seconds * ESTIMATED_BYTES_PER_SECOND)
    common.assert_disk_headroom(estimated_bytes, f"下载 {item['id']}")

    bbdown = find_bbdown()
    command = [
        str(bbdown),
        "--use-tv-api",
        "-e", BBDOWN_VIDEO_ENCODING_PRIORITY,
        "-q", BBDOWN_QUALITY_PRIORITY,
        "--skip-subtitle",
        "--delay-per-page", str(BBDOWN_PAGE_DELAY_SECONDS),
        "--work-dir", str(target_dir),
        "-M", PAGE_NAME_PATTERN,
        item["url"],
    ]

    last_error = ""
    for attempt in range(1, CONTAINER_RETRIES + 1):
        if progress:
            progress.set_current(f"video: {item['id']} ({item['pages']}P, 第 {attempt} 次)")
        completed = subprocess.run(
            command,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=CONTAINER_TIMEOUT_SECONDS,
            cwd=str(common.REPO_ROOT),
        )
        done_now = count_existing_pages(target_dir)
        # BBDown 偶尔在最后一 P 失败时返回非 0，但前面的 P 都成功了；
        # 所以判成功以「文件数是否达标」为主，退出码为辅。
        if done_now >= item["pages"] > 0 or completed.returncode == 0:
            cleanup_cover_cache(target_dir)
            # 统一 `[P###]` 补零位数：`-p` 补下会导致位数不一致，
            # 产生 `[P1]` 与 `[P001]` 两份同名内容
            normalize_page_numbers(target_dir, item["pages"])
            return {
                "id": item["id"], "status": "ok", "pages_done": count_existing_pages(target_dir),
                "path": str(target_dir), "bytes": _dir_bytes(target_dir),
            }
        last_error = (completed.stderr or completed.stdout or "").strip()[-500:]

    return {
        "id": item["id"], "status": "failed", "pages_done": count_existing_pages(target_dir),
        "path": str(target_dir), "error": last_error,
    }


def run(progress: common.Progress | None = None, only_core: bool = True) -> list[dict]:
    planned = plan_videos(only_core=only_core)
    if progress:
        progress.set_totals(
            item_total=len(planned),
            page_total=sum(item["pages"] for item in planned),
        )

    results: list[dict] = []
    consecutive_failures = 0
    for item in planned:
        try:
            result = download_collection(item, progress)
        except common.InsufficientDisk as disk_error:
            results.append({"id": item["id"], "status": "skipped_disk", "error": str(disk_error)})
            if progress:
                progress.record_error(str(disk_error))
            break
        except subprocess.TimeoutExpired:
            result = {"id": item["id"], "status": "failed",
                      "error": f"超时（{CONTAINER_TIMEOUT_SECONDS}s）",
                      "pages_done": count_existing_pages(pathlib.Path(item["target_dir"]))}
        except Exception as unexpected:  # noqa: BLE001
            result = {"id": item["id"], "status": "failed",
                      "error": f"{type(unexpected).__name__}: {unexpected}"}

        results.append(result)
        _append_manifest(result)
        if progress:
            # page_done 由各合集已完成 P 数汇总得出，而不是逐个累加 ——
            # 重跑时同一个合集会再次上报已完成的 P，直接累加会虚高。
            progress.state["page_done"] = sum(int(r.get("pages_done") or 0) for r in results)
            progress.state["bytes_done"] = sum(int(r.get("bytes") or 0) for r in results)
            if result["status"] in {"ok", "skipped"}:
                progress.state["item_done"] = int(progress.state.get("item_done") or 0) + 1
            else:
                progress.record_error(f"{result['id']}: {result.get('error', '')}")
            progress.flush()

        consecutive_failures = consecutive_failures + 1 if result["status"] == "failed" else 0
        if consecutive_failures >= 5:
            if progress:
                progress.record_error("连续 5 个合集失败，暂停视频阶段（可能是风控或网络）")
            break

    return results


def _append_manifest(record: dict) -> None:
    manifest_dir = common.DOWNLOADS_ROOT / "videos"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    entry = {"recorded_at": common.now_iso(), **record}
    with (manifest_dir / "_manifest.jsonl").open("a", encoding="utf-8") as manifest:
        manifest.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _dir_bytes(root: pathlib.Path) -> int:
    total = 0
    for path in root.rglob("*.mp4"):
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def probe_formats(url: str) -> list[str]:
    """用 --only-show-info 探测可用清晰度，返回以 `[720P` 等开头的行。

    这是脚本内唯一的「验证 720P 仍然可用」手段。B 站调整接口后，
    720P 可能退回 480P，此时应当停下而不是静默下一遍 480P。
    """
    bbdown = find_bbdown()
    completed = subprocess.run(
        [str(bbdown), "--use-tv-api", "-e", BBDOWN_VIDEO_ENCODING_PRIORITY,
         "-q", BBDOWN_QUALITY_PRIORITY, "--only-show-info", "-p", "1", url],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    return [line.strip() for line in (completed.stdout or "").splitlines() if re.search(r"\d+P", line)]
