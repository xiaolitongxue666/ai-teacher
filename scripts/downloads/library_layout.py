#!/usr/bin/env python3
"""把一条已有相对路径映到课程槽位。

下载续传认的是「目标路径上文件在且字节数一致」。搬迁脚本和夸克 / B站
落盘必须调用这里的同一个函数，否则重跑会把已经下完的文件判成缺失。

槽位只从路径和文件名读，不打开 PDF。读不出年级的材料进「跨年级」，
不复制到六个年级；完全对不上来源的进 `_unsorted`，不丢文件。
"""

from __future__ import annotations

import pathlib
import re
from dataclasses import dataclass

from . import common

LIBRARY_DIRNAME = "library"

# 文件名里的「1下」「一年级上册」才是这一份材料的册次。
# 父目录常见「1-6上册」「3-6上册」，那是一叠分册放在一起，不能盖过文件名。
# 「年级」必须写成 (?:年级)?。写成 年级? 只是「年」加可选的「级」，
# 「3-6上册」里没有「年」，整段范围会匹配失败，退回去把「6上」当成六年级。
_RANGE_GRADE = re.compile(
    r"([1-6])\s*(?:-|~|～|到|至)\s*([1-6])\s*(?:年级)?\s*(上下|上|下)?\s*册?"
)
_SINGLE_GRADE = re.compile(r"([1-6一二三四五六])年级")
# 「一年级语文上册」的册次和年级之间隔着学科名，册次单独找。
_VOLUME_MARK = re.compile(r"(上下|上|下)册")
# 「五三全优卷1下数学」这种不写「年级」也不写「册」的册次。前面不能是数字，避免吃掉年份。
_COMPACT_GRADE = re.compile(r"(?<!\d)([1-6])\s*(上|下)(?!\d)")
# 「语文一下」「部编 一上」：年级用汉字，中间没有「年级」二字。
_CN_COMPACT_GRADE = re.compile(r"([一二三四五六])(上|下)册?")
# 「西1数上」：版本简称 + 年级数字 + 数 + 上下。
_SUBJECT_COMPACT_GRADE = re.compile(r"(?<!\d)([1-6])数(上|下)")
# 教辅压缩册次：1A = 一年级上册，3B = 三年级下册。只认独立的「数字+A/B」，
# 不把「5.5 两位数」这种课时序号当成年级。
_AB_VOLUME = re.compile(r"(?<![0-9A-Za-z])([1-6])([ABab])(?![0-9A-Za-z])")
_YEAR_TOKEN = re.compile(r"(?<!\d)(20[12]\d|[12]\d)(春|秋)")
_VIDEO_ID = re.compile(
    r"^(tongbian|renjiao|beishida|waiyanshe)_(chinese|math|english)_g([1-6])_(up|down)$"
)

_CN = {
    "1": "一", "2": "二", "3": "三", "4": "四", "5": "五", "6": "六",
    "一": "一", "二": "二", "三": "三", "四": "四", "五": "五", "六": "六",
}
_VIDEO_EDITION = {
    "tongbian": "统编版",
    "renjiao": "人教版",
    "beishida": "北师大版",
    "waiyanshe": "外研社版",
}
_VIDEO_SUBJECT = {"chinese": "语文", "math": "数学", "english": "英语"}
_VIDEO_VOLUME = {"up": "上册", "down": "下册"}
_VIDEO_GRADE = {str(number): f"{_CN[str(number)]}年级" for number in range(1, 7)}

# 数学包的第二层是版本目录，文件夹名和规范名不完全一致（「北师大」没有「版」）。
_MATH_FOLDER = {
    "人教版": "人教版",
    "北师大": "北师大版",
    "北师大版": "北师大版",
    "苏教版": "苏教版",
    "西师大": "西师大版",
    "西师大版": "西师大版",
    "冀教版": "冀教版",
    "青岛版": "青岛版",
    "BJ版": "BJ版",
    "BJ": "BJ版",
    "通用版": "通用版",
}
_SCIENCE_FOLDER = {
    "人教鄂教版": "人教鄂教版",
    "冀人版": "冀人版",
    "大象版": "大象版",
    "教科版": "教科版",
    "湘科版": "湘科版",
    "苏教版": "苏教版",
    "青岛版": "青岛版",
}

