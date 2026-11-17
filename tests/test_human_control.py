"""Offline checks for the human-control measurement: no test touches the network."""

import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("human_control", ROOT / "scripts" / "human_control.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


def entry(**overrides):
    value = {"host": "en.wikipedia.org", "title": "Sample", "revid": 1,
             "timestamp": "2022-11-01T00:00:00Z"}
    value.update(overrides)
    return value


class ExtractProseTests(unittest.TestCase):
    def test_keeps_paragraphs_and_drops_non_prose(self):
        html = (
            '<div><p>Bread is a staple<sup class="reference">[1]</sup> food.</p>'
            "<table><tr><td><p>Cell text</p></td></tr></table>"
            "<ul><li>List item</li></ul>"
            "<figure><figcaption>Caption</figcaption></figure>"
            "<p>It is baked<math>x^2</math> in an oven.[2]</p><p> </p></div>"
        )
        self.assertEqual(control.extract_prose(html),
                         "Bread is a staple food.\n\nIt is baked in an oven.\n")

    def test_strips_russian_footnote_marks_and_entities(self):
        html = "<p>Чай&nbsp;&mdash; напиток[нет АИ].</p>"
        self.assertEqual(control.extract_prose(html), "Чай — напиток.\n")


class ManifestTests(unittest.TestCase):
    def test_pinned_manifest_predates_cutoff(self):
        manifest = json.loads((ROOT / "tests" / "human_control.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["cutoff"], control.CUTOFF)
        entries = manifest["revisions"]
        self.assertGreaterEqual(len(entries), 20)
        self.assertEqual({e["host"] for e in entries}, set(control.HOSTS))
        for item in entries:
            control.check_entry(item)
        ids = [(e["host"], e["revid"]) for e in entries]
        self.assertEqual(len(ids), len(set(ids)))

    def test_rejects_revision_saved_at_or_after_cutoff(self):
        for stamp in (control.CUTOFF, "2023-01-01T00:00:00Z"):
            with self.assertRaises(ValueError):
                control.check_entry(entry(timestamp=stamp))

    def test_rejects_unknown_host_and_missing_field(self):
        with self.assertRaises(ValueError):
            control.check_entry(entry(host="example.org"))
        broken = entry()
        del broken["revid"]
        with self.assertRaises(ValueError):
            control.check_entry(broken)


class MeasureTests(unittest.TestCase):
    def run_measure(self, texts, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            entries = []
            for number, (host, text) in enumerate(texts, 1):
                item = entry(host=host, revid=number, title=f"T{number}")
                control.cache_path(cache, item).write_text(text, encoding="utf-8")
                entries.append(item)
            out = io.StringIO()
            code = control.measure(entries, cache, offline=True,
                                   fail_on=set(control.DEFAULT_FAIL_ON), out=out, **kwargs)
            return code, out.getvalue()

    def test_reports_rates_per_language(self):
        code, report = self.run_measure([
            ("en.wikipedia.org", "Tea is not a drink of the poor but of the court.\n"),
            ("ru.wikipedia.org", "Чай пьют не только в Китае.\n"),
        ])
        self.assertEqual(code, 0)
        self.assertIn("[en] 12 words", report)
        self.assertIn("formulaic contrast: 1 (83.33 per 1,000 words)", report)
        self.assertIn("[ru] 6 words", report)
        self.assertIn("russian formulaic contrast: 1 (166.67 per 1,000 words)", report)
        self.assertIn("Blocking matches in human text: 0", report)

    def test_blocking_label_in_human_text_fails(self):
        code, report = self.run_measure([("en.wikipedia.org", "The host said: hope this helps.\n")])
        self.assertEqual(code, 1)
        self.assertIn("BLOCKING in human text: T1 (1) L1: assistant residue", report)

    def test_quoted_blocking_label_does_not_fail(self):
        code, _ = self.run_measure([("en.wikipedia.org", 'The sign read "hope this helps" in red.\n')])
        self.assertEqual(code, 0)

    def test_offline_requires_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                control.measure([entry()], Path(directory), offline=True,
                                fail_on=set(control.DEFAULT_FAIL_ON), out=io.StringIO())

    def test_cli_rejects_unknown_label(self):
        err = io.StringIO()
        from contextlib import redirect_stderr
        with redirect_stderr(err):
            self.assertEqual(control.main(["human_control.py", "--offline", "--fail-on", "nope"]), 2)
        self.assertIn("unknown label", err.getvalue())


if __name__ == "__main__":
    unittest.main()
