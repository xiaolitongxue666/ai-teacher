#!/usr/bin/env python3
"""课程槽位路径的纯函数测试。

搬迁和以后的下载必须算出同一条路径，否则重跑会把已落盘文件判成缺失。
这里只用真实目录里抽到的相对路径，不碰磁盘。
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from downloads import common, library_layout
import library_query


def _place(source_id: str, relative: str) -> library_layout.Placement:
    return library_layout.place(source_id, relative)


class WorkbookPlacementTests(unittest.TestCase):
    def test_math_quiz_file_goes_to_grade_and_paper_slot(self):
        placed = _place(
            "p_math",
            "人教版/《53全优卷》/2024春五三全优卷1下数学（人教）.pdf",
        )
        self.assertFalse(placed.unsorted)
        self.assertEqual(placed.subject, "数学")
        self.assertEqual(placed.edition, "人教版")
        self.assertEqual(placed.grade, "一年级")
        self.assertEqual(placed.volume, "下册")
        self.assertEqual(placed.role, "试卷")
        self.assertEqual(placed.series, "53全优卷-2024春")
        self.assertEqual(
            placed.relative.parts[:7],
            ("小学", "数学", "人教版", "一年级", "下册", "试卷", "53全优卷-2024春"),
        )
        self.assertEqual(placed.relative.name, "2024春五三全优卷1下数学（人教）.pdf")

    def test_chinese_renjiao_label_is_tongbian(self):
        placed = _place(
            "p_chn",
            "《53天天练》/一年级语文上册人教版《53天天练》/第1课.pdf",
        )
        self.assertEqual(placed.subject, "语文")
        self.assertEqual(placed.edition, "统编版")
        self.assertEqual(placed.grade, "一年级")
        self.assertEqual(placed.volume, "上册")
        self.assertEqual(placed.role, "同步练习")
        self.assertEqual(placed.series, "53天天练")
        self.assertNotIn("人教版", placed.relative.parts)

    def test_english_pep_is_renjiao(self):
        placed = _place(
            "p_eng",
            "《53天天练》/五年级英语上册人教PEP版24秋《53天天练》/a.pdf",
        )
        self.assertEqual(placed.edition, "人教版")
        self.assertEqual(placed.grade, "五年级")
        self.assertEqual(placed.volume, "上册")
        self.assertEqual(placed.role, "同步练习")
        self.assertEqual(placed.series, "53天天练-2024秋")

    def test_year_token_splits_series_directories(self):
        autumn = _place(
            "p_math",
            "人教版/《53天天练》/人教版数学一年级上册《53天天练》24秋/a.pdf",
        )
        spring = _place(
            "p_math",
            "人教版/《53天天练》/人教版数学一年级上册《53天天练》25春/a.pdf",
        )
        self.assertNotEqual(autumn.series_relative, spring.series_relative)
        self.assertEqual(autumn.relative.name, spring.relative.name)

    def test_beishida_folder_without_ban_suffix(self):
        placed = _place("p_math", "北师大/《口算天天练》/一年级上册.pdf")
        self.assertEqual(placed.edition, "北师大版")
        self.assertEqual(placed.grade, "一年级")
        self.assertEqual(placed.volume, "上册")

    def test_science_edition_folder_and_grade_range(self):
        placed = _place("p_sci", "教科版/《乐学帮》3-6上册/file.pdf")
        self.assertEqual(placed.subject, "科学")
        self.assertEqual(placed.edition, "教科版")
        self.assertEqual(placed.grade, "三至六年级")
        self.assertEqual(placed.volume, "上册")
        self.assertFalse(placed.unsorted)

    def test_morality_is_tongbian(self):
        placed = _place("p_morality", "《速记速查手册》/三年级下册.pdf")
        self.assertEqual(placed.subject, "道法")
        self.assertEqual(placed.edition, "统编版")
        self.assertEqual(placed.grade, "三年级")
        self.assertEqual(placed.volume, "下册")

    def test_filename_grade_overrides_parent_range(self):
        placed = _place(
            "p_math",
            "人教版/《53单元归类复习》/1-6上册/人教版数学1年级下册《53归类复习》.pdf",
        )
        self.assertEqual(placed.grade, "一年级")
        self.assertEqual(placed.volume, "下册")
        self.assertEqual(placed.role, "复习冲刺")

    def test_compressed_grade_marks_in_filenames(self):
        cases = [
            ("p_chn", "《53单元归类复习》/2024春53单元归类复习语文一下.pdf", "一年级", "下册"),
            ("p_chn", "《教材习题参考答案》/小学语文部编 一上 教材课后习题参考答案.pdf", "一年级", "上册"),
            ("p_math", "西师大/《一线好卷》/一线好卷西1数上-学用.pdf", "一年级", "上册"),
            ("p_chn", "《53单元提优》/53单元提优1A.zip", "一年级", "上册"),
            ("p_eng", "《53单元归类复习》/小学英语《53单元归类复习》3B.pdf", "三年级", "下册"),
        ]
        for source_id, relative, grade, volume in cases:
            placed = _place(source_id, relative)
            self.assertEqual(placed.grade, grade, relative)
            self.assertEqual(placed.volume, volume, relative)

    def test_lesson_index_is_not_a_grade(self):
        placed = _place("p_math", "人教版/《口算天天练》/5.5 两位数加一位数.docx")
        self.assertEqual(placed.grade, "")

    def test_missing_grade_stays_in_one_span_folder(self):
        placed = _place("p_chn", "《思维导图》/总览.pdf")
        self.assertEqual(placed.grade, "")
        self.assertIn("跨年级", placed.relative.parts)
        self.assertEqual(placed.relative.parts.count("跨年级"), 1)


class SpecialPackTests(unittest.TestCase):
    def test_fan_geometry_is_topic_not_a_volume(self):
        name = "01_1、【L5、6】（拉窗帘模型即等积变形)巧求面积.mp4"
        placed = _place("fan_geometry_900", name)
        self.assertFalse(placed.unsorted)
        self.assertEqual(placed.edition, "通用")
        self.assertEqual(placed.role, "思维专题")
        self.assertEqual(placed.grade, "")
        self.assertEqual(placed.volume, "")
        self.assertEqual(
            placed.relative.parts[:5],
            ("小学", "数学", "通用", "思维专题", "巧求面积"),
        )
        self.assertNotIn("五年级", placed.relative.parts)
        self.assertNotIn("上册", placed.relative.parts)

    def test_phonics_and_bridge_math_split(self):
        phonics = _place("phonics_270", "Z 自然拼读作业纸270多页/a.pdf")
        bridge = _place("phonics_270", "超全幼小衔接数学资料/b.pdf")
        self.assertEqual(phonics.relative.parts[:4], ("小学", "英语", "通用", "自然拼读"))
        self.assertEqual(bridge.relative.parts[:4], ("小学", "数学", "通用", "幼小衔接"))

    def test_primary_words(self):
        placed = _place("primary_1000_words", "40篇短文记完小学1000核心词汇.pdf")
        self.assertEqual(
            placed.relative.parts[:5],
            ("小学", "英语", "通用", "词汇", "小学1000词"),
        )

    def test_curriculum_uses_folder_year_not_grade(self):
        placed = _place(
            "j_curriculum",
            "《义务教育课程标准》2025修订/2025版/义务教育数学课程标准.pdf",
        )
        self.assertEqual(placed.stage, "课标")
        self.assertEqual(placed.subject, "数学")
        self.assertEqual(placed.relative.parts[:3], ("课标", "义务教育", "2025"))
        self.assertNotIn("一年级", placed.relative.parts)

    def test_unknown_source_is_unsorted(self):
        placed = _place("no_such_pack", "子目录/a.pdf")
        self.assertTrue(placed.unsorted)
        self.assertEqual(placed.relative.parts[0], "_unsorted")
        self.assertEqual(placed.relative.parts[1], "no_such_pack")
        self.assertEqual(placed.relative.name, "a.pdf")


class VideoPlacementTests(unittest.TestCase):
    def test_video_id_lands_in_sync_slot(self):
        placed = _place("renjiao_english_g3_down", "[P001] 标题.mp4")
        self.assertEqual(placed.subject, "英语")
        self.assertEqual(placed.edition, "人教版")
        self.assertEqual(placed.grade, "三年级")
        self.assertEqual(placed.volume, "下册")
        self.assertEqual(placed.role, "同步课")
        self.assertEqual(placed.series, "renjiao_english_g3_down")
        self.assertEqual(
            placed.relative.parts,
            ("小学", "英语", "人教版", "三年级", "下册", "同步课",
             "renjiao_english_g3_down", "[P001] 标题.mp4"),
        )

    def test_video_record_prefers_resource_fields(self):
        directory = library_layout.video_directory({
            "id": "tongbian_chinese_g1_up",
            "subject": "语文",
            "grade": "一年级",
            "volume": "上册",
        })
        self.assertEqual(
            directory,
            common.DOWNLOADS_ROOT / "library" / "小学" / "语文" / "统编版"
            / "一年级" / "上册" / "同步课" / "tongbian_chinese_g1_up",
        )

    def test_legacy_video_directories_are_not_nested(self):
        placed = _place(
            "renjiao_english_g3_down",
            "小学/英语-人教版/三年级-下册/[P001] 标题.mp4",
        )
        self.assertNotIn("英语-人教版", placed.relative.parts)
        self.assertEqual(placed.relative.name, "[P001] 标题.mp4")


class QueryCoverageTests(unittest.TestCase):
    def test_range_covers_included_grade_only(self):
        self.assertTrue(library_query._grade_covers("三至六年级", "四年级"))
        self.assertFalse(library_query._grade_covers("三至六年级", "一年级"))
        self.assertTrue(library_query._grade_covers("", "四年级"))
        self.assertTrue(library_query._grade_covers("四年级", "四年级"))

    def test_volume_does_not_cross_terms(self):
        self.assertFalse(library_query._volume_covers("上册", "下册"))
        self.assertTrue(library_query._volume_covers("上下册", "下册"))
        self.assertTrue(library_query._volume_covers("", "下册"))


if __name__ == "__main__":
    unittest.main()