# 先匹配更具体的用途，避免「归类复习」落到「练习」、「口算天天练」落到「天天练」。
_ROLE_RULES = (
    ("字帖", ("字帖", "描红")),
    ("预习", ("预习",)),
    ("默写背记", ("默写", "背记", "背诵", "看拼音", "必背", "晨读晚背", "速记")),
    ("试卷", ("全优卷", "测试卷", "名卷", "试卷", "好卷", "练习卷", "通关卷",
             "特色卷", "考卷", "练加考", "测评卷", "调研卷", "活页卷")),
    ("复习冲刺", ("期末", "归类复习", "冲刺", "小升初", "总复习", "复习", "自查", "过关", "闯关")),
    ("教材解读", ("教材全解", "一点通", "教材解读", "课堂笔记", "全解",
                 "教材巧解", "导学案", "知识清单", "知识梳理", "知识归纳", "笔记",
                 "考点清单", "考点梳理", "思维导图", "答案", "划重点", "核心课堂",
                 "导图", "手册")),
    ("专项", ("写作", "习作", "阅读", "口算", "实验", "语法", "专项", "提优", "易错", "计算")),
    ("同步练习", ("天天练", "练习帮", "一遍过", "课时练", "课时", "课堂作业",
                 "学练考", "作业本", "课后练习", "基础性作业", "训练",
                 "练习册", "同步练习", "练霸", "一起练习", "随堂练", "同步精练",
                 "左记右练", "精品教辅", "七彩课堂", "课后习题", "学习任务单", "小纸条",
                 "练+考", "讲练测", "学霸作业", "每日一练", "作业纸")),
)

# 课标文件名里的学科。长名字放前面，避免「生物学」被「生物」截断。
_CURRICULUM_SUBJECTS = (
    "道德与法治", "思想政治", "信息科技", "信息技术", "通用技术", "生物学",
    "语文", "数学", "英语", "科学", "物理", "化学", "生物", "历史", "地理",
    "体育", "艺术", "劳动", "俄语", "日语", "政治", "音乐", "美术", "课程方案",
)

_WORKBOOKS = {
    "p_chn": ("语文", "tongbian"),
    "p_morality": ("道法", "tongbian"),
    "p_math": ("数学", "math"),
    "p_sci": ("科学", "science"),
    "p_eng": ("英语", "english"),
}


@dataclass(frozen=True)
class Placement:
    """一条文件在资料库里的位置。`relative` 相对 `downloads/library/`。"""

    source_id: str
    stage: str
    subject: str
    edition: str
    grade: str
    volume: str
    role: str
    series: str
    unsorted: bool
    series_relative: pathlib.Path
    relative: pathlib.Path


def place(source_id: str, relative: str) -> Placement:
    """由来源 id 和现有相对路径得到槽位。视频 id 只取文件名，不把旧目录嵌进来。"""
    parts = _parts(relative)
    source_id = str(source_id or "")
    if _VIDEO_ID.match(source_id):
        filename = parts[-1] if parts else "未命名"
        return _place_video_identity(source_id, filename, source_id=source_id)
    if source_id == "j_curriculum":
        return _place_curriculum(source_id, parts)
    if source_id == "fan_geometry_900":
        return _place_fan(source_id, parts)
    if source_id == "phonics_270":
        return _place_phonics(source_id, parts)
    if source_id == "primary_1000_words":
        return _place_words(source_id, parts)
    workbook = _WORKBOOKS.get(source_id)
    if workbook:
        subject, mode = workbook
        return _place_workbook(source_id, subject, mode, parts)
    return _place_unsorted(source_id, parts)


def destination_for(source_id: str, relative: str) -> pathlib.Path:
    """该文件应落盘的绝对路径。"""
    return common.DOWNLOADS_ROOT / LIBRARY_DIRNAME / place(source_id, relative).relative


