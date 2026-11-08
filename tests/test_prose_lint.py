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
            path.write_bytes(text.encode("utf-8"))
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
            path.write_bytes(text.encode("utf-8"))
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = lint.main(["prose_lint.py", *options, str(path)])
            return code, out.getvalue(), err.getvalue(), str(path)

    def test_fail_on_selected_label_fails(self):
        code, out, _, _ = self.run_cli("Hope this helps.\n", "--fail-on", "assistant residue")
        self.assertEqual(code, 1)
        self.assertIn("blocking", out)

    def test_fail_on_ignores_other_labels(self):
        code, _, _, _ = self.run_cli("That distinction matters.\n", "--fail-on", "assistant residue")
        self.assertEqual(code, 0)

    def test_fail_on_unknown_label_is_usage_error(self):
        code, _, err, _ = self.run_cli("Text.\n", "--fail-on", "no such label")
        self.assertEqual(code, 2)
        self.assertIn("unknown", err)

    def test_fail_on_respects_code_fences(self):
        code, _, _, _ = self.run_cli("```text\nHope this helps.\n```\n", "--fail-on", "assistant residue")
        self.assertEqual(code, 0)

    def test_github_annotations(self):
        code, out, _, path = self.run_cli(
            "Intro.\nHope this helps.\nThat distinction matters.\n",
            "--fail-on", "assistant residue", "--github-annotations",
        )
        self.assertEqual(code, 1)
        prop = path.replace("%", "%25").replace(":", "%3A").replace(",", "%2C")
        self.assertIn(f"::error file={prop},line=2::assistant residue: Hope this helps", out)
        self.assertIn(f"::warning file={prop},line=3::restating closer: That distinction matters", out)

    def test_annotation_file_property_is_escaped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "a,b:c.md"
            path.write_text("Hope this helps.\n", encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                lint.main(["prose_lint.py", "--github-annotations", str(path)])
        line = [item for item in out.getvalue().splitlines() if item.startswith("::")][0]
        self.assertIn("a%2Cb%3Ac.md,line=1::", line)

    def test_quoted_match_is_reported_but_not_blocking(self):
        text = (
            "> Owner: Hope this helps the team.\n"
            "The owner wrote «Надеюсь, это поможет» in the brief.\n"
            'He said "As an AI language model" twice.\n'
        )
        code, out, _, _ = self.run_cli(text, "--fail-on", "assistant residue")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("[quoted]"), 3)

    def test_unquoted_after_quote_still_blocks(self):
        code, _, _, _ = self.run_cli('He said "hi". Hope this helps.\n', "--fail-on", "assistant residue")
        self.assertEqual(code, 1)

    def test_inch_marks_do_not_exempt_residue(self):
        for text in (
            'Use a 6" display. Hope this helps. The 12" model also works.\n',
            'Use the 6" display. Hope this helps. Select "Save" to continue.\n',
        ):
            with self.subTest(text=text):
                code, _, _, _ = self.run_cli(text, "--fail-on", "assistant residue")
                self.assertEqual(code, 1)

    def test_match_across_blockquote_lines_is_quoted(self):
        code, out, _, _ = self.run_cli("> [cite:\n1] was in the pasted answer.\n", "--fail-on", "chatbot artifact")
        self.assertEqual(code, 0)
        self.assertIn("chatbot artifact [quoted]", out)
        code, _, _, _ = self.run_cli("> Quoted line.\n\n[cite: 1] outside.\n", "--fail-on", "chatbot artifact")
        self.assertEqual(code, 1)

    def test_quotation_ending_in_a_digit_is_closed(self):
        text = 'The model replied "as an AI language model, I cannot confirm version 2" and stopped.\n'
        code, out, _, _ = self.run_cli(text, "--fail-on", "assistant residue")
        self.assertEqual(code, 0)
        self.assertIn("[quoted]", out)
        code, _, _, _ = self.run_cli('He wrote "Version 2" and the reply was: Hope this helps."\n',
                                     "--fail-on", "assistant residue")
        self.assertEqual(code, 1)
        # documented: an inch mark inside an open quotation ends it
        code, out, _, _ = self.run_cli('He said "as an AI language model, the 6" screen is fine.\n',
                                       "--fail-on", "assistant residue")
        self.assertEqual(code, 0)
        self.assertIn("[quoted]", out)

    def test_unclosed_quote_does_not_exempt_residue(self):
        code, _, _, _ = self.run_cli('He wrote "Hope this helps.\n\nNext paragraph.\n', "--fail-on", "assistant residue")
        self.assertEqual(code, 1)

    def test_multiline_quotations_are_quoted(self):
        for text in (
            "The transcript reads: «\nНадеюсь, это поможет.\n»\n",
            "He wrote “Thanks for the files.\nHope this helps.”\n",
            'He wrote "Thanks for the files.\nHope this helps."\n',
            "> The assistant replied:\nHope this helps.\n",
        ):
            with self.subTest(text=text):
                code, out, _, _ = self.run_cli(text, "--fail-on", "assistant residue")
                self.assertEqual(code, 0, out)
                self.assertIn("[quoted]", out)

    def test_residue_after_quotation_still_blocks(self):
        for text in (
            "The transcript reads: «\nСпасибо.\n» Надеюсь, это поможет.\n",
            "> The assistant replied:\nThanks.\n\nHope this helps.\n",
            '"Save" it. Hope this helps.\n',
        ):
            with self.subTest(text=text):
                code, _, _, _ = self.run_cli(text, "--fail-on", "assistant residue")
                self.assertEqual(code, 1)

    def test_escaped_straight_quote_is_not_a_delimiter(self):
        code, _, _, _ = self.run_cli('Type \\"x and Hope this helps \\" end.\n', "--fail-on", "assistant residue")
        self.assertEqual(code, 1)

    def gate(self, text):
        return self.run_cli(text, "--fail-on", "assistant residue")[0]

    def test_stray_formatted_opener_does_not_pair_with_later_inches(self):
        for text in (
            'He wrote "`save` Hope this helps. The 12" screen.\n',
            'He wrote *"Hope this helps. The 12" screen.\n',
            'He wrote "Hope this helps! The 12" screen.\n',
            'He wrote "Hope this helps? The 12" screen.\n',
        ):
            with self.subTest(text=text):
                self.assertEqual(self.gate(text), 1)
        self.assertTrue(lint.quoted_ranges(lint.quote_scan('"version 2"')))

    def test_fidelity_permissiveness_does_not_relax_the_gate(self):
        for text in (
            'The plan said: "we need\n- more time\n- more budget"\n',
            'The agent wrote: "The refund is processed weekly. Step 2"\n',
        ):
            with self.subTest(text=text):
                self.assertEqual(lint.quoted_ranges(lint.quote_scan(text)), [])
        for text in (
            'The plan said: "we need\n- Hope this helps.\n- more budget"\n',
            'The agent wrote: "Hope this helps. Step 2"\n',
        ):
            with self.subTest(text=text):
                self.assertEqual(self.gate(text), 1)

    def test_ellipsis_before_inches_discards_stray_quotation(self):
        for text in (
            'He wrote *"Hope this helps… The 12" screen.\n',
            'Он написал *"Надеюсь, это поможет… Экран 12".\n',
        ):
            with self.subTest(text=text):
                self.assertEqual(self.gate(text), 1)
        self.assertEqual(self.gate('He wrote *"Hope this helps…"*\n'), 0)
        self.assertEqual(self.gate('Он написал *"Надеюсь, это поможет…"*\n'), 0)

    def test_quoted_html_continuations_are_not_paragraphs(self):
        for opening, closing in (
            ("<script>", "</script>"), ("<pre>", "</pre>"),
            ("<STYLE>", "</STYLE>"), ("<textarea>", "</textarea>"),
            ("<!--", "-->"), ("<?php", "?>"),
            ("<!DOCTYPE", ">"), ("<![CDATA[", "]]>"),
        ):
            with self.subTest(opening=opening):
                self.assertEqual(self.gate(f"> {opening}\n> Hope this helps.\n"), 1)
                self.assertEqual(self.gate(f"> {opening}\n>\n> Hope this helps.\n"), 1)
                self.assertEqual(self.gate(f"> {opening}\n> {closing}\n> Hope this helps.\n"), 0)
                self.assertEqual(self.gate(f"> {opening}\n\n> Hope this helps.\n"), 0)
        self.assertEqual(self.gate("> <div>\n> Hope this helps.\n"), 1)
        self.assertEqual(self.gate("> <div>\n>\n> Hope this helps.\n"), 0)
        self.assertEqual(self.gate("> ```\n> <script>\n> ```\n> Hope this helps.\n"), 0)
        self.assertEqual(self.gate("> <script>\n> </script>\n> text\nHope this helps.\n"), 1)
        self.assertEqual(self.gate(">> <script>\n> Hope this helps.\n"), 0)

    def test_direct_raw_crlf_quotation_boundaries(self):
        for boundary in ("***", "___", "---", "==="):
            text = f'He said "first\r\n{boundary}\r\nHope this helps.\r\nend"\r\n'
            with self.subTest(boundary=boundary):
                self.assertEqual(lint.quoted_ranges(text), [])

    def test_tabs_at_blockquote_and_list_boundaries(self):
        for text in (
            "> Quote.\n-\titem\nHope this helps.\n",
            "> Quote.\n1.\titem\nHope this helps.\n",
            ">   \tcode\nHope this helps.\n",
            "> Intro\n>\t# H\nHope this helps.\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.gate(text), 1)
        for text in (
            ">\tQuote.\nHope this helps.\n",
            "> Intro\n>\tcontinued\nHope this helps.\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.gate(text), 0)

    def test_html_types_one_to_five_survive_blank_lines_until_their_end(self):
        for opening, closing in (
            ("<script>", "</script>"), ("<pre>", "</pre>"),
            ("<STYLE>", "</STYLE>"), ("<textarea>", "</textarea>"),
            ("<!--", "-->"), ("<?php", "?>"),
            ("<!DOCTYPE", ">"), ("<![CDATA[", "]]>"),
        ):
            with self.subTest(opening=opening):
                self.assertEqual(self.gate(opening + "\n\n> Owner: Quote.\nHope this helps.\n"), 1)
                self.assertEqual(self.gate(opening + "\n\n" + closing + "\n> Quote.\nHope this helps.\n"), 0)
                self.assertEqual(self.gate(opening + closing + "\n> Quote.\nHope this helps.\n"), 0)

    def test_inline_quotation_does_not_cross_a_block_start(self):
        for block in ("# Hope this helps.", "- Hope this helps.", "1. Hope this helps.",
                      "-\tHope this helps.", "---\nHope this helps.", "===\nHope this helps.",
                      "> Quote.\n---\nHope this helps.", "~~~\ncode\n~~~\nHope this helps."):
            for opening, closing in (('"', '"'), ("«", "»"), ("“", "”"), ("„", "“")):
                text = "He wrote " + opening + "see\n" + block + "\nend" + closing + "\n"
                with self.subTest(text=text):
                    self.assertEqual(self.gate(text), 1)
        self.assertEqual(self.gate('He said "first\nHope this helps.\nend" ok'), 0)

    def test_structural_line_numbers_use_only_newlines(self):
        for separator in ("\f", "\x85", "\u2028", "\u2029"):
            with self.subTest(separator=separator):
                self.assertIn((2, "bold-label bullet", "- **Label:** text"),
                              self.scan("A" + separator + "B\n- **Label:** text\n"))
                geometry = "".join(f"## Section {i}\n### First\n### Second\n" for i in range(6))
                self.assertEqual([item[0] for item in self.scan("A" + separator + "B\n" + geometry)
                                  if item[1] == "uniform heading geometry"], [2])

    def test_blockquote_ends_where_markdown_ends_it(self):
        for text in (
            "> A preserved quotation.\n---\nHope this helps.\n",
            "> # Heading\nHope this helps.\n",
            "> Quote.\n***\nНадеюсь, это поможет.\n",
            "> Quote.\n___\nHope this helps.\n",
            "> Quote.\n - - -\nHope this helps.\n",
            "> Quote.\n   ***\nHope this helps.\n",
            "> Quote.\n> ---\nHope this helps.\n",
            "> Quote.\n> ===\nHope this helps.\n",
            "> Quote.\n>\nHope this helps.\n",
            "> \nHope this helps.\n",
            "> > # Heading\nHope this helps.\n",
            "> ```\n> code\n> ```\nHope this helps.\n",
            "> ```\n> code\nHope this helps.\n",
            ">     indented code\nHope this helps.\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.gate(text), 1)

    def test_blockquote_lazy_continuation_stays_quoted(self):
        for text in (
            "> A quotation\nHope this helps.\n",
            "> A quotation\n    Hope this helps.\n",
            "> A quotation\n===\nHope this helps.\n",
            "> # Heading\n> Hope this helps.\n",
            "> Quote.\n>\n> Hope this helps.\n",
            "> > Nested\nHope this helps.\n",
        ):
            with self.subTest(text=text):
                code, out, _, _ = self.run_cli(text, "--fail-on", "assistant residue")
                self.assertEqual(code, 0, out)
                self.assertIn("[quoted]", out)

    def test_straight_quotation_with_emphasis_or_code_at_the_edge_is_quoted(self):
        for text in (
            'He wrote **"Hope this helps."**\n',
            'He wrote *"Hope this helps."*\n',
            'He wrote _"Hope this helps."_\n',
            'He wrote "`save` Hope this helps."\n',
            'He wrote "Hope this helps. Use `save`".\n',
        ):
            with self.subTest(text=text):
                code, out, _, _ = self.run_cli(text, "--fail-on", "assistant residue")
                self.assertEqual(code, 0, out)
                self.assertIn("[quoted]", out)

    def test_emphasis_and_code_edges_do_not_widen_the_exemption(self):
        for text in (
            'A 12" pipe. Hope this helps.\n',
            'He wrote "fine." Hope this helps.\n',
            'He wrote **"fine."** Hope this helps.\n',
            'He wrote "`save`" Hope this helps.\n',
            'He wrote **"Hope this helps.\n',
            'He wrote "Hope this helps. Use `save`.\n',
            'He wrote snake_"Hope this helps."\n',
        ):
            with self.subTest(text=text):
                self.assertEqual(self.gate(text), 1)

    def test_code_outside_a_quotation_is_a_boundary(self):
        for text in (
            'He wrote "Hope this helps."`x`\n',
            'He wrote `x`"Hope this helps."\n',
            'He wrote `x`"Hope this helps."`y`\n',
            'He wrote "`x`"Hope this helps."\n',
        ):
            with self.subTest(text=text):
                code, out, _, _ = self.run_cli(text, "--fail-on", "assistant residue")
                self.assertEqual(code, 0, out)
                self.assertIn("[quoted]", out)
        for text in (
            'A 12" pipe. Hope this helps.\n',
            'A 12`x`" pipe. Hope this helps.\n',
            'A 12`x`"pipe. Hope this helps.\n',
            'He wrote "fine."`x` Hope this helps.\n',
            'He wrote `x`"fine." Hope this helps.\n',
            'He wrote "Hope this helps."**Bold** end.\n',  # known: emphasis followed by a word is no boundary
        ):
            with self.subTest(text=text):
                self.assertEqual(self.gate(text), 1)

    def test_nested_container_in_a_blockquote_ends_lazy_quoting(self):
        # a list item, HTML block or link reference definition anywhere in the quote: the gate
        # blocks an unmarked line after it (CommonMark would sometimes still quote it)
        for text in (
            "> - # Heading\nHope this helps.\n",
            "> -\nHope this helps.\n",
            "> - ***\nHope this helps.\n",
            "> - ```\n> code\nHope this helps.\n",
            "> - ```\n> code\n> ```\n> text\nHope this helps.\n",
            "> - ```\n>   code\nHope this helps.\n",
            "> -     code\nHope this helps.\n",
            "> - > # H\nHope this helps.\n",
            "> - >\nHope this helps.\n",
            "> - [foo]: /url\nHope this helps.\n",
            "> 1. # Heading\nHope this helps.\n",
            "> 1) ---\nHope this helps.\n",
            "> - item\nHope this helps.\n",
            "> 1. item\nHope this helps.\n",
            "> - - item\nHope this helps.\n",
            "> + item\nHope this helps.\n",
            "> Intro\n> - item\nHope this helps.\n",
            "> - item\n> More text\nHope this helps.\n",
            ">> - item\nHope this helps.\n",
            "> <div>\nHope this helps.\n",
            "> </div>\nHope this helps.\n",
            "> <!-- c -->\nHope this helps.\n",
            "> <?php\nHope this helps.\n",
            "> [foo]: /url\nHope this helps.\n",
            "> * * *\nHope this helps.\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.gate(text), 1)

    def test_html_block_ends_a_quote_and_swallows_quote_markers(self):
        for text in (
            "> text\n<div>\nHope this helps.\n",
            "> text\n<!-- c -->\nHope this helps.\n",
            "> text\n</div>\nHope this helps.\n",
            "> text\n<span>x</span>\nHope this helps.\n",  # CommonMark quotes this; the gate blocks
            "<div>\n> Quote text\nHope this helps.\n",
            "<div>1. x\n>> Quote text\nHope this helps.\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.gate(text), 1)
        code, out, _, _ = self.run_cli("<div>\n\n> Quote text\nHope this helps.\n", "--fail-on", "assistant residue")
        self.assertEqual(code, 0, out)  # a blank line ends the HTML block, so the quote is real
        self.assertIn("[quoted]", out)

    def test_blockquote_lazy_controls_stay_quoted(self):
        for text in (
            "> A quotation\nHope this helps.\n",
            ">> deep quote\nHope this helps.\n",
            "> A quotation\n===\nHope this helps.\n",
            "> # Title\n> Quote text\nHope this helps.\n",
            "> 1.5 million\nHope this helps.\n",
            "> -5 degrees\nHope this helps.\n",
            "> *emphasis* and text\nHope this helps.\n",
            "> a <b>bold</b> word\nHope this helps.\n",
            "> ```\n> - not a list\n> ```\n> text\nHope this helps.\n",  # list-like text inside a quote-level fence
        ):
            with self.subTest(text=text):
                code, out, _, _ = self.run_cli(text, "--fail-on", "assistant residue")
                self.assertEqual(code, 0, out)
                self.assertIn("[quoted]", out)

    def test_container_flag_does_not_leak_into_the_next_blockquote(self):
        self.assertEqual(self.gate("> - item\n\n> A quotation\nHope this helps.\n"), 0)

    def test_nul_in_input_is_not_a_code_boundary(self):
        for text in (
            b'A 12\x00"pipe is fine. Hope this helps. The 6" model.\n',
            b'A \x00"pipe is fine. Hope this helps. The 6" model.\n',
        ):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "sample.md"
                path.write_bytes(text)
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(lint.main(["prose_lint.py", "--fail-on", "assistant residue", str(path)]), 1)

    def test_quote_ends_with_crlf_and_cr_line_endings(self):
        for ending in ("\r\n", "\r"):
            for text in (
                "> Quote.{0}---{0}Hope this helps.{0}",
                "> Quote.{0}***{0}Hope this helps.{0}",
                "> # Heading{0}Hope this helps.{0}",
                "> - item{0}Hope this helps.{0}",
                "> <div>{0}Hope this helps.{0}",
            ):
                text = text.format(ending)
                with self.subTest(text=text):
                    self.assertEqual(self.gate(text), 1)
            with self.subTest(ending=ending):
                self.assertEqual(self.gate("> A quotation{0}Hope this helps.{0}".format(ending)), 0)

    def test_blockquote_ranges_on_raw_cr_and_crlf_text(self):
        for ending in ("\r", "\r\n"):
            quote, rest = "> Quote." + ending, "---" + ending + "Hope this helps." + ending
            self.assertEqual(lint._blockquote_ranges(quote + rest), [(0, len(quote))])
            self.assertEqual(lint.quoted_ranges(quote + rest), [(0, len(quote))])
            lazy = "> Quote." + ending + "Hope this helps." + ending
            self.assertEqual(lint._blockquote_ranges(lazy), [(0, len(lazy))])
            heading = "> # H" + ending + "Hope this helps." + ending
            self.assertEqual(lint._blockquote_ranges(heading), [(0, len("> # H" + ending))])
            listed = "> - a" + ending + "Hope this helps." + ending
            self.assertEqual(lint._blockquote_ranges(listed), [(0, len("> - a" + ending))])

    def test_stacked_short_lines_are_numbered_by_bisect(self):
        filler = "A separating sentence that is clearly longer than forty-five characters.\n"
        text = "Plain line without a stop\n" * 2000 + "".join(
            f"Short {i}.\nTiny {i}.\nBrief {i}.\n{filler}" for i in range(50))
        found = [item[0] for item in self.scan(text) if item[1] == "stacked short-sentence rhythm"]
        self.assertEqual(len(found), 50)
        expected = [text[:m.start()].count("\n") + 1 for m in lint.STACKED_SHORT.finditer(lint.strip_code_fences(text))]
        self.assertEqual(found, expected)

    def test_line_numbers_count_every_line_ending(self):
        residue = lambda text: [item for item in self.scan(text) if item[1] == "assistant residue"]
        self.assertEqual(residue("One.\r\nTwo.\n\n\nHope this helps.\n"), [(5, "assistant residue", "Hope this helps")])
        self.assertEqual(residue("One.\rHope this helps.\r"), [(2, "assistant residue", "Hope this helps")])  # read_text turns CR into "\\n"

    def test_range_lookup_matches_brute_force(self):
        import random
        rng = random.Random(23)
        for _ in range(300):
            ranges = []
            for _ in range(rng.randint(0, 12)):
                start = rng.randint(0, 40)
                ranges.append((start, start + rng.randint(1, 15)))
            contains = lint._range_lookup(ranges)
            for start in range(0, 50):
                for end in range(start, start + 8):
                    self.assertEqual(contains(start, end),
                                     any(a <= start and end <= b for a, b in ranges), (ranges, start, end))

    def test_paragraph_split_matches_the_reference_regex(self):
        import random
        import re
        reference = re.compile(r"(?:[^\n]*\S[^\n]*(?:\n|$))+")
        rng = random.Random(11)
        pieces = ["a", " ", "\n", "\r\n", "\r", "\t", "\f", "\u2028", "\x85", "\n\n", "  "]
        for _ in range(3000):
            text = "".join(rng.choice(pieces) for _ in range(rng.randint(0, 14)))
            self.assertEqual(list(lint._paragraphs(text)),
                             [(m.start(), m.group(0)) for m in reference.finditer(text)], repr(text))

    def test_degenerate_lines_lint_in_linear_time(self):
        import time
        for text in (" " * 50000 + "\n", " " * 50000, "*_\"" * 17000 + "\n", '"' * 50000 + "\n",
                     ">" * 50000 + "\n", "> " * 25000 + "\n", "*" * 50000 + "\n", "_" * 50000 + "\n",
                     '"*' * 25000 + "\n", "\n".join(" " * 100 for _ in range(500)),
                     'He said "Hope this helps." ' * 10000 + "\n", "> Hope this helps.\n" * 10000,
                     "- 1. " * 10000 + "x\n", "> - 1. " * 10000 + "x\n", "1. " * 20000 + "\n", "`" * 50000 + "\n"):
            with self.subTest(length=len(text)):
                start = time.monotonic()
                self.scan(text)
                self.assertLess(time.monotonic() - start, 2)

    def test_legitimate_prose_passes_strong_label(self):
        text = (
            "Уважаемый Иван! С радостью помогу подготовить документы к заседанию.\n"
            "> Владелец: «Давайте разберёмся в причинах задержки».\n"
            "The distinction is between a draft and an accepted decision. That distinction matters.\n"
            "Давайте разберёмся с графиком на следующей неделе.\n"
        )
        code, _, _, _ = self.run_cli(text, "--fail-on", "assistant residue")
        self.assertEqual(code, 0)

    def test_russian_chatbot_residue_is_report_only_label(self):
        findings = self.scan("Давайте разберёмся. С радостью помогу.\n")
        self.assertEqual([item[1] for item in findings].count("russian chatbot residue"), 2)

    def test_assistant_residue(self):
        findings = self.scan(
            "Great question. As an AI language model, I cannot. Hope this helps.\n"
            "Отличный вопрос! Надеюсь, это поможет. Как языковая модель, я не могу.\n"
        )
        self.assertEqual([item[1] for item in findings].count("assistant residue"), 6)

    def test_abstract_metaphor_noun_is_candidate(self):
        findings = self.scan("The flywheel is the north star of this substrate.\n")
        self.assertEqual([item[1] for item in findings].count("abstract metaphor noun"), 3)

    def labels(self, text):
        return [item[1] for item in self.scan(text)]

    def test_chatbot_citation_markup(self):
        text = (
            "Revenue grew in 2025. :contentReference[oaicite:1]{index=1}\n"
            "It opened in 1998 turn0search3 and closed in 2004 [cite: 2, 5].\n"
            "The mayor resigned 【4:0†source】 and grok_card followed.\n"
        )
        self.assertEqual(self.labels(text).count("chatbot artifact"), 5)

    def test_ai_referral_parameter_in_link(self):
        text = (
            "Source: https://www.theguardian.com/sport/2025/feb/11/interview?utm_source=chatgpt.com\n"
            "Also [this](https://example.org/a?x=1&referrer=grok.com) and https://site.test/p?utm_source=openai.\n"
        )
        self.assertEqual(self.labels(text).count("chatbot artifact"), 3)

    def test_ordinary_tracking_and_code_markup_are_not_artifacts(self):
        text = (
            "Read https://example.org/post?utm_source=newsletter&utm_medium=email.\n"
            "The leak looks like `contentReference[oaicite:1]` or `?utm_source=chatgpt.com`.\n"
        )
        self.assertNotIn("chatbot artifact", self.labels(text))

    def test_inline_code_scanner_matches_reference_regex(self):
        import random
        rng = random.Random(7)
        pieces = ["`", "``", "```", "a", " ", "\n", "\r\n", "\r", "\f", "\v", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029", "b`c", "````"]
        for _ in range(5000):
            text = "".join(rng.choice(pieces) for _ in range(rng.randint(0, 12)))
            self.assertEqual(lint._inline_code_spans(text),
                             [match.span() for match in lint.INLINE_CODE.finditer(text)], repr(text))

    def test_long_backtick_runs_are_linear(self):
        import time
        start = time.monotonic()
        lint.code_ranges("`" * 200000 + " a ` b " * 20000)
        lint.code_ranges("".join("`" * length + "a" for length in range(1, 900)))  # distinct run lengths
        self.assertLess(time.monotonic() - start, 2)

    def test_unicode_separator_does_not_end_a_fence(self):
        ranges = lint.code_ranges("```\na\u2029```\nb\n")
        self.assertEqual(ranges, [(0, len("```\na\u2029```\nb\n"))])

    def test_lone_cr_ends_a_closing_fence(self):
        self.assertEqual(lint.code_ranges("```\na\n```\rprose"), [(0, 10)])

    def test_form_feed_does_not_end_inline_code(self):
        self.assertEqual(self.scan("`x\fthat distinction matters`\n"), [])

    def test_glued_artifact_markers(self):
        text = "Revenue grew in 1998turn0search0. It closed citeturn0news2 later.\n"
        self.assertEqual(self.labels(text).count("chatbot artifact"), 2)

    def test_quoted_link_artifact_does_not_block(self):
        for text in ['He wrote "https://x.test/?utm_source=chatgpt.com".\n',
                     "Он написал: «https://x.test/?utm_source=chatgpt.com».\n",
                     "He wrote “https://x.test/?utm_source=chatgpt.com” and left.\n"]:
            code, out, _, _ = self.run_cli(text, "--fail-on", "chatbot artifact")
            self.assertEqual(code, 0, text)
            self.assertIn("chatbot artifact [quoted]", out, text)

    def test_unquoted_link_artifact_after_quoted_link_blocks(self):
        text = 'See "https://a.test/" and https://b.test/?utm_source=openai today.\n'
        code, _, _, _ = self.run_cli(text, "--fail-on", "chatbot artifact")
        self.assertEqual(code, 1)

    def test_artifact_label_can_block(self):
        code, out, _, _ = self.run_cli("Founded in 1990.turn0search0\n", "--fail-on", "chatbot artifact")
        self.assertEqual(code, 1)
        self.assertIn("[blocking]", out)

    def test_placeholder_text(self):
        text = (
            "Travomate was founded in [Year] by [Founder Names].\n"
            "Accessed 2026-xx-xx at INSERT_SOURCE_URL_01 and https://example.com/source2.\n"
            "Компания [Название компании] основана [Дата рождения]; [вставьте ссылку].\n"
        )
        self.assertEqual(self.labels(text).count("placeholder text"), 8)

    def test_ordinary_brackets_are_not_placeholders(self):
        text = "As reported [1], the fee [sic] was waived (if applicable) by the insert team.\n"
        self.assertNotIn("placeholder text", self.labels(text))

    def test_markdown_link_text_is_not_a_placeholder(self):
        text = "See [Add note](https://example.org/n) and [Year][ref].\n\n[date]: https://example.org/x\n"
        self.assertNotIn("placeholder text", self.labels(text))

    def test_new_chatbot_residue(self):
        text = (
            "Would you like me to format it? Here is a revised version of the text.\n"
            "It's important to note that delete this section before submission.\n"
            "Хотите, я подготовлю письмо? Вот исправленный вариант.\n"
        )
        found = self.labels(text)
        self.assertEqual(found.count("chatbot residue"), 4)
        self.assertEqual(found.count("russian chatbot residue"), 2)

    def test_corrective_disclaimer(self):
        text = (
            "The account should be treated as tradition rather than verified fact.\n"
            "The records do not themselves establish his role, based on available information.\n"
            "Это следует рассматривать как предание, а не как факт. Само по себе не доказывает связь.\n"
        )
        self.assertEqual(self.labels(text).count("corrective disclaimer"), 5)

    def test_plain_evidence_limit_is_not_a_disclaimer(self):
        text = "The 2019 extract lists him as director; no later extract was found. A refund in progress does not establish completion.\n"
        self.assertNotIn("corrective disclaimer", self.labels(text))

    def test_procedural_assurance(self):
        text = (
            "Revised the lead to ensure neutrality while preserving the original meaning.\n"
            "Improved clarity and flow in line with the guidelines.\n"
            "Текст отредактирован с сохранением исходного смысла; улучшена читаемость.\n"
        )
        self.assertEqual(self.labels(text).count("procedural assurance"), 6)


if __name__ == "__main__":
    unittest.main()
