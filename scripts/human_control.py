#!/usr/bin/env python3
"""Measure the prose linter against human writing from before ChatGPT.

Usage:
    python3 -S scripts/human_control.py [--cache DIR] [--offline] [--fail-on LABEL ...] [--manifest FILE]
    python3 -S scripts/human_control.py --resolve HOST TITLE

The manifest (default `tests/human_control.json`) pins Wikipedia revisions saved before
ChatGPT's public release on 30 November 2022, a proxy for human-written text: the article
source predates ChatGPT, while templates are rendered as of the fetch.
The script fetches each pinned revision once through the MediaWiki API, keeps only paragraph
prose (no tables, lists, captions, footnote marks or formulas), and caches it outside the
repository: the article text is CC BY-SA and is never committed here. A cached file's name
carries the SHA-256 of its bytes and counts only when they match, so a partial write is fetched
again; the linter reads a private copy of the verified bytes. It then runs
`prose_lint.py` over every article and reports each label's matches per 1,000 words, by language.

An unquoted match on a blocking label (`assistant residue` and `chatbot artifact` by default)
in this corpus is a false positive in human prose: exit 1. Every other label is a review candidate,
and its rate here is an observation for this sample of rendered encyclopedic paragraphs, not a
baseline for other genres. Paragraph extraction drops link destinations, lists and headings, so URL and
structural labels are barely exercised. A match rate is not an authorship test. Words are
Unicode `\\w+` runs. A pinned revision fixes the article text; templates are rendered as of the fetch.

Tests never touch the network. `--offline` reads only the cache and cannot be combined with
`--resolve`. Cache files are written atomically; an empty manifest or a cached file without words
is an error. `--resolve HOST TITLE` prints a manifest entry for the last revision before the cutoff.
Exit codes: 0 clean, 1 blocking match in human text, 2 error (missing cache entry, a pinned
revision saved after the cutoff, network failure).
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import os
import tempfile
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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
        self.quote_depth = 0
        self._paragraph_quoted = False
        self.paragraphs: list[str] = []
        self._current: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self.skip_depth += 1
        elif self.skip_depth:
            return
        elif tag == "blockquote":
            self.quote_depth += 1
        elif tag == "q" and self.in_paragraph:
            self._current.append("“")  # keep an inline quotation visible to the linter
        elif tag == "p":
            self.in_paragraph = True
            self._paragraph_quoted = bool(self.quote_depth)
            self._current = []
        elif tag == "br" and self.in_paragraph:
            self._current.append(" ")

    def handle_startendtag(self, tag: str, attrs) -> None:
        if tag == "br" and self.in_paragraph and not self.skip_depth:
            self._current.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            if self.skip_depth:
                self.skip_depth -= 1
        elif tag == "q" and self.in_paragraph and not self.skip_depth:
            self._current.append("”")
        elif tag == "blockquote" and not self.skip_depth:
            self.quote_depth = max(0, self.quote_depth - 1)
        elif tag == "p" and self.in_paragraph and not self.skip_depth:
            self.in_paragraph = False
            text = " ".join("".join(self._current).split())
            if text:  # a blockquote stays a Markdown blockquote, so the linter's exemption applies
                self.paragraphs.append(("> " if self._paragraph_quoted else "") + text)

    def handle_data(self, data: str) -> None:
        if self.in_paragraph and not self.skip_depth:
            self._current.append(data)


FOOTNOTE_MARK = re.compile(r"\[(?:\d+|[a-z]|citation needed|нет АИ|источник не указан \d+ дней)\]")
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
LAST_BEFORE_CUTOFF = "2022-11-29T23:59:59Z"  # rvstart is inclusive, so start one second earlier
RETRY_CODES = {"ratelimited", "maxlag", "readonly"}
MAX_RETRY_WAIT = 120


def extract_prose(html: str) -> str:
    parser = ProseExtractor()
    parser.feed(html)
    parser.close()
    paragraphs = (FOOTNOTE_MARK.sub("", paragraph).strip() for paragraph in parser.paragraphs)
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph) + "\n"


def word_count(text: str) -> int:
    """Count Unicode `\\w+` runs: `don't 3.14 state-of-the-art` is eight words."""
    return len(re.findall(r"\w+", text))


def check_entry(entry: dict) -> None:
    if not isinstance(entry, dict):
        raise ValueError(f"manifest entry is not an object: {entry!r}")
    for key in ("host", "title", "revid", "timestamp"):
        if key not in entry:
            raise ValueError(f"manifest entry missing {key!r}: {entry}")
    if entry["host"] not in HOSTS:
        raise ValueError(f"unsupported host {entry['host']!r}; known: {', '.join(HOSTS)}")
    revid = entry["revid"]
    if isinstance(revid, bool) or not isinstance(revid, int) or revid <= 0:
        raise ValueError(f"{entry['title']}: revid must be a positive integer, not {revid!r}")
    stamp = entry["timestamp"]
    try:
        if not isinstance(stamp, str) or not TIMESTAMP.fullmatch(stamp):
            raise ValueError
        datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")  # rejects impossible dates such as 02-31
    except ValueError:
        raise ValueError(f"{entry['title']}: timestamp {stamp!r} is not a valid YYYY-MM-DDTHH:MM:SSZ") from None
    if not stamp < CUTOFF:
        raise ValueError(f"{entry['title']} revision {revid} was saved at {stamp}, not before {CUTOFF}")


def _retry_after(value: str | None, attempt: int, *, now: datetime | None = None) -> float:
    """Seconds to wait before a retry. Retry-After may be delta-seconds or an HTTP date
    (RFC 9110 10.2.3); a delay beyond MAX_RETRY_WAIT stops the run instead of retrying early."""
    if not value:
        return 10.0 * (attempt + 1)
    value = value.strip()
    if value.isdigit():
        delay = float(value)
    else:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return 10.0 * (attempt + 1)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        delay = max(0.0, (when - (now or datetime.now(timezone.utc))).total_seconds())
    if delay > MAX_RETRY_WAIT:
        raise ValueError(f"server asks to wait {delay:.0f} s, more than {MAX_RETRY_WAIT} s; try later")
    return delay


def _api(host: str, **params) -> dict:
    """One MediaWiki API call. Throttling is retried; any other API error raises ValueError."""
    params.update(format="json", formatversion=1, maxlag=5)
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        last = attempt == 3
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
                retry_after = response.headers.get("Retry-After")
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503) or last:
                raise
            time.sleep(_retry_after(exc.headers.get("Retry-After"), attempt))
            continue
        except (OSError, http.client.HTTPException, ValueError) as exc:  # JSON and UTF-8 decode errors
            # a dropped connection or truncated body is a network failure (exit 2), not a lint result
            if last:
                raise OSError(f"{host}: {type(exc).__name__}: {exc}") from exc
            time.sleep(_retry_after(None, attempt))
            continue
        if not isinstance(payload, dict):
            raise ValueError(f"{host}: malformed API response")
        error = payload.get("error")
        if error:
            code = error.get("code", "unknown") if isinstance(error, dict) else "unknown"
            if code in RETRY_CODES and not last:
                time.sleep(_retry_after(retry_after, attempt))
                continue
            raise ValueError(f"{host}: API error {code}: {error.get('info', '') if isinstance(error, dict) else error}")
        time.sleep(DELAY)
        return payload
    raise ValueError(f"{host}: API still throttled after retries")


def _only_page(payload: dict) -> dict:
    try:
        pages = list(payload["query"]["pages"].values())
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("malformed API response: no query.pages") from exc
    if len(pages) != 1 or not isinstance(pages[0], dict):
        raise ValueError(f"malformed API response: expected one page, got {len(pages)}")
    return pages[0]


def _only_revision(page: dict) -> dict:
    revisions = page.get("revisions")
    if not isinstance(revisions, list) or len(revisions) != 1 or not isinstance(revisions[0], dict):
        raise ValueError(f"malformed API response for {page.get('title')!r}: expected one revision")
    return revisions[0]


def fetch_revision(entry: dict) -> str:
    """Return the revision's prose, confirming on the server that it is the pinned revision."""
    revision = _only_revision(_only_page(_api(entry["host"], action="query", prop="revisions",
                                              revids=entry["revid"], rvprop="ids|timestamp")))
    if (revision.get("revid"), revision.get("timestamp")) != (entry["revid"], entry["timestamp"]):
        raise ValueError(f"{entry['title']}: server returned revision {revision.get('revid')} at "
                         f"{revision.get('timestamp')}, not {entry['revid']} at {entry['timestamp']}")
    parsed = _api(entry["host"], action="parse", oldid=entry["revid"], prop="text")
    try:
        parse = parsed["parse"]
        returned, html = parse["revid"], parse["text"]["*"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"{entry['title']}: malformed parse response") from exc
    if returned != entry["revid"]:
        raise ValueError(f"{entry['title']}: parse returned revision {returned}, not {entry['revid']}")
    prose = extract_prose(html)
    if not word_count(prose):
        raise ValueError(f"{entry['title']} revision {entry['revid']}: no paragraph prose")
    return prose


