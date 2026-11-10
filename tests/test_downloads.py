#!/usr/bin/env python3
"""下载管道纯函数的单元测试。

只测不需要网络与磁盘副作用的逻辑：文件名清洗、目录推导、进度合成、
格式化。涉及实际克隆/下载的部分靠人工冒烟（见 README 的批量下载一节），
不在这里伪造 —— 伪造出来的「测试通过」比没有测试更危险。

用法：
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

from downloads import bilibili, common, github, quark


class SanitizeSegmentTests(unittest.TestCase):
    def test_replaces_windows_forbidden_chars(self):
        self.assertEqual(
            common.sanitize_segment("01 数一数：认识|数字?"),
            "01 数一数：认识_数字_",
        )

    def test_strips_trailing_dot_and_space(self):
        # Windows 会静默丢弃尾部点，留着会导致「写入 A. 读取 A」失败
        self.assertEqual(common.sanitize_segment("第一课 . "), "第一课")

    def test_prefixes_reserved_device_names(self):
        for reserved in ("CON", "nul", "PRN", "com1"):
            cleaned = common.sanitize_segment(reserved)
            self.assertTrue(cleaned.startswith("_"), f"{reserved} -> {cleaned}")
            self.assertNotEqual(cleaned.upper(), reserved.upper())

    def test_accepts_reserved_name_with_extension_stripped(self):
        # `CON.mp4` 的主干仍是保留名，必须加前缀
        self.assertEqual(common.sanitize_segment("CON.mp4"), "CON.mp4")
        self.assertTrue(common.sanitize_segment("CON").startswith("_"))

    def test_empty_input_falls_back(self):
        self.assertEqual(common.sanitize_segment("   "), "未命名")
        self.assertEqual(common.sanitize_segment(None), "未命名")

    def test_truncates_long_names(self):
        cleaned = common.sanitize_segment("a" * 300)
        self.assertEqual(len(cleaned), common.MAX_SEGMENT_LENGTH)

    def test_collapses_whitespace(self):
        self.assertEqual(common.sanitize_segment("a    b\n\tc"), "a b c")


class SanitizeRelativePathTests(unittest.TestCase):
    def test_joins_sanitized_segments(self):
        path = common.sanitize_relative_path("语文-统编版", "一年级-上册")
        self.assertEqual(path, pathlib.Path("语文-统编版") / "一年级-上册")

    def test_skips_blank_segments(self):
        path = common.sanitize_relative_path("a", "", "  ", "b")
        self.assertEqual(path, pathlib.Path("a") / "b")

    def test_splits_embedded_slashes_into_levels(self):
        """网盘 rel_path 是 `标题/子目录/文件.mp4` 这种多级路径。

        整段当成单个路径段清洗会把 `/` 换成 `_`，所有文件被拍平到一层，
        文件名里还残留整条路径（实测网盘产物每个文件带 50+ 字符前缀）。
        """
        path = common.sanitize_relative_path("标题/子目录/文件.mp4")
        self.assertEqual(len(path.parts), 3)
        self.assertEqual(path.parts[-1], "文件.mp4")

    def test_ignores_parent_directory_tokens(self):
        path = common.sanitize_relative_path("../a/./b.mp4")
        self.assertNotIn("..", path.parts)
        self.assertNotIn(".", path.parts)


class QuarkShareRootTests(unittest.TestCase):
    """分享根目录剥离：target_dir 已带 `<id>__<资料名>`，不该重复长标题。"""

    def test_strips_single_common_root(self):
        entries = [{"rel_path": "分享标题/a.mp4"}, {"rel_path": "分享标题/子/b.mp4"}]
        root = quark.share_root_prefix(entries)
        self.assertEqual(root, "分享标题")
        self.assertEqual(quark.relative_after_root(entries[1], root), "子/b.mp4")

    def test_keeps_multiple_roots(self):
        entries = [{"rel_path": "语文/a.mp4"}, {"rel_path": "数学/b.mp4"}]
        self.assertEqual(quark.share_root_prefix(entries), "")

    def test_keeps_when_root_level_file_exists(self):
        # 有文件直接位于根目录时第一段不是目录，剥掉会丢文件
        entries = [{"rel_path": "top.mp4"}, {"rel_path": "dir/a.mp4"}]
        self.assertEqual(quark.share_root_prefix(entries), "")

    def test_empty_entries(self):
        self.assertEqual(quark.share_root_prefix([]), "")


class FormatBytesTests(unittest.TestCase):
    def test_units(self):
        self.assertEqual(common.format_bytes(0), "0 B")
        self.assertEqual(common.format_bytes(512), "512 B")
        self.assertEqual(common.format_bytes(1024), "1.00 KB")
        self.assertEqual(common.format_bytes(1536), "1.50 KB")
        self.assertEqual(common.format_bytes(1024**3), "1.00 GB")

    def test_handles_none(self):
        self.assertEqual(common.format_bytes(None), "0 B")


class RepoDirNameTests(unittest.TestCase):
    def test_double_underscore_separator(self):
        self.assertEqual(github.repo_dir_name("HKUDS/DeepTutor"), "HKUDS__DeepTutor")

    def test_avoids_collision_between_slash_and_underscore(self):
        # a/b_c 与 a_b/c 必须映射到不同目录
        self.assertNotEqual(github.repo_dir_name("a/b_c"), github.repo_dir_name("a_b/c"))

    def test_missing_repo_part(self):
        self.assertEqual(github.repo_dir_name("onlyowner"), "onlyowner__repo")


class GitProgressPatternTests(unittest.TestCase):
    def test_parses_receiving_objects_line(self):
        line = "Receiving objects:  37% (1234/3333), 45.67 MiB | 2.31 MiB/s"
        match = github.GIT_PROGRESS_PATTERN.search(line)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "45.67")
        self.assertEqual(match.group(2), "M")

    def test_ignores_unrelated_lines(self):
        for line in ("Cloning into 'x'...", "remote: Compressing objects:  54% (9123/16894)"):
            self.assertIsNone(github.GIT_PROGRESS_PATTERN.search(line))


class BilibiliPathTests(unittest.TestCase):
    def test_edition_mapping(self):
        self.assertEqual(bilibili.edition_of("tongbian_chinese_g1_up"), "统编版")
        self.assertEqual(bilibili.edition_of("renjiao_math_g3_down"), "人教版")
        self.assertEqual(bilibili.edition_of("waiyanshe_english_g6_up"), "外研社版")
        self.assertEqual(bilibili.edition_of("unknown_prefix_x"), "其他版")

    def test_target_dir_layout(self):
        record = {
            "id": "tongbian_chinese_g1_up",
            "subject": "语文",
            "grade": "一年级",
            "volume": "上册",
        }
        path = bilibili.target_dir_for(record)
        expected = (
            common.DOWNLOADS_ROOT / "videos" / "bilibili" / "小学"
            / "语文-统编版" / "一年级-上册"
        )
        self.assertEqual(path, expected)

    def test_target_dir_sanitizes_subject(self):
        record = {"id": "renjiao_math_g1_up", "subject": "数学/奥数",
                  "grade": "一年级", "volume": "上册"}
        path = bilibili.target_dir_for(record)
        self.assertNotIn("/", path.name)
        self.assertNotIn("/", path.parent.name)

    def test_plan_videos_only_returns_core_by_default(self):
        planned = bilibili.plan_videos(only_core=True)
        self.assertTrue(planned, "resources.json 里应有核心合集")
        for item in planned:
            self.assertTrue(
                item["id"].startswith(bilibili.CORE_PREFIXES),
                f"{item['id']} 不属于核心范围",
            )

    def test_plan_videos_sorted_by_subject_then_grade(self):
        planned = bilibili.plan_videos(only_core=True)
        subjects = [item["subject"] for item in planned]
        order = {"语文": 0, "数学": 1, "英语": 2}
        ranks = [order.get(subject, 9) for subject in subjects]
        self.assertEqual(ranks, sorted(ranks), "学科顺序应为 语文 -> 数学 -> 英语")


class QuarkPlanTests(unittest.TestCase):
    def test_plan_only_contains_primary_scope(self):
        planned = quark.plan_netdisk()
        for item in planned:
            self.assertIn(item["id"], quark.PRIMARY_ITEM_IDS)

    def test_passcodes_attached_where_known(self):
        planned = {item["id"]: item for item in quark.plan_netdisk()}
        self.assertEqual(planned["primary_1000_words"]["passcode"], "YhRG")
        self.assertEqual(planned["phonics_270"]["passcode"], "ab8M")

    def test_items_without_quark_source_are_flagged(self):
        planned = {item["id"]: item for item in quark.plan_netdisk()}
        # word_posters 的夸克源已 404，必须标出来而不是静默跳过
        self.assertEqual(planned["word_posters"]["status"], "no_quark_source")

    def test_share_id_extracted_from_url(self):
        planned = {item["id"]: item for item in quark.plan_netdisk()}
        self.assertEqual(planned["fan_geometry_900"]["share_id"], "668920790b03")


class QuarkErrorTests(unittest.TestCase):
    def test_business_code_is_preserved(self):
        error = quark.QuarkError("需要提取码", quark.QUARK_PASSCODE_REQUIRED_CODE)
        self.assertEqual(error.code, 41008)
        self.assertIn("提取码", str(error))


class PageNumberNormalizationTests(unittest.TestCase):
    """BBDown 的 `<pageNumberWithZero>` 补零位数随请求的 P 范围漂移。"""

    def test_width_thresholds(self):
        self.assertEqual(bilibili.page_number_width(5), 1)
        self.assertEqual(bilibili.page_number_width(56), 2)
        self.assertEqual(bilibili.page_number_width(100), 3)
        self.assertEqual(bilibili.page_number_width(102), 3)
        self.assertEqual(bilibili.page_number_width(1994), 4)

    def test_dedupes_same_size_duplicate(self):
        import tempfile
        with tempfile.TemporaryDirectory() as workspace:
            directory = pathlib.Path(workspace)
            (directory / "[P1] a.mp4").write_bytes(b"x" * 10)
            (directory / "[P001] a.mp4").write_bytes(b"x" * 10)
            result = bilibili.normalize_page_numbers(directory, 100)
            self.assertEqual(result["deduped"], 1)
            self.assertEqual([p.name for p in directory.glob("*.mp4")], ["[P001] a.mp4"])

    def test_renames_short_prefix(self):
        import tempfile
        with tempfile.TemporaryDirectory() as workspace:
            directory = pathlib.Path(workspace)
            (directory / "[P2] b.mp4").write_bytes(b"y" * 20)
            result = bilibili.normalize_page_numbers(directory, 100)
            self.assertEqual(result["renamed"], 1)
            self.assertEqual([p.name for p in directory.glob("*.mp4")], ["[P002] b.mp4"])

    def test_keeps_already_canonical_names(self):
        import tempfile
        with tempfile.TemporaryDirectory() as workspace:
            directory = pathlib.Path(workspace)
            (directory / "[P050] c.mp4").write_bytes(b"z" * 30)
            result = bilibili.normalize_page_numbers(directory, 100)
            self.assertEqual(result, {"renamed": 0, "deduped": 0, "conflicts": []})

    def test_reports_conflict_when_sizes_differ(self):
        import tempfile
        with tempfile.TemporaryDirectory() as workspace:
            directory = pathlib.Path(workspace)
            (directory / "[P1] a.mp4").write_bytes(b"x" * 10)
            (directory / "[P001] a.mp4").write_bytes(b"x" * 99)
            result = bilibili.normalize_page_numbers(directory, 100)
            self.assertEqual(result["conflicts"], ["[P1] a.mp4"])
            self.assertEqual(len(list(directory.glob("*.mp4"))), 2)


class ProgressCombinationTests(unittest.TestCase):
    def test_combine_sums_stages(self):
        states = [
            {"stage": "github", "item_done": 3, "item_total": 22,
             "page_done": 3, "page_total": 0, "bytes_done": 100,
             "finished": False, "updated_at": "2026-11-09T10:00:00+08:00"},
            {"stage": "video", "item_done": 1, "item_total": 32,
             "page_done": 50, "page_total": 1994, "bytes_done": 200,
             "finished": False, "updated_at": "2026-11-09T11:00:00+08:00"},
        ]
        original = common.read_all_progress
        try:
            common.read_all_progress = lambda: states
            combined = common.combine_progress()
        finally:
            common.read_all_progress = original
        self.assertEqual(combined["item_done"], 4)
        self.assertEqual(combined["item_total"], 54)
        self.assertEqual(combined["page_done"], 53)
        self.assertEqual(combined["bytes_done"], 300)
        self.assertEqual(combined["updated_at"], "2026-11-09T11:00:00+08:00")
        self.assertFalse(combined["finished"])

    def test_finished_only_when_all_stages_finished(self):
        states = [
            {"stage": "a", "finished": True, "updated_at": "1", "item_done": 1,
             "item_total": 1, "page_done": 0, "page_total": 0, "bytes_done": 0},
            {"stage": "b", "finished": False, "updated_at": "2", "item_done": 0,
             "item_total": 1, "page_done": 0, "page_total": 0, "bytes_done": 0},
        ]
        original = common.read_all_progress
        try:
            common.read_all_progress = lambda: states
            combined = common.combine_progress()
        finally:
            common.read_all_progress = original
        self.assertFalse(combined["finished"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
