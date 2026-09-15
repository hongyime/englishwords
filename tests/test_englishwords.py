"""Exercise generation and file preservation using temporary fixture directories."""
from contextlib import redirect_stderr
from io import StringIO
from itertools import islice
from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("englishwords", ROOT / "englishwords.py")
words = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(words)


class WordGenerationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / "words.txt"

    def cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "englishwords.py"), *args],
                              cwd=self.root, text=True, capture_output=True, timeout=10)

    def test_import_does_not_read_or_write_files(self):
        self.output.write_bytes(b"retained original\n")
        result = subprocess.run([sys.executable, "-c", "import englishwords"],
                                cwd=self.root, env={**os.environ, "PYTHONPATH": str(ROOT)},
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.output.read_bytes(), b"retained original\n")
        self.assertEqual(list(self.root.iterdir()), [self.output])

    def test_original_length_and_letter_order(self):
        result = list(words.iter_words(1, 2))
        self.assertEqual(len(result), 702)
        self.assertEqual(len(set(result)), 702)
        self.assertEqual(result[:3], ["a", "b", "c"])
        self.assertEqual(result[25:29], ["z", "aa", "ab", "ac"])
        self.assertEqual(result[51:54], ["az", "ba", "bb"])
        self.assertEqual(result[-2:], ["zy", "zz"])

    def test_twenty_six_letter_prefix_has_bounded_memory(self):
        tracemalloc.start()
        try:
            result = list(islice(words.iter_words(26, 26), 1000))
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 1_000_000)
        self.assertEqual(result[0], "a" * 26)
        self.assertEqual(result[1], "a" * 25 + "b")
        self.assertEqual(len(result), 1000)

    def test_exact_output_totals_include_lf_bytes(self):
        self.assertEqual(words.estimate_output(1, 2), (702, 2080))
        self.assertEqual(words.estimate_output(26, 26), (26 ** 26, 27 * 26 ** 26))

    def test_invalid_ranges_are_rejected(self):
        for bounds in [(0, 1), (2, 1), (1, 27), (True, 2), (1, 2.5)]:
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                words.estimate_output(*bounds)

    def test_cli_requires_an_explicit_maximum_length(self):
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_dry_run_can_estimate_huge_output_without_generation(self):
        result = self.cli("--min-length", "26", "--max-length", "26", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"{26 ** 26:,}", result.stdout)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_workload_limits_fail_before_creating_any_file(self):
        for args in [("--max-length", "26"), ("--max-length", "1", "--max-words", "25"),
                     ("--max-length", "1", "--max-bytes", "51")]:
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_explicit_limits_allow_a_complete_ordered_file(self):
        result = self.cli("--max-length", "2", "--max-words", "702", "--max-bytes", "2080")
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = "\n".join(words.iter_words(1, 2)) + "\n"
        self.assertEqual(self.output.read_bytes(), expected.encode("ascii"))
        self.assertEqual(self.output.stat().st_size, 2080)
        self.assertEqual(list(self.root.iterdir()), [self.output])

    def test_existing_output_and_directories_are_preserved(self):
        self.output.write_bytes(b"original data\x00\xff")
        with self.assertRaises(FileExistsError):
            words.write_words(self.output, 1, 1)
        self.assertEqual(self.output.read_bytes(), b"original data\x00\xff")
        with self.assertRaises(FileExistsError):
            words.write_words(self.root, 1, 1)
        self.assertEqual(list(self.root.iterdir()), [self.output])

    def test_a_destination_created_during_generation_is_never_replaced(self):
        link = os.link

        def raced_link(source, destination):
            Path(destination).write_bytes(b"concurrent original")
            return link(source, destination)

        with patch.object(words.os, "link", side_effect=raced_link), self.assertRaises(FileExistsError):
            words.write_words(self.output, 1, 1)
        self.assertEqual(self.output.read_bytes(), b"concurrent original")
        partials = list(self.root.glob("*.partial"))
        self.assertEqual(len(partials), 1)
        self.assertEqual(partials[0].read_bytes(), b"a\nb\nc\nd\ne\nf\ng\nh\ni\nj\nk\nl\nm\nn\no\np\nq\nr\ns\nt\nu\nv\nw\nx\ny\nz\n")

    def test_interruption_preserves_partial_data_without_publishing(self):
        def interrupted(*args):
            yield "a"
            yield "b"
            raise KeyboardInterrupt

        with patch.object(words, "iter_words", side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
            words.write_words(self.output, 1, 1)
        self.assertFalse(self.output.exists())
        partials = list(self.root.glob("*.partial"))
        self.assertEqual(len(partials), 1)
        self.assertEqual(partials[0].read_bytes(), b"a\nb\n")

    def test_publish_failure_keeps_complete_partial_file(self):
        with patch.object(words.os, "link", side_effect=OSError("fixture filesystem cannot link")), self.assertRaises(OSError):
            words.write_words(self.output, 1, 1)
        self.assertFalse(self.output.exists())
        self.assertEqual(len(list(self.root.glob("*.partial"))), 1)
        self.assertEqual(next(self.root.glob("*.partial")).stat().st_size, 52)

    def test_cleanup_failure_keeps_published_output_and_reports_duplicate(self):
        errors = StringIO()
        with patch.object(words.Path, "unlink", side_effect=OSError("fixture busy")), redirect_stderr(errors):
            words.write_words(self.output, 1, 1)
        self.assertEqual(self.output.stat().st_size, 52)
        self.assertIn("partial", errors.getvalue())
        self.assertEqual(len(list(self.root.glob("*.partial"))), 1)


if __name__ == "__main__":
    unittest.main()