def resolve(host: str, title: str) -> dict:
    page = _only_page(_api(host, action="query", prop="revisions", titles=title, rvlimit=1,
                           rvstart=LAST_BEFORE_CUTOFF, rvdir="older", rvprop="ids|timestamp",
                           redirects=1))
    if "revisions" not in page:
        raise ValueError(f"{title}: no revision on {host} before {CUTOFF}")
    revision = _only_revision(page)
    entry = {"host": host, "title": page.get("title", title), "revid": revision.get("revid"),
             "timestamp": revision.get("timestamp")}
    check_entry(entry)
    return entry


# Bump with any change to extraction: a render from an older extractor must not be reused.
CACHE_FORMAT = "v4"  # v4: blockquotes and <q> keep their quotation marks


def cache_dir(cache: Path) -> Path:
    return cache / CACHE_FORMAT


def _stem(entry: dict) -> str:
    return f"{HOSTS[entry['host']]}-{entry['revid']}"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    """Write through a temporary file unique to this writer, then rename it into place."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def store(cache: Path, entry: dict, text: str) -> Path:
    """Publish the text under a name that carries its own SHA-256, in one atomic rename, so
    text and checksum can never come from different writers."""
    data = text.encode("utf-8")
    path = cache_dir(cache) / f"{_stem(entry)}.{_digest(data)}.md"
    _write_atomic(path, data)
    return path


def load(cache: Path, entry: dict) -> str | None:
    """The one cached render whose bytes match the checksum in its name, or None. Two valid
    renders of one revision are ambiguous: the result could depend on which is read."""
    valid: list[str] = []
    for path in sorted(cache_dir(cache).glob(f"{_stem(entry)}.*.md")):
        name_digest = path.name[len(_stem(entry)) + 1:-len(".md")]
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            continue
        if name_digest == _digest(data):
            try:
                valid.append(data.decode("utf-8"))
            except UnicodeError:
                continue
    if len(valid) > 1:
        raise ValueError(f"{cache_dir(cache) / _stem(entry)}: {len(valid)} different cached renders; "
                         "delete them and fetch again")
    return valid[0] if valid else None


def _lint_text(text: str) -> list[tuple[int, str, str, bool]]:
    """Lint exactly these verified bytes from a private copy, not the shared cache file."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "revision.md"
        path.write_text(text, encoding="utf-8")
        return prose_lint.lint_detailed(path)


