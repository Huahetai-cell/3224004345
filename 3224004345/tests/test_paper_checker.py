from __future__ import annotations

import contextlib
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from paper_checker import (
    _dice_similarity,
    calculate_similarity,
    main,
    normalize_text,
    run,
)


class NormalizationTests(unittest.TestCase):
    def test_normalizes_width_case_whitespace_and_symbols(self) -> None:
        self.assertEqual(normalize_text(" Ａb，C！\n￥ "), "abc")

    def test_keeps_letters_numbers_and_chinese(self) -> None:
        self.assertEqual(normalize_text("论文 2026_v1"), "论文2026v1")


class SimilarityTests(unittest.TestCase):
    def test_identical_text_is_one(self) -> None:
        self.assertEqual(calculate_similarity("今天是星期天。", "今天是星期天"), 1.0)

    def test_completely_different_text_is_zero(self) -> None:
        self.assertEqual(calculate_similarity("甲乙丙", "丁戊己"), 0.0)

    def test_document_example_is_partial_match(self) -> None:
        score = calculate_similarity(
            "今天是星期天，天气晴，今天晚上我要去看电影。",
            "今天是周天，天气晴朗，我晚上要去看电影。",
        )
        self.assertAlmostEqual(score, 0.6372549020)

    def test_empty_texts_are_identical(self) -> None:
        self.assertEqual(calculate_similarity("", " \n，！"), 1.0)

    def test_only_one_empty_text_is_zero(self) -> None:
        self.assertEqual(calculate_similarity("正文", ""), 0.0)
        self.assertEqual(calculate_similarity("", "正文"), 0.0)

    def test_single_character_falls_back_to_unigram(self) -> None:
        self.assertEqual(calculate_similarity("甲", "甲"), 1.0)
        self.assertEqual(calculate_similarity("甲", "乙"), 0.0)

    def test_repeated_fragments_use_multiset_counts(self) -> None:
        self.assertAlmostEqual(calculate_similarity("aaaa", "aa"), 0.5333333333)

    def test_reordered_blocks_keep_internal_matches(self) -> None:
        self.assertAlmostEqual(calculate_similarity("甲乙丙丁", "丙丁甲乙"), 0.7333333333)

    def test_empty_feature_lists_are_identical(self) -> None:
        self.assertEqual(_dice_similarity([], []), 1.0)


class FileAndCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _write_inputs(self) -> tuple[Path, Path, Path]:
        original = self.base / "原文.txt"
        suspect = self.base / "抄袭版.txt"
        answer = self.base / "答案.txt"
        original.write_text("今天天气晴朗。", encoding="utf-8-sig")
        suspect.write_text("今天，天气晴朗！", encoding="utf-8")
        return original, suspect, answer

    def test_run_reads_utf8_bom_and_writes_two_decimals(self) -> None:
        original, suspect, answer = self._write_inputs()
        run(original, suspect, answer)
        self.assertEqual(answer.read_text(encoding="utf-8"), "1.00\n")

    def test_run_falls_back_to_gb18030(self) -> None:
        original = self.base / "original.txt"
        suspect = self.base / "suspect.txt"
        answer = self.base / "answer.txt"
        original.write_bytes("中文论文".encode("gb18030"))
        suspect.write_bytes("中文论文".encode("gb18030"))
        run(original, suspect, answer)
        self.assertEqual(answer.read_text(encoding="utf-8"), "1.00\n")

    def test_output_may_overwrite_an_input_after_both_are_read(self) -> None:
        original, suspect, _ = self._write_inputs()
        run(original, suspect, original)
        self.assertRegex(original.read_text(encoding="utf-8"), r"^\d\.\d{2}\n$")

    def test_main_rejects_wrong_argument_count(self) -> None:
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            exit_code = main([])
        self.assertEqual(exit_code, 2)
        self.assertIn("用法", errors.getvalue())

    def test_main_uses_process_arguments_when_argv_is_none(self) -> None:
        original, suspect, answer = self._write_inputs()
        with mock.patch.object(sys, "argv", ["main.py", str(original), str(suspect), str(answer)]):
            self.assertEqual(main(), 0)
        self.assertEqual(answer.read_text(encoding="utf-8"), "1.00\n")

    def test_main_reports_missing_input_without_traceback(self) -> None:
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            exit_code = main([str(self.base / "missing.txt"), "unused.txt", "answer.txt"])
        self.assertEqual(exit_code, 1)
        self.assertIn("输入文件不存在", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def test_main_reports_invalid_encoding(self) -> None:
        invalid = self.base / "invalid.txt"
        valid = self.base / "valid.txt"
        invalid.write_bytes(b"\x80")
        valid.write_text("正文", encoding="utf-8")
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            exit_code = main([str(invalid), str(valid), str(self.base / "answer.txt")])
        self.assertEqual(exit_code, 1)
        self.assertIn("无法以 UTF-8 或 GB18030 解码", errors.getvalue())

    def test_main_reports_unwritable_output_location(self) -> None:
        original, suspect, _ = self._write_inputs()
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            exit_code = main(
                [str(original), str(suspect), str(self.base / "missing" / "answer.txt")]
            )
        self.assertEqual(exit_code, 1)
        self.assertTrue(errors.getvalue().startswith("错误："))

    def test_cli_end_to_end(self) -> None:
        original, suspect, answer = self._write_inputs()
        project_root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                str(project_root / "main.py"),
                str(original),
                str(suspect),
                str(answer),
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(re.fullmatch(r"(?:0|1)\.\d{2}\n", answer.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
