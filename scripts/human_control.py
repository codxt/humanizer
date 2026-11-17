#!/usr/bin/env python3
"""Measure the prose linter against human writing from before ChatGPT.

Usage:
    python3 -S scripts/human_control.py [--cache DIR] [--offline] [--fail-on LABEL ...] [--manifest FILE]
    python3 -S scripts/human_control.py --resolve HOST TITLE

The manifest (default `tests/human_control.json`) pins Wikipedia revisions saved before
ChatGPT's public release on 30 November 2022, so every word in them was written by people.
The script fetches each pinned revision once through the MediaWiki API, keeps only paragraph
prose (no tables, lists, captions, footnote marks or formulas), and caches it outside the
repository: the article text is CC BY-SA and is never committed here. It then runs
`prose_lint.py` over every article and reports each label's matches per 1,000 words, by language.

A match on a blocking label (`assistant residue` and `chatbot artifact` by default) in this
corpus is a false positive in human prose: exit 1. Every other label is a review candidate,
and its rate here is the human baseline to compare a draft's density against. A clean run says
nothing about a label's precision on other genres, and a match rate is not an authorship test.

Network use is opt-in: tests never call this module's fetch path. `--offline` reads only the
cache. `--resolve HOST TITLE` prints a manifest entry for the last revision before the cutoff.
Exit codes: 0 clean, 1 blocking match in human text, 2 error (missing cache entry, a pinned
revision saved after the cutoff, network failure).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = "2022-11-30T00:00:00Z"  # ChatGPT's public release; revisions must be saved before it
DEFAULT_FAIL_ON = ("assistant residue", "chatbot artifact")
USER_AGENT = "codxt-humanizer-human-control/1.0 (https://github.com/codxt/humanizer)"
DELAY = 2.0  # seconds between API calls; Wikipedia throttles bursts
HOSTS = {"en.wikipedia.org": "en", "ru.wikipedia.org": "ru"}

_spec = importlib.util.spec_from_file_location("prose_lint", ROOT / "scripts" / "prose_lint.py")
prose_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prose_lint)


class ProseExtractor(HTMLParser):
    """Collect the text of top-level <p> elements, skipping embedded non-prose."""

    SKIP = {"table", "style", "script", "sup", "figure", "math", "ul", "ol", "dl"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.in_paragraph = False
        self.paragraphs: list[str] = []
        self._current: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag == "p" and not self.skip_depth:
            self.in_paragraph = True
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag == "p" and self.in_paragraph:
            self.in_paragraph = False
            text = " ".join("".join(self._current).split())
            if text:
                self.paragraphs.append(text)

    def handle_data(self, data: str) -> None:
        if self.in_paragraph and not self.skip_depth:
            self._current.append(data)


FOOTNOTE_MARK = re.compile(r"\[(?:\d+|[a-z]|citation needed|нет АИ|источник не указан \d+ дней)\]")


def extract_prose(html: str) -> str:
    parser = ProseExtractor()
    parser.feed(html)
    parser.close()
    paragraphs = (FOOTNOTE_MARK.sub("", paragraph).strip() for paragraph in parser.paragraphs)
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph) + "\n"


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text))


def check_entry(entry: dict) -> None:
    for key in ("host", "title", "revid", "timestamp"):
        if key not in entry:
            raise ValueError(f"manifest entry missing {key!r}: {entry}")
    if entry["host"] not in HOSTS:
        raise ValueError(f"unsupported host {entry['host']!r}; known: {', '.join(HOSTS)}")
    if not entry["timestamp"] < CUTOFF:
        raise ValueError(f"{entry['title']} revision {entry['revid']} was saved at "
                         f"{entry['timestamp']}, not before {CUTOFF}")


def _api(host: str, **params) -> dict:
    params["format"] = "json"
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
            time.sleep(DELAY)
            return payload
        except OSError:
            if attempt == 2:
                raise
            time.sleep(10 * (attempt + 1))
    raise AssertionError("unreachable")


def fetch_revision(entry: dict) -> str:
    """Return the revision's prose, confirming on the server that it predates the cutoff."""
    meta = _api(entry["host"], action="query", prop="revisions", revids=entry["revid"],
                rvprop="ids|timestamp")
    page = next(iter(meta["query"]["pages"].values()))
    timestamp = page["revisions"][0]["timestamp"]
    if timestamp != entry["timestamp"]:
        raise ValueError(f"{entry['title']} revision {entry['revid']}: server timestamp "
                         f"{timestamp} differs from the manifest's {entry['timestamp']}")
    parsed = _api(entry["host"], action="parse", oldid=entry["revid"], prop="text")
    return extract_prose(parsed["parse"]["text"]["*"])


