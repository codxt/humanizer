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

    def run_cli(self, text, *options):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.md"
            path.write_text(text, encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = lint.main(["prose_lint.py", *options, str(path)])
            return code, out.getvalue(), err.getvalue(), str(path)

    def test_fail_on_selected_label_fails(self):
        code, out, _, _ = self.run_cli("Hope this helps.\n", "--fail-on", "chatbot residue")
        self.assertEqual(code, 1)
        self.assertIn("blocking", out)

    def test_fail_on_ignores_other_labels(self):
        code, _, _, _ = self.run_cli("That distinction matters.\n", "--fail-on", "chatbot residue")
        self.assertEqual(code, 0)

    def test_fail_on_unknown_label_is_usage_error(self):
        code, _, err, _ = self.run_cli("Text.\n", "--fail-on", "no such label")
        self.assertEqual(code, 2)
        self.assertIn("unknown", err)

    def test_fail_on_respects_code_fences(self):
        code, _, _, _ = self.run_cli("```text\nHope this helps.\n```\n", "--fail-on", "chatbot residue")
        self.assertEqual(code, 0)

    def test_github_annotations(self):
        code, out, _, path = self.run_cli(
            "Intro.\nHope this helps.\nThat distinction matters.\n",
            "--fail-on", "chatbot residue", "--github-annotations",
        )
        self.assertEqual(code, 1)
        self.assertIn(f"::error file={path},line=2::chatbot residue: Hope this helps", out)
        self.assertIn(f"::warning file={path},line=3::restating closer: That distinction matters", out)

    def test_russian_chatbot_residue(self):
        findings = self.scan("Отличный вопрос! Надеюсь, это поможет.\n")
        labels = [item[1] for item in findings]
        self.assertEqual(labels.count("russian chatbot residue"), 2)

    def test_english_chatbot_residue_additions(self):
        findings = self.scan("Great question. As an AI language model, I cannot.\n")
        self.assertEqual([item[1] for item in findings].count("chatbot residue"), 2)

    def test_abstract_metaphor_noun_is_candidate(self):
        findings = self.scan("The flywheel is the north star of this substrate.\n")
        self.assertEqual([item[1] for item in findings].count("abstract metaphor noun"), 3)


if __name__ == "__main__":
    unittest.main()