def video_directory(record: dict) -> pathlib.Path:
    """一个 B 站合集的目录。年级和册取记录字段，不从标题猜。"""
    placed = place_video(record)
    return common.DOWNLOADS_ROOT / LIBRARY_DIRNAME / placed.series_relative


def place_video(record: dict, filename: str = "") -> Placement:
    """用 resources.json 里的学科 / 年级 / 册覆盖 id 解码结果。版本仍从 id 前缀取。"""
    item_id = str(record.get("id") or "")
    decoded = _decode_video(item_id)
    subject = str(record.get("subject") or decoded["subject"] or "未知学科")
    grade = str(record.get("grade") or decoded["grade"] or "未知年级")
    volume = str(record.get("volume") or decoded["volume"] or "全册")
    edition = decoded["edition"] or "其他版"
    return _video_placement(
        source_id=item_id,
        subject=subject,
        edition=edition,
        grade=grade,
        volume=volume,
        series=item_id or "未知合集",
        filename=filename,
        unsorted=not bool(decoded["edition"]),
    )


def _place_video_identity(item_id: str, filename: str, source_id: str) -> Placement:
    decoded = _decode_video(item_id)
    if not decoded["edition"]:
        return _place_unsorted(source_id, _parts(filename))
    return _video_placement(
        source_id=source_id,
        subject=decoded["subject"],
        edition=decoded["edition"],
        grade=decoded["grade"],
        volume=decoded["volume"],
        series=item_id,
        filename=filename,
        unsorted=False,
    )


def _video_placement(source_id: str, subject: str, edition: str, grade: str,
                     volume: str, series: str, filename: str, unsorted: bool) -> Placement:
    series_relative = _path(
        "小学", subject, edition, grade, volume, "同步课", series,
    )
    relative = series_relative
    leaf = pathlib.PurePosixPath(filename).name if filename else ""
    if leaf:
        relative = series_relative / common.sanitize_segment(leaf)
    return Placement(
        source_id=source_id, stage="小学", subject=common.sanitize_segment(subject),
        edition=edition, grade=grade, volume=volume, role="同步课", series=series,
        unsorted=unsorted, series_relative=series_relative, relative=relative,
    )


def _decode_video(item_id: str) -> dict[str, str]:
    match = _VIDEO_ID.match(item_id)
    if not match:
        return {"edition": "", "subject": "", "grade": "", "volume": ""}
    edition_key, subject_key, grade_number, volume_key = match.groups()
    return {
        "edition": _VIDEO_EDITION[edition_key],
        "subject": _VIDEO_SUBJECT[subject_key],
        "grade": _VIDEO_GRADE[grade_number],
        "volume": _VIDEO_VOLUME[volume_key],
    }


def _place_workbook(source_id: str, subject: str, mode: str, parts: list[str]) -> Placement:
    if not parts:
        return _place_unsorted(source_id, parts)
    edition, skip_edition_folder = _edition_of(mode, parts)
    series_raw, tail = _series_and_tail(parts, skip_edition_folder)
    grade, volume = _grade_and_volume(parts)
    role = _role_of(series_raw)
    year = _year_token("/".join(parts))
    series = _series_label(series_raw, year)
    grade_slot = grade or "跨年级"
    volume_slot = volume or "全册"
    series_relative = _path(
        "小学", subject, edition, grade_slot, volume_slot, role, series,
    )
    relative = _with_tail(series_relative, tail)
    return Placement(
        source_id=source_id, stage="小学", subject=subject, edition=edition,
        grade=grade, volume=volume, role=role, series=series, unsorted=False,
        series_relative=series_relative, relative=relative,
    )


def _place_fan(source_id: str, parts: list[str]) -> Placement:
    filename = parts[-1] if parts else "未命名"
    topic = _fan_topic(filename)
    series_relative = _path("小学", "数学", "通用", "思维专题", topic)
    relative = series_relative / common.sanitize_segment(filename)
    return Placement(
        source_id=source_id, stage="小学", subject="数学", edition="通用",
        grade="", volume="", role="思维专题", series=topic, unsorted=False,
        series_relative=series_relative, relative=relative,
    )