def resolve(host: str, title: str) -> dict:
    data = _api(host, action="query", prop="revisions", titles=title, rvlimit=1, rvstart=CUTOFF,
                rvdir="older", rvprop="ids|timestamp", redirects=1)
    page = next(iter(data["query"]["pages"].values()))
    if "revisions" not in page:
        raise ValueError(f"{title}: no revision on {host} before {CUTOFF}")
    revision = page["revisions"][0]
    return {"host": host, "title": page["title"], "revid": revision["revid"],
            "timestamp": revision["timestamp"]}


def cache_path(cache: Path, entry: dict) -> Path:
    return cache / f"{HOSTS[entry['host']]}-{entry['revid']}.md"


def measure(entries: list[dict], cache: Path, *, offline: bool, fail_on: set[str], out=sys.stdout) -> int:
    words: Counter = Counter()
    matches: dict[str, Counter] = defaultdict(Counter)
    blocking: list[str] = []
    for entry in entries:
        check_entry(entry)
        path = cache_path(cache, entry)
        if not path.is_file():
            if offline:
                raise FileNotFoundError(f"{path}: not cached; run once without --offline")
            cache.mkdir(parents=True, exist_ok=True)
            path.write_text(fetch_revision(entry), encoding="utf-8")
        language = HOSTS[entry["host"]]
        words[language] += word_count(path.read_text(encoding="utf-8"))
        for line, label, excerpt, quoted in prose_lint.lint_detailed(path):
            matches[language][label] += 1
            if label in fail_on and not quoted:
                blocking.append(f"{entry['title']} ({entry['revid']}) L{line}: {label}: {excerpt}")

    print(f"Human control: {len(entries)} revisions saved before {CUTOFF}", file=out)
    for language in sorted(words):
        print(f"\n[{language}] {words[language]} words", file=out)
        for label, count in sorted(matches[language].items(), key=lambda item: (-item[1], item[0])):
            rate = 1000 * count / words[language] if words[language] else 0.0
            print(f"  {label}: {count} ({rate:.2f} per 1,000 words)", file=out)
        if not matches[language]:
            print("  no candidates", file=out)
    for finding in blocking:
        print(f"BLOCKING in human text: {finding}", file=out)
    print(f"\nBlocking matches in human text: {len(blocking)}", file=out)
    return 1 if blocking else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="human_control.py")
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests" / "human_control.json")
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "humanizer-human-control")
    parser.add_argument("--offline", action="store_true", help="read only the cache; never fetch")
    parser.add_argument("--fail-on", action="append", metavar="LABEL",
                        help=f"blocking label; repeatable (default: {', '.join(DEFAULT_FAIL_ON)})")
    parser.add_argument("--resolve", nargs=2, metavar=("HOST", "TITLE"),
                        help="print a manifest entry for the last revision before the cutoff")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        if args.resolve:
            host, title = args.resolve
            if host not in HOSTS:
                raise ValueError(f"unsupported host {host!r}; known: {', '.join(HOSTS)}")
            print(json.dumps(resolve(host, title), ensure_ascii=False))
            return 0
        fail_on = set(args.fail_on or DEFAULT_FAIL_ON)
        unknown = sorted(fail_on - prose_lint.LABELS)
        if unknown:
            raise ValueError(f"unknown label(s): {', '.join(unknown)}")
        entries = json.loads(args.manifest.read_text(encoding="utf-8"))["revisions"]
        return measure(entries, args.cache, offline=args.offline, fail_on=fail_on)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
