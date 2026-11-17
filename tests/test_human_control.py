"""Offline checks for the human-control measurement: no test touches the network."""

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


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

    def test_blockquote_stays_quoted_through_measurement(self):
        html = "<blockquote><p>Hope this helps.</p></blockquote><p>Tea is a drink.</p>"
        prose = control.extract_prose(html)
        self.assertEqual(prose, "> Hope this helps.\n\nTea is a drink.\n")
        with tempfile.TemporaryDirectory() as directory:
            control.store(Path(directory), entry(), prose)
            code = control.measure([entry()], Path(directory), offline=True,
                                   fail_on=set(control.DEFAULT_FAIL_ON), out=io.StringIO())
        self.assertEqual(code, 0)

    def test_inline_q_stays_quoted_through_measurement(self):
        html = "<p>The sign read <q>hope this helps</q> in red.</p>"
        prose = control.extract_prose(html)
        self.assertEqual(prose, "The sign read “hope this helps” in red.\n")
        with tempfile.TemporaryDirectory() as directory:
            control.store(Path(directory), entry(), prose)
            control.store(Path(directory), entry(revid=2), control.extract_prose("<p>Hope this helps.</p>"))
            out = io.StringIO()
            code = control.measure([entry(), entry(revid=2)], Path(directory), offline=True,
                                   fail_on=set(control.DEFAULT_FAIL_ON), out=out)
        self.assertEqual(code, 1)
        self.assertIn("Unquoted blocking matches in human text: 1", out.getvalue())

    def test_strips_russian_footnote_marks_and_entities(self):
        html = "<p>Чай&nbsp;&mdash; напиток[нет АИ].</p>"
        self.assertEqual(control.extract_prose(html), "Чай — напиток.\n")


    def test_skipped_paragraph_does_not_close_the_open_one(self):
        html = "<p>Before <figure><p>Caption</p></figure>after the figure.</p>"
        self.assertEqual(control.extract_prose(html), "Before after the figure.\n")

    def test_line_break_separates_words(self):
        for html in ("<p>First<br>Second.</p>", "<p>First<br/>Second.</p>"):
            self.assertEqual(control.extract_prose(html), "First Second.\n")

    def test_word_count_counts_unicode_word_runs(self):
        self.assertEqual(control.word_count("don't 3.14 state-of-the-art"), 8)


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

    def test_rejects_malformed_timestamp_and_revid(self):
        for bad in ({"timestamp": ""}, {"timestamp": "2022-11-01"}, {"revid": 0},
                    {"revid": "1"}, {"revid": True}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                control.check_entry(entry(**bad))

    def test_rejects_impossible_calendar_date(self):
        with self.assertRaises(ValueError):
            control.check_entry(entry(timestamp="2022-02-31T00:00:00Z"))

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
                control.store(cache, item, text)
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
        self.assertIn("Unquoted blocking matches in human text: 0", report)

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
        with redirect_stderr(err):
            self.assertEqual(control.main(["human_control.py", "--offline", "--fail-on", "nope"]), 2)
        self.assertIn("unknown label", err.getvalue())


class FakeResponse(io.BytesIO):
    def __init__(self, payload, headers=None):
        super().__init__(json.dumps(payload).encode())
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def responses(*payloads):
    """Patch urlopen to return the payloads in order and never touch the network."""
    queue = list(payloads)

    def fake(request, timeout=None):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    return mock.patch.object(control.urllib.request, "urlopen", side_effect=fake)


def http_client_incomplete():
    import http.client
    return http.client.IncompleteRead(b"{}", 98)


def meta(revid, timestamp):
    return {"query": {"pages": {"1": {"title": "Sample", "revisions": [
        {"revid": revid, "timestamp": timestamp}]}}}}


class NetworkGuardTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(control.time, "sleep")
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def test_offline_and_resolve_are_exclusive_and_make_no_request(self):
        with responses() as urlopen, redirect_stderr(io.StringIO()):
            code = control.main(["human_control.py", "--offline", "--resolve", "en.wikipedia.org", "Tea"])
        self.assertEqual(code, 2)
        urlopen.assert_not_called()

    def test_empty_manifest_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "m.json"
            manifest.write_text(json.dumps({"cutoff": control.CUTOFF, "revisions": []}))
            with redirect_stderr(io.StringIO()):
                code = control.main(["human_control.py", "--offline", "--manifest", str(manifest),
                                     "--cache", directory])
        self.assertEqual(code, 2)

    def test_cached_file_without_words_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            item = entry()
            control.store(Path(directory), item, "\n")
            with self.assertRaises(ValueError):
                control.measure([item], Path(directory), offline=True,
                                fail_on=set(control.DEFAULT_FAIL_ON), out=io.StringIO())

    def test_fetch_rejects_a_different_revision(self):
        with responses(meta(2, "2022-11-01T00:00:00Z")):
            with self.assertRaises(ValueError):
                control.fetch_revision(entry())

    def test_fetch_rejects_parse_of_a_different_revision(self):
        parsed = {"parse": {"revid": 2, "text": {"*": "<p>Text.</p>"}}}
        with responses(meta(1, "2022-11-01T00:00:00Z"), parsed):
            with self.assertRaises(ValueError):
                control.fetch_revision(entry())

    def test_fetch_rejects_revision_without_prose_and_caches_nothing(self):
        parsed = {"parse": {"revid": 1, "text": {"*": "<table><tr><td>x</td></tr></table>"}}}
        with tempfile.TemporaryDirectory() as directory:
            with responses(meta(1, "2022-11-01T00:00:00Z"), parsed):
                with self.assertRaises(ValueError):
                    control.measure([entry()], Path(directory), offline=False,
                                    fail_on=set(control.DEFAULT_FAIL_ON), out=io.StringIO())
            self.assertEqual(list(Path(directory).rglob("*")), [])

    def test_fetch_writes_cache_and_measures(self):
        parsed = {"parse": {"revid": 1, "text": {"*": "<p>Tea is a drink.</p>"}}}
        with tempfile.TemporaryDirectory() as directory:
            with responses(meta(1, "2022-11-01T00:00:00Z"), parsed):
                code = control.measure([entry()], Path(directory), offline=False,
                                       fail_on=set(control.DEFAULT_FAIL_ON), out=io.StringIO())
            self.assertEqual(code, 0)
            names = [p.name for p in control.cache_dir(Path(directory)).iterdir()]
            digest = control._digest(b"Tea is a drink.\n")
            self.assertEqual(names, [f"en-1.{digest}.md"])

    def test_api_error_is_reported_not_retried(self):
        with responses({"error": {"code": "nosuchrevid", "info": "no revision"}}) as urlopen:
            with self.assertRaises(ValueError):
                control.fetch_revision(entry())
        self.assertEqual(urlopen.call_count, 1)

    def test_rate_limit_error_is_retried(self):
        with responses({"error": {"code": "ratelimited"}}, meta(1, "2022-11-01T00:00:00Z"),
                       {"parse": {"revid": 1, "text": {"*": "<p>Tea.</p>"}}}) as urlopen:
            self.assertEqual(control.fetch_revision(entry()), "Tea.\n")
        self.assertEqual(urlopen.call_count, 3)

    def test_http_429_honors_retry_after(self):
        throttled = control.urllib.error.HTTPError("u", 429, "Too Many Requests",
                                                   {"Retry-After": "60"}, None)
        with responses(throttled, meta(1, "2022-11-01T00:00:00Z"),
                       {"parse": {"revid": 1, "text": {"*": "<p>Tea.</p>"}}}):
            control.fetch_revision(entry())
        self.assertIn(mock.call(60.0), self.sleep.call_args_list)

    def test_truncated_response_is_a_network_failure_exit_2(self):
        truncated = http_client_incomplete()
        with responses(truncated, truncated, truncated, truncated) as urlopen, \
                redirect_stderr(io.StringIO()) as err, redirect_stdout(io.StringIO()):
            code = control.main(["human_control.py", "--resolve", "en.wikipedia.org", "Tea"])
        self.assertEqual(code, 2)
        self.assertEqual(urlopen.call_count, 4)
        self.assertIn("IncompleteRead", err.getvalue())

    def test_body_cut_mid_character_is_retried(self):
        class Cut(FakeResponse):
            def __init__(self):
                io.BytesIO.__init__(self, '{"query": "Ч'.encode("utf-8")[:-1])
                self.headers = {}

        payloads = [Cut(), meta(5, "2022-11-01T00:00:00Z")]

        def fake(request, timeout=None):
            item = payloads.pop(0)
            return item if isinstance(item, FakeResponse) else FakeResponse(item)

        with mock.patch.object(control.urllib.request, "urlopen", side_effect=fake):
            self.assertEqual(control.resolve("en.wikipedia.org", "Sample")["revid"], 5)

    def test_empty_pages_exits_2_without_traceback(self):
        with responses({"query": {"pages": {}}}), redirect_stderr(io.StringIO()) as err, \
                redirect_stdout(io.StringIO()):
            code = control.main(["human_control.py", "--resolve", "en.wikipedia.org", "Tea"])
        self.assertEqual(code, 2)
        self.assertIn("malformed API response", err.getvalue())

    def test_resolve_asks_for_revisions_strictly_before_cutoff(self):
        with responses(meta(5, "2022-11-29T23:59:59Z")) as urlopen:
            found = control.resolve("en.wikipedia.org", "Sample")
        self.assertEqual(found["revid"], 5)
        self.assertIn("rvstart=2022-11-29T23%3A59%3A59Z", urlopen.call_args.args[0].full_url)
        with responses(meta(6, control.CUTOFF)), self.assertRaises(ValueError):
            control.resolve("en.wikipedia.org", "Sample")


class CacheIntegrityTests(unittest.TestCase):
    def measure_offline(self, cache):
        return control.measure([entry()], cache, offline=True,
                               fail_on=set(control.DEFAULT_FAIL_ON), out=io.StringIO())

    def test_truncated_text_is_not_trusted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = control.store(Path(directory), entry(),
                                 "Opening paragraph.\n\nThe host said: hope this helps.\n")
            path.write_text("Opening paragraph.\n", encoding="utf-8")  # interrupted rewrite
            self.assertIsNone(control.load(Path(directory), entry()))
            with self.assertRaises(FileNotFoundError):
                self.measure_offline(Path(directory))

    def test_render_from_an_older_extractor_is_ignored(self):
        text = "Hope this helps.\n"  # a v3 render lost the blockquote marker
        with tempfile.TemporaryDirectory() as directory:
            old = Path(directory) / "v3" / f"en-1.{control._digest(text.encode())}.md"
            old.parent.mkdir()
            old.write_text(text, encoding="utf-8")
            self.assertIsNone(control.load(Path(directory), entry()))
            with self.assertRaises(FileNotFoundError):
                self.measure_offline(Path(directory))

    def test_old_format_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            for old in ("en-1.md", "v2/en-1.md"):
                (Path(directory) / old).parent.mkdir(exist_ok=True)
                (Path(directory) / old).write_text("Opening paragraph.\n", encoding="utf-8")
            (Path(directory) / "v2/en-1.md.sha256").write_text(
                control._digest(b"Opening paragraph.\n") + "\n", encoding="ascii")
            with self.assertRaises(FileNotFoundError):
                self.measure_offline(Path(directory))

    def test_incomplete_cache_is_fetched_again_online(self):
        parsed = {"parse": {"revid": 1, "text": {"*": "<p>The host said: hope this helps.</p>"}}}
        with tempfile.TemporaryDirectory() as directory:
            path = control.store(Path(directory), entry(), "Opening.\n")
            path.write_text("Open\n", encoding="utf-8")
            with mock.patch.object(control.time, "sleep"), responses(meta(1, "2022-11-01T00:00:00Z"), parsed):
                code = control.measure([entry()], Path(directory), offline=False,
                                       fail_on=set(control.DEFAULT_FAIL_ON), out=io.StringIO())
            self.assertEqual(code, 1)

    def test_two_valid_renders_are_ambiguous(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            control.store(cache, entry(), "Clean render.\n")
            control.store(cache, entry(), "The host said: hope this helps.\n")
            with self.assertRaises(ValueError):
                self.measure_offline(cache)

    def test_concurrent_render_during_fetch_is_not_silently_chosen(self):
        parsed = {"parse": {"revid": 1, "text": {"*": "<p>The host said: hope this helps.</p>"}}}
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            real_fetch = control.fetch_revision

            def fetch_while_another_writer_stores(item):
                control.store(cache, item, "Clean render.\n")
                return real_fetch(item)

            with mock.patch.object(control.time, "sleep"), \
                    mock.patch.object(control, "fetch_revision", side_effect=fetch_while_another_writer_stores), \
                    responses(meta(1, "2022-11-01T00:00:00Z"), parsed):
                with self.assertRaises(ValueError):
                    control.measure([entry()], cache, offline=False,
                                    fail_on=set(control.DEFAULT_FAIL_ON), out=io.StringIO())

    def test_file_replaced_after_verification_is_not_linted(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            path = control.store(cache, entry(), "The host said: hope this helps.\n")
            real_load = control.load

            def load_then_swap(*args):
                text = real_load(*args)
                path.write_text("Clean text.\n", encoding="utf-8")  # concurrent replacement
                return text

            with mock.patch.object(control, "load", side_effect=load_then_swap):
                self.assertEqual(self.measure_offline(cache), 1)

    def test_each_writer_uses_its_own_temporary_file(self):
        sources = []
        real_replace = control.os.replace

        def spy(source, target):
            sources.append(source)
            real_replace(source, target)

        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(control.os, "replace", side_effect=spy):
            path = Path(directory) / "v3" / "en-1.x.md"
            control._write_atomic(path, b"first")
            control._write_atomic(path, b"second")
            self.assertEqual(path.read_bytes(), b"second")
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["en-1.x.md"])
        self.assertEqual(len(set(sources)), 2)


class RetryAfterTests(unittest.TestCase):
    NOW = control.datetime(2026, 11, 18, 12, 0, 0, tzinfo=control.timezone.utc)

    def test_delta_seconds_within_budget(self):
        self.assertEqual(control._retry_after("60", 0, now=self.NOW), 60.0)

    def test_http_date(self):
        self.assertEqual(control._retry_after("Wed, 18 Nov 2026 12:01:00 GMT", 0, now=self.NOW), 60.0)

    def test_delay_beyond_budget_stops_instead_of_retrying_early(self):
        for value in ("180", "Wed, 18 Nov 2026 12:03:00 GMT"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                control._retry_after(value, 0, now=self.NOW)

    def test_missing_or_unparseable_value_backs_off(self):
        self.assertEqual(control._retry_after(None, 1, now=self.NOW), 20.0)
        self.assertEqual(control._retry_after("soon", 0, now=self.NOW), 10.0)


if __name__ == "__main__":
    unittest.main()
