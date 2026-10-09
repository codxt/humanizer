"""Regression checks for report-only lint, masking, and source coordinates."""

import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "prose_lint", Path(__file__).resolve().parents[1] / "scripts" / "prose_lint.py"
)
lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint)


class ProseLintTests(unittest.TestCase):
    def scan(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.md"
            path.write_text(text, encoding="utf-8")
            before = path.read_bytes()
            findings = lint.lint(path)
            self.assertEqual(before, path.read_bytes())
            return findings

    def test_fence_preserves_source_line(self):
        text = "Intro\n```python\ncrucial = 'delve'\n```\nThat distinction matters.\n"
        self.assertEqual(self.scan(text), [(5, "restating closer", "That distinction matters")])

    def test_tilde_fence(self):
        self.assertEqual(self.scan("~~~text\nВ этом и заключается главное.\n~~~\n"), [])

    def test_long_fence_does_not_close_on_short_fence(self):
        text = "````text\n```\nLet that sink in.\n````\nReal talk.\n"
        self.assertEqual(self.scan(text), [(5, "staged candor", "Real talk")])

    def test_unclosed_fence(self):
        self.assertEqual(self.scan("```text\nRead that again.\n"), [])

    def test_inline_code_and_url(self):
        self.assertEqual(self.scan("Use `crucial` and ``delve `x` `` at https://example.org/landscape.\n"), [])

    def test_offset_and_line_count_unchanged(self):
        source = "A\r\n```\r\ncrucial\r\n```\r\nReal talk.\r\n"
        masked = lint.strip_code_fences(source)
        self.assertEqual(len(source), len(masked))
        self.assertEqual(source.count("\n"), masked.count("\n"))
        self.assertEqual(source.index("Real talk"), masked.index("Real talk"))

    def test_russian_patterns(self):
        findings = self.scan("Давайте начистоту.\nВ этом и заключается главное.\n")
        self.assertIn((1, "staged candor", "Давайте начистоту"), findings)
        self.assertIn((2, "restating closer", "В этом и заключается главное"), findings)

    def test_material_negation_remains_candidate_only(self):
        text = "Это не означает, что мы принимаем начисление.\n"
        findings = self.scan(text)
        self.assertEqual(findings[0][1], "possible imagined objection")

    def test_missing_file_is_failure(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(lint.main(["prose_lint.py", str(Path(directory) / "missing")]), 2)

    def test_invalid_utf8_is_failure(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            path = Path(directory) / "sample.md"
            path.write_bytes(b"\xff")
            self.assertEqual(lint.main(["prose_lint.py", str(path)]), 2)

    def test_findings_do_not_make_cli_fail(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            path = Path(directory) / "sample.md"
            path.write_text("That distinction matters.\n")
            self.assertEqual(lint.main(["prose_lint.py", str(path)]), 0)

    def test_geometry_still_reported(self):
        text = "".join(f"## Section {i}\n### First\n### Second\n" for i in range(6))
        self.assertTrue(any(item[1] == "uniform heading geometry" for item in self.scan(text)))


if __name__ == "__main__":
    unittest.main()