def _place_phonics(source_id: str, parts: list[str]) -> Placement:
    head = parts[0] if parts else ""
    tail = parts[1:] if len(parts) > 1 else parts
    if "幼小衔接" in head or (head and "数学" in head and "拼读" not in head):
        subject, role, series = "数学", "幼小衔接", "幼小衔接数学"
    else:
        subject, role, series = "英语", "自然拼读", "Z自然拼读作业纸"
    series_relative = _path("小学", subject, "通用", role, series)
    relative = _with_tail(series_relative, tail or [head or "未命名"])
    return Placement(
        source_id=source_id, stage="小学", subject=subject, edition="通用",
        grade="", volume="", role=role, series=series, unsorted=False,
        series_relative=series_relative, relative=relative,
    )


def _place_words(source_id: str, parts: list[str]) -> Placement:
    filename = parts[-1] if parts else "未命名"
    series_relative = _path("小学", "英语", "通用", "词汇", "小学1000词")
    relative = series_relative / common.sanitize_segment(filename)
    return Placement(
        source_id=source_id, stage="小学", subject="英语", edition="通用",
        grade="", volume="", role="词汇", series="小学1000词", unsorted=False,
        series_relative=series_relative, relative=relative,
    )


def _place_curriculum(source_id: str, parts: list[str]) -> Placement:
    blob = "/".join(parts)
    if "普通高中" in blob:
        bucket = "普通高中"
    elif "义务教育" in blob:
        bucket = "义务教育"
    else:
        bucket = "未知学段"
    year = "未知年份"
    for part in parts[:-1]:
        found = re.findall(r"20\d{2}", part)
        if found:
            year = found[-1]
    filename = parts[-1] if parts else "未命名"
    subject = ""
    for name in _CURRICULUM_SUBJECTS:
        if name in filename:
            subject = name
            break
    if not subject:
        for name in _CURRICULUM_SUBJECTS:
            if name in blob:
                subject = name
                break
    series_relative = _path("课标", bucket, year)
    relative = series_relative / common.sanitize_segment(filename)
    return Placement(
        source_id=source_id, stage="课标", subject=subject, edition="",
        grade="", volume="", role="课标", series=year, unsorted=False,
        series_relative=series_relative, relative=relative,
    )


def _place_unsorted(source_id: str, parts: list[str]) -> Placement:
    safe_id = common.sanitize_segment(source_id or "未知来源")
    tail = [_seg(part) for part in parts] or ["未命名"]
    relative = pathlib.Path("_unsorted", safe_id, *tail)
    return Placement(
        source_id=source_id, stage="", subject="", edition="", grade="",
        volume="", role="", series="", unsorted=True,
        series_relative=pathlib.Path("_unsorted", safe_id), relative=relative,
    )


def _edition_of(mode: str, parts: list[str]) -> tuple[str, bool]:
    """返回 (规范版本名, 第一段是不是版本目录)。

    语文和道法在国家审定目录里只有统编，路径里的「人教版」不采用。
    """
    head = parts[0] if parts else ""
    if mode == "tongbian":
        return "统编版", False
    if mode == "math":
        edition = _MATH_FOLDER.get(head, "")
        return (edition, True) if edition else ("通用版", False)
    if mode == "science":
        edition = _SCIENCE_FOLDER.get(head, "")
        return (edition, True) if edition else ("通用版", False)
    blob = "/".join(parts)
    if "外研" in blob:
        return "外研社版", False
    if "人教" in blob or "PEP" in blob.upper():
        return "人教版", False
    return "通用", False


def _series_and_tail(parts: list[str], skip_edition_folder: bool) -> tuple[str, list[str]]:
    start = 1 if skip_edition_folder else 0
    if start >= len(parts) - 1:
        return "未命名系列", parts[start:] or parts
    return parts[start], parts[start + 1:]


