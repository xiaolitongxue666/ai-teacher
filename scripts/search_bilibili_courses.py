#!/usr/bin/env python3
"""按国家审定教材的「版本 × 学科 × 年级 × 册别」矩阵，在 B站检索配套视频课程。

为什么需要这个脚本，而不是手工搜：
  1. 教材组合有几十格，手工搜完再逐条核对分P数要几个小时；
  2. B站搜索结果里混着高中教材、上册/下册串台、教资面试题，标题看着对但内容不对；
  3. 标题声称的集数经常与实际分P数不符，只有调接口才能拿到真值。

分类基准是**国家中小学智慧教育平台的教材目录**，不是 B站 的标签或 UP 主自述。
矩阵数据来自平台公开的 JSON 分片，无需登录：

    https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/resources/tch_material/version/data_version.json
    .../part_100.json  .../part_101.json  .../part_102.json

三条实测结论决定了检索策略：

    SSR 搜索页 search.bilibili.com/all   8/8 成功，只给 bvid + 标题
    view 接口 /x/web-interface/view      31/32 成功，给分P数与全量元数据
    wbi 搜索 /x/web-interface/wbi/search  5/8 成功，命中的话元数据最全

所以：SSR 保证召回确定性，wbi 争取元数据丰富度，view 负责最终核实。
`space/wbi/arc/search`（UP 主投稿列表）与 `yt-dlp bilisearch` 实测 412/-799，
不要浪费时间在这两条路上。

用法：
    python scripts/search_bilibili_courses.py              # 只报告，不写文件
    python scripts/search_bilibili_courses.py --write      # 写回 data/resources.json
    python scripts/search_bilibili_courses.py --grid       # 只打印教材矩阵
    python scripts/search_bilibili_courses.py --only 数学,英语
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html as html_module
import http.cookiejar
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
RESOURCES_PATH = REPO_ROOT / "data" / "resources.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 25
SEARCH_INTERVAL_SECONDS = 1.2
DETAIL_INTERVAL_SECONDS = 0.4
SEARCH_RETRIES = 3

# ── 教材矩阵来源 ────────────────────────────────────────────────
SMARTEDU_PART_TEMPLATE = "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/resources/tch_material/part_{page}.json"
SMARTEDU_PAGES = (100, 101, 102)

TARGET_SUBJECTS = ("语文", "数学", "英语")
TARGET_STAGE = "小学"

# 版本名在平台里的写法不完全统一，用「包含」匹配，并映射到统一的展示名。
# 语文在国家审定目录里只有统编版一个版本；所谓「人教版语文」就是统编版。
PUBLISHER_RULES: tuple[tuple[str, str, str], ...] = (
    # (学科, 平台标签包含的片段, 统一展示名)
    ("语文", "统编版", "统编版"),
    ("数学", "人教版", "人教版"),
    ("数学", "北师大版", "北师大版"),
    ("英语", "人教版（主编：吴欣）", "人教版"),
    ("英语", "北师大版", "北师大版"),
    ("英语", "外研社版（主编：刘兆义）", "外研社版"),
)

GRADE_ORDER = ("一年级", "二年级", "三年级", "四年级", "五年级", "六年级")
VOLUME_ORDER = ("上册", "下册")

# 平台目录里没有、但用户明确提供的条目。外研新交际是地方教材/校本教材，
# 不在国家审定目录里，二年级也没有任何国家审定英语教材。
MANUAL_SEEDS: tuple[dict, ...] = (
    {
        "id": "waiyan_xinjiaoji_english_g2_up",
        "platform": "bilibili",
        "bvid": "BV1eFmAY4Eq4",
        "publisher": "外研新交际（地方教材）",
        "subject": "英语",
        "grade": "二年级",
        "volume": "上册",
        "note": "外研社新交际英语，属地方/校本教材，不在国家中小学智慧教育平台的国家审定目录内。"
                "小学英语国家审定教材统一从三年级起，二年级没有审定版本。",
    },
)

# ── 标题打分 ────────────────────────────────────────────────────
# 实测反例，这两条解释了为什么负向词必须做：
#   BV11i4y1T7sS  「高中一年级数学上册 … 人教版A版必修二」
#                 含「一年级」「数学」「上册」「人教版」，正向满分，但它是高中教材
#   BV1mJK66VEoE  「北师大版四年级数学上册」
#                 出现在「四年级下册」的搜索结果里
NEGATIVE_TITLE_HINTS = (
    "高中", "初中", "七年级", "八年级", "九年级", "高一", "高二", "高三",
    "必修", "选修", "高考", "中考", "专升本", "考研",
    "教资", "面试", "笔试", "课件制作", "说课",
)
NEGATIVE_PENALTY = 8

# 学科串台是实测踩到的真实错误：查「北师大版 四年级 英语 下册」时，
# 排名第一的是 BV13p8S6iEx2「北师大版小学四年级数学下册同步课程」——
# 版本、年级、册别全中，只有学科是「数学」。必须显式排除。
ALL_SUBJECTS = ("语文", "数学", "英语")

# 分P数低于此阈值时视为「不是成套课程」：单词朗读、单节精讲、课文动画单条
# 都会命中标题关键词，但对「跟教材学一遍」没有价值。
MIN_COURSE_PAGES = 5
INSUFFICIENT_PAGES_PENALTY = 6

# 外研社小学英语在平台里按主编分成三个版本（孙有中 / 刘兆义 / 张祖春），
# 覆盖的年级不同。B站标题通常只写「外研版」，无法区分主编，但有时会写进副标题。
# 出现非目标主编时降权，避免把「孙有中版四年级」当成「刘兆义版四年级」。
EDITOR_HINTS = ("孙有中", "刘兆义", "张祖春", "苗兴伟", "吴欣")
EDITOR_MISMATCH_PENALTY = 6

# 纯音频类内容：单词朗读、课文朗读、音频、听力磨耳朵、点读。
# 这些是辅助材料，不是课程讲解；分P 数够也不该顶替主课程。
AUDIO_ONLY_HINTS = ("单词朗读", "单词音频", "课文朗读", "朗读音频", "听力磨耳朵", "点读音频")
AUDIO_ONLY_PENALTY = 5

EPISODE_PATTERN = re.compile(r"([0-9]{1,4})\s*[集课讲]")
EM_TAG_PATTERN = re.compile(r"<[^>]+>")
BVID_PATTERN = re.compile(r"BV[0-9A-Za-z]{10}")
TITLE_ATTR_PATTERN = re.compile(r'title="([^"]{6,200})"')

# wbi 签名用的固定混淆表（B站前端公开算法）
WBI_MIXIN_KEY_ORDER = (
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61,
    26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36,
    20, 34, 44, 52,
)


# ── 教材矩阵 ────────────────────────────────────────────────────

def fetch_textbook_records() -> list[dict]:
    """拉取智慧教育平台的教材记录。单份分片失败不影响其它分片。"""
    records: list[dict] = []
    for page in SMARTEDU_PAGES:
        url = SMARTEDU_PART_TEMPLATE.format(page=page)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                records.extend(json.loads(response.read().decode("utf-8")))
        except Exception as unexpected_error:  # noqa: BLE001 - 单分片失败要能继续
            print(f"  教材分片 {page} 拉取失败：{type(unexpected_error).__name__}", file=sys.stderr)
    return records


def record_tags(record: dict) -> dict[str, str]:
    """把 tag_list 摊平成 {维度: 名称}。维度见平台：zxxbb 版本 / zxxxk 学科 / zxxnj 年级 / zxxcc 册别。"""
    return {
        tag["tag_dimension_id"]: tag["tag_name"]
        for tag in (record.get("tag_list") or [])
        if tag.get("tag_dimension_id")
    }


def build_grid(records: list[dict]) -> list[dict]:
    """按目标学科与版本白名单筛出教材组合，返回 [{publisher, subject, grade, volume, official_title}]。"""
    grid: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for record in records:
        tags = record_tags(record)
        if tags.get("zxxxd") != TARGET_STAGE:
            continue
        subject = tags.get("zxxxk")
        if subject not in TARGET_SUBJECTS:
            continue
        platform_publisher = tags.get("zxxbb") or ""
        grade = tags.get("zxxnj") or ""
        volume = tags.get("zxxcc") or ""
        if grade not in GRADE_ORDER or volume not in VOLUME_ORDER:
            continue
        display_publisher = ""
        matched_editor = ""
        for rule_subject, fragment, display in PUBLISHER_RULES:
            if rule_subject == subject and fragment in platform_publisher:
                display_publisher = display
                # 外研社版/人教版英语按主编拆成多个平台条目，主编是区分键
                editor_match = re.search(r"主编[：:]\s*([^）)]+)", platform_publisher)
                matched_editor = editor_match.group(1).strip() if editor_match else ""
                break
        if not display_publisher:
            continue
        key = (display_publisher, subject, grade, volume, matched_editor)
        if key in seen:
            continue
        seen.add(key)
        grid.append({
            "publisher": display_publisher,
            "subject": subject,
            "grade": grade,
            "volume": volume,
            "editor": matched_editor,
            "official_title": (record.get("global_title") or {}).get("zh-CN", ""),
        })
    grid.sort(key=lambda cell: (
        TARGET_SUBJECTS.index(cell["subject"]),
        cell["publisher"],
        GRADE_ORDER.index(cell["grade"]),
        VOLUME_ORDER.index(cell["volume"]),
    ))
    return grid


PUBLISHER_SLUGS = {
    "统编版": "tongbian",
    "人教版": "renjiao",
    "北师大版": "beishida",
    "外研社版": "waiyanshe",
    "外研新交际（地方教材）": "waiyan_xinjiaoji",
}
SUBJECT_SLUGS = {"语文": "chinese", "数学": "math", "英语": "english"}
VOLUME_SLUGS = {"上册": "up", "下册": "down"}


def grid_cell_id(cell: dict) -> str:
    """稳定 id：{出版社}_{学科}_g{年级}_{册别}，例如 beishida_math_g2_up。"""
    publisher = PUBLISHER_SLUGS.get(cell["publisher"], "unknown")
    subject = SUBJECT_SLUGS[cell["subject"]]
    grade_number = GRADE_ORDER.index(cell["grade"]) + 1
    volume = VOLUME_SLUGS[cell["volume"]]
    return f"{publisher}_{subject}_g{grade_number}_{volume}"


def build_keyword(cell: dict) -> str:
    """检索关键词。带上「同步」是因为纯版本+年级会大量命中教案合集与电子课本翻页视频。"""
    return f"{cell['publisher']} {cell['grade']} {cell['subject']} {cell['volume']} 同步"


# ── 搜索通道 ────────────────────────────────────────────────────

def _build_http_opener() -> urllib.request.OpenerDirector:
    """带 CookieJar 的 opener。访问首页拿到 buvid3 与 b_nut 后才能调 wbi 接口。"""
    cookie_jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))


def _request_headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Referer": "https://search.bilibili.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }


def search_via_ssr(keyword: str) -> list[dict]:
    """抓搜索页 SSR HTML，用正则取 (bvid, 标题)。

    只给 bvid 与标题，没有元数据。但它实测 8/8 成功，是召回的主力通道。
    注意正则会误抓无效串（如 BVpAY3909LRs），所以结果必须再经 view 接口核实。
    """
    url = "https://search.bilibili.com/all?keyword=" + urllib.parse.quote(keyword)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            page = response.read().decode("utf-8", "replace")
    except Exception as unexpected_error:  # noqa: BLE001 - 失败要能回退到另一通道
        return []

    candidates: list[dict] = []
    seen_bvid: set[str] = set()
    for match in BVID_PATTERN.finditer(page):
        bvid = match.group(0)
        if bvid in seen_bvid:
            continue
        # 卡片结构里标题属性紧跟在封面之后，取 bvid 之后的一段窗口
        window = page[match.start(): match.start() + 1500]
        title_match = TITLE_ATTR_PATTERN.search(window)
        if not title_match:
            continue
        seen_bvid.add(bvid)
        candidates.append({
            "bvid": bvid,
            "title": html_module.unescape(title_match.group(1)),
            "source": "ssr",
        })
    return candidates


def _sign_wbi_params(opener: urllib.request.OpenerDirector, params: dict) -> str:
    """按 B站 wbi 算法签名。密钥来自 nav 接口返回的两张图名。"""
    nav_request = urllib.request.Request(
        "https://api.bilibili.com/x/web-interface/nav", headers=_request_headers()
    )
    with opener.open(nav_request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        nav = json.loads(response.read().decode("utf-8"))
    wbi_image = nav["data"]["wbi_img"]
    img_key = wbi_image["img_url"].rsplit("/", 1)[-1].split(".")[0]
    sub_key = wbi_image["sub_url"].rsplit("/", 1)[-1].split(".")[0]
    raw_key = img_key + sub_key
    mixin_key = "".join(raw_key[index] for index in WBI_MIXIN_KEY_ORDER)[:32]

    params["wts"] = int(time.time())
    # 文档要求的字符过滤：只剔除 !'()*
    filtered = [
        (key, "".join(char for char in str(value) if char not in "!'()*"))
        for key, value in sorted(params.items())
    ]
    query = urllib.parse.urlencode(filtered)
    params["w_rid"] = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return urllib.parse.urlencode(sorted(params.items()))


def search_via_wbi(keyword: str, opener: urllib.request.OpenerDirector) -> list[dict]:
    """走 wbi 搜索接口。实测只有 5/8 命中，命中时元数据最全（含播放量、时长、UP 主）。

    失败时 data 里只有一个 v_voucher 字段，没有 result，直接返回空让上层回退。
    标题里的 <em class="keyword"> 高亮标签必须剥掉，否则关键词匹配失效。
    """
    params = {"search_type": "video", "keyword": keyword, "page": 1}
    try:
        query_string = _sign_wbi_params(opener, params)
        url = "https://api.bilibili.com/x/web-interface/wbi/search/type?" + query_string
        request = urllib.request.Request(url, headers=_request_headers())
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - 该通道不稳定，失败即回退
        return []

    if body.get("code") != 0:
        return []
    candidates: list[dict] = []
    for item in (body.get("data") or {}).get("result") or []:
        bvid = item.get("bvid")
        if not bvid:
            continue
        candidates.append({
            "bvid": bvid,
            "title": EM_TAG_PATTERN.sub("", item.get("title") or ""),
            "source": "wbi",
            "play": item.get("play"),
            "duration_text": item.get("duration"),
            "author": item.get("author"),
            "mid": item.get("mid"),
            "pubdate": item.get("pubdate"),
        })
    return candidates


def fetch_video_detail(bvid: str) -> dict | None:
    """调 view 接口拿真实分P数与元数据。失败返回 None（bvid 无效或限流）。"""
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Referer": "https://www.bilibili.com"}
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - 无效 bvid 与网络失败同样处理
        return None
    if body.get("code") != 0:
        return None
    data = body.get("data") or {}
    owner = data.get("owner") or {}
    stat = data.get("stat") or {}
    return {
        "title": data.get("title") or "",
        "pages": data.get("videos") or 0,
        "duration_seconds": data.get("duration") or 0,
        "uploader": owner.get("name") or "",
        "uploader_mid": str(owner.get("mid") or ""),
        "pubdate": dt.datetime.fromtimestamp(data.get("pubdate") or 0).strftime("%Y-%m-%d"),
        "play": stat.get("view") or 0,
        "favorites": stat.get("favorite") or 0,
        "bvid": data.get("bvid") or bvid,
    }


# ── 打分 ────────────────────────────────────────────────────────

def volume_matches(title: str, cell: dict) -> bool:
    """册别必须对得上。

    实测错误：查「北师大版 四年级 英语 下册」时命中 BV1GmgQ6bEbz
    「北师大英语四年级上册」——出版社、年级、学科全中，只有册别是上册。
    光靠扣分它仍能拿到正分，所以册别做成硬门槛。

    同时描述上下册的合集（「五年级英语上册下册」）视为通过，
    因为这类视频确实覆盖目标册，只是不专一，会在 note 里标注。
    """
    cleaned = EM_TAG_PATTERN.sub("", title)
    expected = cell["volume"]
    other = "下册" if expected == "上册" else "上册"
    if expected in cleaned:
        return True
    # 只写了另一册，且没有目标册 → 排除
    return other not in cleaned


def publisher_matches(title: str, cell: dict) -> bool:
    """标题里必须出现目标出版社的名字，否则直接排除。

    这是硬门槛，不是扣分项。实测教训：查「北师大版 六年级 英语 上册」时，
    排序靠前的是 BV1uNgK68EBd「湘少版小学六年级英语上册同步课程」——
    年级、册别、学科全中，只有出版社是湘少版。光靠扣分压不住，必须直接排除。
    """
    cleaned = EM_TAG_PATTERN.sub("", title)
    publisher = cell["publisher"]
    if publisher in cleaned:
        return True
    if publisher == "统编版":
        return "部编" in cleaned or "统编" in cleaned or "人教" in cleaned
    if publisher == "外研社版":
        return "外研" in cleaned
    if publisher == "人教版":
        return "人教版" in cleaned or "人教PEP" in cleaned or "PEP" in cleaned
    if publisher == "北师大版":
        return "北师大" in cleaned
    if publisher.startswith("外研新交际"):
        return "外研" in cleaned or "新交际" in cleaned
    return False


def score_title(title: str, cell: dict) -> int:
    """标题与目标格子的匹配度。

    负向词的权重高于所有正向项之和，确保跨学段误命中被压下去。
    学科串台单独处理：标题里出现其它学科名时直接压倒性扣分。
    """
    cleaned = EM_TAG_PATTERN.sub("", title)
    score = 0
    if cell["publisher"] in cleaned:
        score += 4
    elif cell["publisher"] == "统编版" and ("部编" in cleaned or "统编" in cleaned):
        score += 4
    elif cell["publisher"] == "外研社版" and "外研" in cleaned:
        score += 4
    if cell["grade"] in cleaned:
        score += 2
    if cell["subject"] in cleaned:
        score += 2

    # 学科串台：查英语却命中数学视频，实测真实发生过
    for other_subject in ALL_SUBJECTS:
        if other_subject != cell["subject"] and other_subject in cleaned:
            score -= NEGATIVE_PENALTY
            break

    expected_volume = cell["volume"]
    other_volume = "下册" if expected_volume == "上册" else "上册"
    if expected_volume in cleaned:
        score += 1
    elif other_volume in cleaned:
        score -= NEGATIVE_PENALTY

    for hint in NEGATIVE_TITLE_HINTS:
        if hint in cleaned:
            score -= NEGATIVE_PENALTY
            break

    # 主编串台：目标是刘兆义版却命中孙有中版四年级，实测存在
    for editor in EDITOR_HINTS:
        if editor in cleaned and editor not in cell.get("editor", ""):
            score -= EDITOR_MISMATCH_PENALTY
            break

    # 纯音频内容不顶替课程
    for hint in AUDIO_ONLY_HINTS:
        if hint in cleaned:
            score -= AUDIO_ONLY_PENALTY
            break

    if EPISODE_PATTERN.search(cleaned):
        score += 2
    return score


def claimed_episode_count(title: str) -> int | None:
    """从标题里抽「62集」「83集」这类声称集数，用于跟实际分P数对比。"""
    match = EPISODE_PATTERN.search(title)
    if not match:
        return None
    value = int(match.group(1))
    return value if 1 <= value <= 2000 else None


# ── 单格检索 ────────────────────────────────────────────────────

def search_cell(cell: dict, opener: urllib.request.OpenerDirector, used_bvids: set[str]) -> dict:
    """检索一个格子并核实。返回 {status, candidate, scanned, error}。

    used_bvids 跨格共享，记录已被其它格子占用的 bvid。
    实测教训：人教版五年级上册与下册都命中了 BV1NCph69EcV
    （标题是「五年级上册+下册 全90集」），同一视频占两格没有意义，
    上下册不同的格子必须拿到不同的视频。
    """
    keyword = build_keyword(cell)
    candidates = search_via_wbi(keyword, opener)
    time.sleep(SEARCH_INTERVAL_SECONDS)
    if not candidates:
        # wbi 实测只有 5/8 命中，空返回是常态，不是异常
        candidates = search_via_ssr(keyword)
        time.sleep(SEARCH_INTERVAL_SECONDS)

    if not candidates:
        return {"status": "miss", "candidate": None, "scanned": 0, "error": "两条通道均无结果"}

    ranked = sorted(
        (
            item for item in candidates
            if publisher_matches(item["title"], cell) and volume_matches(item["title"], cell)
        ),
        key=lambda item: -score_title(item["title"], cell),
    )
    if not ranked:
        return {
            "status": "miss",
            "candidate": None,
            "scanned": 0,
            "error": f"没有同时满足「{cell['publisher']}」与「{cell['volume']}」的候选",
        }
    scanned = 0
    rejected_for_size: list[str] = []
    rejected_duplicate: list[str] = []
    for candidate in ranked[:8]:
        if score_title(candidate["title"], cell) <= 0:
            break
        scanned += 1
        if candidate["bvid"] in used_bvids:
            rejected_duplicate.append(candidate["bvid"])
            continue
        detail = fetch_video_detail(candidate["bvid"])
        time.sleep(DETAIL_INTERVAL_SECONDS)
        if detail is None:
            continue
        # 单词朗读、单节精讲、课文动画单条都只有 1-2 个分P，
        # 标题能命中关键词但不是成套课程，跳过并记录。
        if (detail.get("pages") or 0) < MIN_COURSE_PAGES:
            rejected_for_size.append(f"{candidate['bvid']}({detail.get('pages')}P)")
            continue
        used_bvids.add(candidate["bvid"])
        return {
            "status": "ok",
            "candidate": {**candidate, **detail},
            "scanned": scanned,
            "error": "",
        }
    reason = "候选被负向过滤或 view 核实失败"
    if rejected_for_size:
        reason = f"候选分P均少于 {MIN_COURSE_PAGES}，已跳过：{'、'.join(rejected_for_size[:3])}"
    if rejected_duplicate:
        reason = f"候选已被其它格子占用：{'、'.join(rejected_duplicate[:3])}"
    return {
        "status": "miss",
        "candidate": None,
        "scanned": scanned,
        "error": reason,
    }


def build_entry(cell: dict, result: dict, stamp: str) -> dict:
    """把检索结果组装成 videos 分区的记录。"""
    candidate = result["candidate"]
    actual_title = candidate.get("title") or ""
    notes: list[str] = []

    claimed = claimed_episode_count(actual_title)
    pages = candidate.get("pages") or 0
    if claimed and pages and claimed != pages:
        notes.append(f"标题称 {claimed} 集，实际 {pages} 个分P")

    # 标题同时写了上下册：视频覆盖目标册，但不专一，使用者需要自行定位分P
    cleaned_title = EM_TAG_PATTERN.sub("", actual_title)
    if "上册" in cleaned_title and "下册" in cleaned_title:
        notes.append("标题同时含上/下册，属合并合集，需按分P名定位目标册")

    if (pages or 0) < 10:
        notes.append(f"仅 {pages} 个分P，覆盖度可能不足")

    if cell.get("editor"):
        notes.append(f"平台登记主编：{cell['editor']}")

    if cell["publisher"].startswith("外研新交际"):
        notes.append("地方/校本教材，不在国家审定目录")

    entry = {
        "id": grid_cell_id(cell),
        "platform": "bilibili",
        "bvid": candidate["bvid"],
        "title": actual_title,
        "publisher": cell["publisher"],
        "subject": cell["subject"],
        "grade": cell["grade"],
        "volume": cell["volume"],
        "editor": cell.get("editor") or "",
        "pages": pages,        "duration_seconds": candidate.get("duration_seconds") or 0,
        "uploader": candidate.get("uploader") or "",
        "uploader_mid": str(candidate.get("uploader_mid") or ""),
        "pubdate": candidate.get("pubdate") or "",
        "play": candidate.get("play") or 0,
        "url": f"https://www.bilibili.com/video/{candidate['bvid']}",
        "verified": "ok",
        "checked_at": stamp,
    }
    if notes:
        entry["note"] = "；".join(notes)
    return entry


def build_manual_entry(seed: dict, stamp: str) -> dict | None:
    """人工种子条目：仍要过 view 接口核实，拿不到就不写。"""
    detail = fetch_video_detail(seed["bvid"])
    time.sleep(DETAIL_INTERVAL_SECONDS)
    if detail is None:
        return None
    entry = {
        "id": seed["id"],
        "platform": seed["platform"],
        "bvid": seed["bvid"],
        "title": detail["title"],
        "publisher": seed["publisher"],
        "subject": seed["subject"],
        "grade": seed["grade"],
        "volume": seed["volume"],
        "pages": detail["pages"],
        "duration_seconds": detail["duration_seconds"],
        "uploader": detail["uploader"],
        "uploader_mid": detail["uploader_mid"],
        "pubdate": detail["pubdate"],
        "play": detail["play"],
        "url": f"https://www.bilibili.com/video/{seed['bvid']}",
        "verified": "ok",
        "checked_at": stamp,
    }
    if seed.get("note"):
        entry["note"] = seed["note"]
    return entry


def write_videos_section(entries: list[dict], stamp: str) -> int:
    """合并写入 data/resources.json 的 videos 分区，位置在 repos 之后。

    幂等规则：同 id 已存在时只刷新 verified / checked_at 与指标字段，
    不覆盖已人工修改过的 note。

    并发安全：每次写入前重新读盘（不用缓存），避免另一个进程刚写的分区被覆盖。
    """
    data = json.loads(RESOURCES_PATH.read_text(encoding="utf-8"))
    existing = {item["id"]: item for item in data.get("videos", [])}
    added = 0
    for entry in entries:
        if entry["id"] in existing:
            current = existing[entry["id"]]
            for key in ("verified", "checked_at", "pages", "duration_seconds", "play", "title", "url"):
                current[key] = entry[key]
        else:
            existing[entry["id"]] = entry
            added += 1

    ordered = list(existing.values())
    ordered.sort(key=lambda item: (
        TARGET_SUBJECTS.index(item["subject"]) if item["subject"] in TARGET_SUBJECTS else 99,
        item["publisher"],
        GRADE_ORDER.index(item["grade"]) if item["grade"] in GRADE_ORDER else 99,
        VOLUME_ORDER.index(item["volume"]) if item["volume"] in VOLUME_ORDER else 99,
    ))

    # 按原文件顺序重建，videos 插到 repos 之后；其余分区原样保留，
    # 包括本脚本不认识的 tutoring 等分区。
    rebuilt: dict = {}
    inserted = False
    for key, value in data.items():
        if key == "videos":
            continue
        rebuilt[key] = value
        if key == "repos":
            rebuilt["videos"] = ordered
            inserted = True
    if not inserted:
        rebuilt["videos"] = ordered

    rebuilt["checked_at"] = stamp
    RESOURCES_PATH.write_text(json.dumps(rebuilt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="按国家审定教材矩阵检索 B站配套视频课程")
    parser.add_argument("--write", action="store_true", help="写回 data/resources.json 的 videos 分区")
    parser.add_argument("--json-out", default="", help="另存一份结果 JSON 到指定路径，便于并发写入冲突时恢复")
    parser.add_argument("--from-json", default="", help="跳过检索，直接从这个 JSON 写入 videos 分区")
    parser.add_argument("--grid", action="store_true", help="只打印教材矩阵，不检索")
    parser.add_argument("--only", default="", help="只跑指定学科，逗号分隔：语文,数学,英语")
    arguments = parser.parse_args()

    print("拉取教材目录（国家中小学智慧教育平台，无需登录）...")
    records = fetch_textbook_records()
    if not records:
        print("教材目录拉取失败，退出", file=sys.stderr)
        return 1
    grid = build_grid(records)
    print(f"教材记录 {len(records)} 条 -> 目标矩阵 {len(grid)} 格\n")

    if arguments.grid:
        for cell in grid:
            print(f"  {grid_cell_id(cell):32} {cell['publisher']:6} {cell['subject']} {cell['grade']} {cell['volume']}")
        print(f"\n另有 {len(MANUAL_SEEDS)} 条人工种子（不在国家审定目录）：")
        for seed in MANUAL_SEEDS:
            print(f"  {seed['id']:32} {seed['publisher']} {seed['subject']} {seed['grade']} {seed['volume']}")
        return 0

    only_subjects = {name.strip() for name in arguments.only.split(",") if name.strip()}
    if only_subjects:
        grid = [cell for cell in grid if cell["subject"] in only_subjects]

    # 从已有结果 JSON 恢复写入，不重新检索
    if arguments.from_json:
        payload = json.loads(pathlib.Path(arguments.from_json).read_text(encoding="utf-8"))
        stamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        added = write_videos_section(payload, stamp)
        print(f"从 {arguments.from_json} 恢复：新增 {added} 条，当前共 {len(payload)} 条")
        return 0

    opener = _build_opener()
    stamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    entries: list[dict] = []
    misses: list[tuple[str, str]] = []
    used_bvids: set[str] = set()

    for index, cell in enumerate(grid, 1):
        cell_id = grid_cell_id(cell)
        print(f"[{index}/{len(grid)}] {cell_id}  {build_keyword(cell)}")
        result = search_cell(cell, opener, used_bvids)
        if result["status"] == "ok":
            entry = build_entry(cell, result, stamp)
            entries.append(entry)
            print(f"       -> {entry['bvid']}  {entry['pages']} 分P  {entry['title'][:46]}")
        else:
            misses.append((cell_id, result["error"]))
            print(f"       -> 未找到（{result['error']}）")

    for seed in MANUAL_SEEDS:
        if only_subjects and seed["subject"] not in only_subjects:
            continue
        entry = build_manual_entry(seed, stamp)
        if entry:
            entries.append(entry)
            print(f"[种子] {entry['id']}  -> {entry['bvid']}  {entry['pages']} 分P")
        else:
            misses.append((seed["id"], "view 核实失败（bvid 可能失效）"))

    print(f"\n命中 {len(entries)} 格，未找到 {len(misses)} 格")
    if misses:
        print("未找到：")
        for cell_id, reason in misses:
            print(f"  - {cell_id}: {reason}")

    if arguments.json_out:
        out_path = pathlib.Path(arguments.json_out)
        out_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n结果已另存：{out_path}")

    if arguments.write:
        added = write_videos_section(entries, stamp)
        print(f"\n已写入 videos 分区：新增 {added} 条，当前共 {len(entries)} 条命中记录")
    else:
        print("\n只报告，未写文件。加 --write 回写 data/resources.json。")

    return 0


def _build_opener() -> urllib.request.OpenerDirector:
    """先访问首页拿 Cookie，wbi 接口需要 buvid3。"""
    opener = _build_http_opener()
    try:
        opener.open(
            urllib.request.Request("https://www.bilibili.com", headers=_request_headers()),
            timeout=REQUEST_TIMEOUT_SECONDS,
        ).read()
    except Exception:  # noqa: BLE001 - 拿不到 Cookie 时 wbi 会失败，SSR 仍可用
        pass
    return opener


if __name__ == "__main__":
    raise SystemExit(main())