def measure(entries: list[dict], cache: Path, *, offline: bool, fail_on: set[str], out=sys.stdout) -> int:
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest lists no revisions")
    words: Counter = Counter()
    matches: dict[str, Counter] = defaultdict(Counter)
    blocking: list[str] = []
    for entry in entries:
        check_entry(entry)
        text = load(cache, entry)
        if text is None:
            if offline:
                raise FileNotFoundError(f"{cache_dir(cache) / _stem(entry)}: not cached or incomplete; "
                                        "run once without --offline")
            store(cache, entry, fetch_revision(entry))
            text = load(cache, entry)  # measure the one authoritative render, as offline runs will
            if text is None:
                raise ValueError(f"{entry['title']} ({entry['revid']}): cache write did not verify")
        count = word_count(text)
        if not count:
            raise ValueError(f"{entry['title']} ({entry['revid']}): cached text has no words")
        language = HOSTS[entry["host"]]
        words[language] += count
        for line, label, excerpt, quoted in _lint_text(text):
            matches[language][label] += 1
            if label in fail_on and not quoted:
                blocking.append(f"{entry['title']} ({entry['revid']}) L{line}: {label}: {excerpt}")

    print(f"Human control: {len(entries)} revisions saved before {CUTOFF}", file=out)
    for language in sorted(words):
        print(f"\n[{language}] {words[language]} words", file=out)
        for label, count in sorted(matches[language].items(), key=lambda item: (-item[1], item[0])):
            print(f"  {label}: {count} ({1000 * count / words[language]:.2f} per 1,000 words)", file=out)
        if not matches[language]:
            print("  no candidates", file=out)
    for finding in blocking:
        print(f"BLOCKING in human text: {finding}", file=out)
    print(f"\nUnquoted blocking matches in human text: {len(blocking)}", file=out)
    return 1 if blocking else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="human_control.py")
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests" / "human_control.json")
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "humanizer-human-control")
    parser.add_argument("--fail-on", action="append", metavar="LABEL",
                        help=f"blocking label; repeatable (default: {', '.join(DEFAULT_FAIL_ON)})")
    network = parser.add_mutually_exclusive_group()
    network.add_argument("--offline", action="store_true", help="read only the cache; never fetch")
    network.add_argument("--resolve", nargs=2, metavar=("HOST", "TITLE"),
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
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("cutoff") != CUTOFF:
            raise ValueError(f"{args.manifest}: cutoff must be {CUTOFF}")
        return measure(manifest.get("revisions"), args.cache, offline=args.offline, fail_on=fail_on)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