def _grade_and_volume(parts: list[str]) -> tuple[str, str]:
    """从左到右扫。单册覆盖范围，范围不覆盖已经确定的单册。"""
    grade = ""
    volume = ""
    single = False
    for part in parts:
        found = _grade_in_text(part)
        if found is None:
            continue
        found_grade, found_volume, is_single = found
        if is_single:
            grade = found_grade
            volume = found_volume or volume
            single = True
        elif not single:
            grade = found_grade
            volume = found_volume or volume
    return grade, volume


def _grade_in_text(text: str) -> tuple[str, str, bool] | None:
    ranged = _RANGE_GRADE.search(text)
    if ranged:
        left, right, volume_mark = ranged.group(1), ranged.group(2), ranged.group(3) or ""
        return (
            f"{_CN[left]}至{_CN[right]}年级",
            _volume_name(volume_mark),
            False,
        )
    single = _SINGLE_GRADE.search(text)
    if single:
        volume = _VOLUME_MARK.search(text)
        return (
            f"{_CN[single.group(1)]}年级",
            _volume_name(volume.group(1) if volume else ""),
            True,
        )
    compact = _COMPACT_GRADE.search(text)
    if compact:
        return (
            f"{_CN[compact.group(1)]}年级",
            _volume_name(compact.group(2)),
            True,
        )
    cn_compact = _CN_COMPACT_GRADE.search(text)
    if cn_compact:
        return (
            f"{_CN[cn_compact.group(1)]}年级",
            _volume_name(cn_compact.group(2)),
            True,
        )
    subject_compact = _SUBJECT_COMPACT_GRADE.search(text)
    if subject_compact:
        return (
            f"{_CN[subject_compact.group(1)]}年级",
            _volume_name(subject_compact.group(2)),
            True,
        )
    ab_volume = _AB_VOLUME.search(text)
    if ab_volume:
        volume = "上册" if ab_volume.group(2).upper() == "A" else "下册"
        return (f"{_CN[ab_volume.group(1)]}年级", volume, True)
    return None


def _volume_name(mark: str) -> str:
    return {"上": "上册", "下": "下册", "上下": "上下册"}.get(mark, "")


def _role_of(series_raw: str) -> str:
    for role, keys in _ROLE_RULES:
        if any(key in series_raw for key in keys):
            return role
    return "其他"


def _year_token(text: str) -> str:
    matches = list(_YEAR_TOKEN.finditer(text))
    if not matches:
        return ""
    year, season = matches[-1].group(1), matches[-1].group(2)
    if len(year) == 2:
        year = "20" + year
    return f"{year}{season}"


def _series_label(raw: str, year: str) -> str:
    text = raw.replace("《", "").replace("》", "")
    text = _RANGE_GRADE.sub("", text)
    text = _YEAR_TOKEN.sub("", text)
    text = re.sub(r"(上下|上|下)册", "", text)
    text = re.sub(r"\s+", "", text).strip(" -_、")
    if not text:
        text = "未命名系列"
    if year and not text.endswith(year):
        text = f"{text}-{year}"
    return text


def _fan_topic(filename: str) -> str:
    stem = pathlib.PurePosixPath(filename).stem
    positions = [stem.rfind(mark) for mark in (")", "）") if stem.rfind(mark) >= 0]
    if positions:
        tail = stem[max(positions) + 1:].strip(" 、.。")
        if tail:
            return tail
    return "未分主题"


def _with_tail(series_relative: pathlib.Path, tail: list[str]) -> pathlib.Path:
    if not tail:
        return series_relative
    return series_relative.joinpath(*(_seg(part) for part in tail))


def _path(*parts: str) -> pathlib.Path:
    cleaned = [common.sanitize_segment(part) for part in parts if str(part or "").strip()]
    if not cleaned:
        return pathlib.Path("未命名")
    return pathlib.Path(*cleaned)


def _seg(part: str) -> str:
    return common.sanitize_segment(part)


def _parts(relative: str) -> list[str]:
    text = str(relative or "").replace("\\", "/").strip("/")
    return [piece for piece in text.split("/") if piece not in ("", ".", "..")]
