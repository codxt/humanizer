#!/usr/bin/env python3
"""Prose lint for common AI-pattern candidates.

Usage:
    python3 -S scripts/prose_lint.py [--fail-on LABEL ...] [--github-annotations] <file> [<file> ...]

The script never rewrites text. Matches are review candidates, not proof of AI
origination and not automatic replacement instructions. By default every match
is report-only. `--fail-on LABEL` turns matches of that label into blocking
findings (exit 1) for CI gates; choose only high-precision labels such as
`assistant residue` and `chatbot artifact`. Matches inside a closed quotation (straight, «», “”, „“;
it may span lines within a paragraph) or a blockquote paragraph are marked
[quoted] and never block, so preserved quotations stay intact. An unclosed
quotation exempts nothing. `6"` never opens a quotation (it is an inch mark), but
a straight quote after a digit can close one, so "version 2" stays a quotation and
an inch mark inside an open quotation ends it. Emphasis delimiters (`*`, `_`) right next to a
straight quote are looked past, so `**"text"**` is a quotation (emphasis followed by a word,
as in `"text"**Bold** end`, is not a boundary). Inline code inside a quotation does not hide its
edge (`"`save` text"`), and code outside it is a boundary (`` `x`"text" ``, `"text"`x` ``).
A line without `>` continues a blockquote only while the quote's own content ends in an open
paragraph: after a quoted heading, thematic break (`---`, `***`, `___`), setext underline, code
fence, indented code or empty `>` line it is outside the quote. Once a line of the blockquote
starts a list item, an HTML block or a link reference definition, no unmarked line after it is
quoted (CommonMark would sometimes still quote it; the gate prefers to block there). An unmarked
line that starts an HTML block ends the quote, and `>` lines inside an HTML block quote nothing.
"""

from __future__ import annotations

import argparse
import re
import sys
from bisect import bisect_left, bisect_right
from collections import Counter
from itertools import accumulate
from pathlib import Path


PATTERNS = [
    ("assistant residue", re.compile(r"(?<!\w)(?:i hope this (?:helps|was helpful)|hope this helps|great question|as an ai (?:language model|assistant)|надеюсь, это (?:поможет|было полезно)|отличный вопрос|как языковая модель)(?!\w)", re.I)),
    ("chatbot residue", re.compile(r"\b(?:let(?:'|’)s dive in|here(?:'|’)s the thing|after careful consideration|i wanted to provide a quick update)\b", re.I)),
    ("russian chatbot residue", re.compile(r"(?<!\w)(?:давайте разбер[её]мся|с радостью помогу)(?!\w)", re.I)),
    ("chatbot residue", re.compile(r"(?<!\w)(?:would you like me to|let me know if you(?:(?:'|’)d| would)? like|is there anything else (?:i can|you(?:(?:'|’)d| would) like)|delete this (?:section|note) before (?:submission|submitting|publishing|publication)|here(?:(?:'|’)s| is) (?:a|the|your) (?:revised|updated|polished|rewritten|improved) (?:version|draft|text)|it(?:(?:'|’)s| is) important to (?:note|remember)|certainly!|you(?:(?:'|’)re| are) absolutely right)(?!\w)", re.I)),
    ("russian chatbot residue", re.compile(r"(?<!\w)(?:хотите, я (?:подготовлю|сделаю|напишу|составлю)|вот (?:исправленный|обновл[её]нный|переработанный|улучшенный) (?:вариант|текст))(?!\w)", re.I)),
    ("chatbot artifact", re.compile(r"(?:contentReference\[oaicite:\d+\](?:\{index=\d+\})?|\boaicite:\d+|\boai_citation\b|turn\d+(?:search|news|view|fetch|image|file)\d+\b|\[cite(?::\s*\d+(?:\s*,\s*\d+)*|_start|_end)\]|\bgrok_(?:card|render_citation_card_json)\b|【\d+(?::\d+)?†[^】\n]{0,80}】)")),
    ("placeholder text", re.compile(r"(?:\bINSERT_[A-Z0-9_]{3,}\b|(?i:\[(?:insert|add|вставьте|укажите|добавьте)\b[^\]\n]{1,60}\](?![(:\[])|\[(?:year|date|founder names?|company name|your name|full name|дата(?: рождения)?|год|название компании|имя и фамилия|фио)\](?![(:\[])|\b(?:19|20)\d\d-xx-xx\b|\bxx\.xx\.(?:19|20)\d\d\b))")),
    ("abstract metaphor noun", re.compile(r"\b(?:substrate|locus|nexus|bedrock|north star|flywheel)s?\b", re.I)),
    ("significance claim", re.compile(r"\b(?:marks? a (?:major |key |pivotal )?(?:shift|turning point|milestone)|statement of intent|new era|broader trend|testament to|underscores? (?:the )?(?:importance|significance))\b", re.I)),
    ("formulaic contrast", re.compile(r"\b(?:not (?:just|only|simply)\b|not\s+[^.!?;:]{1,80}\s+but\s+[^.!?;:]{1,80}|less about\s+[^.!?;:]{1,80}\s+more about)\b", re.I)),
    ("russian formulaic contrast", re.compile(r"\b(?:не просто|не только|не столько|дело не в)\b", re.I)),
    ("russian metacommentary", re.compile(r"\b(?:важно отметить|следует отметить|стоит подчеркнуть|необходимо понимать|нельзя не отметить|отдельного внимания заслуживает)\b", re.I)),
    ("russian bureaucratic padding", re.compile(r"\b(?:в рамках данного|на сегодняшний день|на текущий момент|осуществляется работа по|в целях обеспечения)\b", re.I)),
    ("generic authority", re.compile(r"\b(?:experts? (?:say|argue|believe|note)|research shows|observers? note|эксперты (?:отмечают|считают)|исследования показывают|аналитики полагают|как показывает практика)\b", re.I)),
    ("generic conclusion", re.compile(r"\b(?:in conclusion|to sum up|the future looks bright|подводя итог|в заключение стоит отметить|таким образом, можно сделать вывод)\b", re.I)),
    ("restating closer", re.compile(r"\b(?:that(?:'|’)s the real win|that distinction matters|let that sink in|read that again|в этом и заключается главное|именно в этом суть|это и есть главный вывод)\b", re.I)),
    ("staged candor", re.compile(r"\b(?:let(?:'|’)s be honest|real talk|давайте начистоту|будем откровенны)\b", re.I)),
    ("possible imagined objection", re.compile(r"\b(?:i(?:'|’)m not saying|don(?:'|’)t get me wrong|one might be tempted to|это не означает, что|поймите меня правильно)\b", re.I)),
    ("possible document narration", re.compile(r"\b(?:the table below compares|this section is organi[sz]ed|в таблице ниже сравниваются|этот раздел организован)\b", re.I)),
    ("corrective disclaimer", re.compile(r"\b(?:should (?:be )?(?:treated|read|understood|viewed|presented|regarded) as\b[^.!?\n]{1,80}\brather than|(?:does|do) not (?:by itself|in itself|itself|themselves|alone|on (?:its|their) own) establish|based on (?:the )?available (?:information|sources|data|evidence)|not (?:widely|publicly) (?:available|documented|disclosed|reported)|specific details (?:are|remain) (?:limited|scarce)|следует (?:рассматривать|воспринимать|трактовать|понимать) как\b[^.!?\n]{1,80}?, а не|сам(?:о|а|и)? по себе не (?:доказывает|подтверждает|означает|устанавливает)|на основе доступн(?:ой|ых) (?:информации|данных|источников))\b", re.I)),
    ("procedural assurance", re.compile(r"\b(?:(?:to|and) ensure (?:the )?(?:clarity|consistency|accuracy|neutrality|compliance|readability|coherence|quality)|while (?:preserving|retaining|maintaining|keeping) (?:the )?(?:original|core|existing|overall|key) (?:meaning|intent|structure|content|tone|voice|message)|(?:improv|enhanc)(?:e|es|ed|ing) (?:the )?(?:overall )?(?:clarity|flow|readability|coherence|tone)|in (?:compliance|line|accordance) with (?:the )?(?:guidelines|standards|style guide|policies)|adheres? to (?:the )?(?:guidelines|standards|style guide|policies)|для обеспечения (?:ясности|согласованности|точности|нейтральности|единообразия)|с сохранением (?:исходного|основного|первоначального) (?:смысла|содержания|замысла)|улучшен[аоы]? (?:читаемость|ясность|структура|связность))\b", re.I)),
]

# Scanned with links visible (code still masked): these signs live inside URLs.
URL_PATTERNS = [
    ("chatbot artifact", re.compile(r"[?&](?:utm_source=(?:chatgpt\.com|openai|copilot\.com)|referrer=grok\.com)(?![\w-]|\.\w)", re.I)),
    ("placeholder text", re.compile(r"\bexample\.(?:com|org)/(?:source|article|news|link)\d*\b", re.I)),
]

BOLD_LABEL = re.compile(r"^\s*[-*+]\s+\*\*[^*]{2,80}:\*\*\s+")
TITLE_CASE_HEADING = re.compile(r"^#{1,6}\s+(?:[A-Z][\w'-]+\s+){2,}[A-Z][\w'-]+\s*$")
STACKED_SHORT = re.compile(r"(?m)(?:^[^\n.!?]{1,45}[.!?]\s*$\n?){3,}")
MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`)[^\r\n]*?(?<!`)\1(?!`)")  # reference definition; see _inline_code_spans
BACKTICK_RUN = re.compile(r"`+")
LINE = re.compile(r"[^\r\n]+(?:\r\n|\r|\n)?|\r\n|\r|\n")
URL = re.compile(r"https?://[^\s<>\"«»“”„]+")  # quote marks end a link, so quoted links stay quoted


def _mask(value: str) -> str:
    return "".join(char if char in "\r\n" else " " for char in value)


def _mask_ranges(text: str, ranges: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in ranges:
        chars[start:end] = _mask(text[start:end])
    return "".join(chars)


def _fence_ranges(text: str) -> list[tuple[int, int]]:
    """Offsets of fenced code blocks, fence lines included."""
    ranges: list[tuple[int, int]] = []
    fence_char = ""
    fence_length = 0
    block_start = 0
    offset = 0
    for line in LINE.findall(text):  # only CR and LF end a line, as in CommonMark
        if fence_char:
            closing = re.fullmatch(r" {0,3}(" + re.escape(fence_char) + r"{"
                                   + str(fence_length) + r",})[ \t]*(?:\r\n|\r|\n)?", line)
            if closing:
                fence_char = ""
                ranges.append((block_start, offset + len(line)))
        else:
            opening = re.match(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)", line)
            if opening and (opening.group(1)[0] != "`" or "`" not in opening.group(2)):
                fence_char = opening.group(1)[0]
                fence_length = len(opening.group(1))
                block_start = offset
        offset += len(line)
    if fence_char:
        ranges.append((block_start, len(text)))
    return ranges


def code_ranges(text: str) -> list[tuple[int, int]]:
    """Offsets of fenced code blocks (fence lines included) and inline code spans."""
    ranges = _fence_ranges(text)
    ranges.extend(_inline_code_spans(_mask_ranges(text, ranges)))
    return sorted(ranges)


def _inline_code_spans(text: str) -> list[tuple[int, int]]:
    """Same spans as `INLINE_CODE.finditer`, in linear time: an opening backtick run pairs with
    the next run of the same length on the same line; an unpaired run opens nothing."""
    spans: list[tuple[int, int]] = []
    offset = 0
    for line in LINE.findall(text):  # only \r and \n end a line, as in INLINE_CODE
        runs = [match.span() for match in BACKTICK_RUN.finditer(line)]
        following: list[int] = [-1] * len(runs)
        last_seen: dict[int, int] = {}
        for index in range(len(runs) - 1, -1, -1):
            length = runs[index][1] - runs[index][0]
            following[index] = last_seen.get(length, -1)
            last_seen[length] = index
        index = 0
        while index < len(runs):
            closer = following[index]
            if closer < 0:
                index += 1
                continue
            spans.append((offset + runs[index][0], offset + runs[closer][1]))
            index = closer + 1
        offset += len(line)
    return spans


def mask_code(text: str, mask_urls: bool = True) -> str:
    """Mask Markdown code (and links, by default) while preserving offsets and line numbers."""
    scan = _mask_ranges(text, code_ranges(text))
    if mask_urls:
        scan = URL.sub(lambda match: _mask(match.group(0)), scan)
    return scan


CODE_MARK = "\x00"  # stands in for an inline code span where quotation boundaries are judged


def quote_scan(text: str) -> str:
    """Text for finding quotations, offsets and line numbers preserved: top-level fenced code is
    blanked (it still separates paragraphs; a fence inside a blockquote stays visible, as part of
    the quote) and each inline code span becomes `CODE_MARK` characters, so a quote next to code
    sees a non-space neighbour instead of the blanked span. Links stay visible. A literal NUL in
    the text becomes U+0001 so it cannot pass for code."""
    fences = _fence_ranges(text)
    scan = _mask_ranges(text, fences).replace(CODE_MARK, "\x01")  # a literal NUL must not pose as code
    chars = list(scan)
    for start, end in _inline_code_spans(scan):
        chars[start:end] = [char if char in "\r\n" else CODE_MARK for char in scan[start:end]]
    return "".join(chars)


def strip_code_fences(text: str) -> str:
    """Mask Markdown code and links while preserving source offsets and line numbers."""
    return mask_code(text)


def uniform_heading_geometry(scan: str) -> list[tuple[int, str, str]]:
    """Flag strong repeated parent->child heading counts in long Markdown.

    This is deliberately conservative and report-only. It detects a dominant
    direct-child count only when at least six peer parent headings exist and at
    least 80% share the same count of two or more children. Regular structure
    can be intentional, so every hit requires human/source review.
    """
    headings: list[tuple[int, int, str]] = []
    for number, line_text in enumerate(scan.splitlines(), 1):
        match = MARKDOWN_HEADING.match(line_text)
        if match:
            headings.append((number, len(match.group(1)), match.group(2).strip()))

    findings: list[tuple[int, str, str]] = []
    for parent_level in range(1, 6):
        parents = [item for item in headings if item[1] == parent_level]
        if len(parents) < 6:
            continue

        child_counts: list[tuple[int, str, int]] = []
        for line_no, _, title in parents:
            count = 0
            started = False
            for child_line, child_level, _ in headings:
                if child_line <= line_no:
                    continue
                if child_level <= parent_level:
                    if started:
                        break
                    break
                started = True
                if child_level == parent_level + 1:
                    count += 1
            if count:
                child_counts.append((line_no, title, count))

        if len(child_counts) < 6:
            continue

        counts = Counter(count for _, _, count in child_counts)
        dominant_count, dominant_n = counts.most_common(1)[0]
        if dominant_count < 2:
            continue
        share = dominant_n / len(child_counts)
        if share < 0.80:
            continue

        first_line = child_counts[0][0]
        excerpt = (
            f"H{parent_level} parents={len(child_counts)}, "
            f"dominant direct H{parent_level + 1} children={dominant_count} "
            f"for {dominant_n}/{len(child_counts)} parents ({share:.0%})"
        )
        findings.append((first_line, "uniform heading geometry", excerpt))

    return findings


def _paragraphs(scan: str):
    """Yield (offset, text) for each maximal run of lines (ended by `\\n`) that contain a
    non-whitespace character; one linear pass."""
    offset = 0
    start = -1
    lines = scan.split("\n")
    for index, line in enumerate(lines):
        length = len(line) + (1 if index < len(lines) - 1 else 0)
        if line.strip():
            if start < 0:
                start = offset
        elif start >= 0:
            yield start, scan[start:offset]
            start = -1
        offset += length
    if start >= 0:
        yield start, scan[start:offset]


QUOTE_MARKER = re.compile(r" {0,3}> ?")
THEMATIC_BREAK = re.compile(r" {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})")
BLOCK_START = re.compile(r" {0,3}(?:#|[-*+] |\d+[.)] |`{3,}|~{3,}|>)")
LIST_MARKER = re.compile(r" {0,3}(?:[-*+]|\d{1,9}[.)])(?:[ \t]+|$)")
HTML_BLOCK_START = re.compile(r" {0,3}<[A-Za-z/!?]")
LINK_DEFINITION = re.compile(r" {0,3}\[[^\]\r\n]+\]:")
ATX_HEADING = re.compile(r" {0,3}#{1,6}(?:[ \t]|$)")
SETEXT_UNDERLINE = re.compile(r" {0,3}(?:=+|-+)[ \t]*")
FENCE_OPEN = re.compile(r" {0,3}(`{3,}|~{3,})([^\r\n]*)")
CURLY_CLOSERS = {"«": "»", "“": "”", "„": "“”"}
STRAIGHT_OPEN_AFTER = set("([{«“„—–-/:" + CODE_MARK)  # inline code next to a quote is a boundary
STRAIGHT_CLOSE_BEFORE = set(".,;:!?)]}»”…—–-'" + CODE_MARK)
EMPHASIS = "*_"


def _quote_content_state(content: str, open_paragraph: bool,
                         fence: tuple[str, int] | None) -> tuple[bool, tuple[str, int] | None]:
    """After one line of blockquote content (the `>` markers already removed): whether a paragraph
    is open, so that an unmarked line continues it lazily, and whether a fenced code block is open.
    An empty line, a heading, a thematic break, a setext underline, a fence line and the lines of
    a fenced or indented code block leave no open paragraph; any other line opens or continues one."""
    body = content.rstrip("\r\n")
    if fence:
        closing = re.fullmatch(r" {0,3}(" + re.escape(fence[0]) + "{" + str(fence[1]) + r",})[ \t]*", body)
        return False, (None if closing else fence)
    if not body.strip():
        return False, None
    indent = len(body) - len(body.lstrip(" \t"))
    if indent >= 4 or body[:1] == "\t":
        return open_paragraph, None  # indented code, or a continuation line of the open paragraph
    opening = FENCE_OPEN.fullmatch(body)
    if opening and (opening.group(1)[0] != "`" or "`" not in opening.group(2)):
        return False, (opening.group(1)[0], len(opening.group(1)))
    if ATX_HEADING.match(body) or THEMATIC_BREAK.fullmatch(body):
        return False, None
    if open_paragraph and SETEXT_UNDERLINE.fullmatch(body):
        return False, None  # the underline closes a heading
    return True, None


def _starts_container(content: str) -> bool:
    """Does this line of blockquote content start a list item, an HTML block or a link reference
    definition? A whole-line thematic break (`* * *`, `- - -`) is not a list item."""
    body = content.rstrip("\r\n")
    if THEMATIC_BREAK.fullmatch(body):
        return False
    return bool(LIST_MARKER.match(body) or HTML_BLOCK_START.match(body) or LINK_DEFINITION.match(body))


def _blockquote_ranges(scan: str) -> list[tuple[int, int]]:
    """Each blockquote paragraph as one range: a `>` line and the lines that continue it, up to a
    blank line or a new block, so a match that spans two of its lines is still quoted.

    An unmarked line continues the quote lazily only while the quote's own content ends in an open
    paragraph: not after a heading, thematic break, setext underline, code fence, indented code
    or empty `>` line. Once any line of the blockquote starts a list item, an HTML block or a link
    reference definition (outside a fenced block), no unmarked line is lazily quoted for the rest
    of that blockquote: the nested structure is not modelled, and the gate prefers to block. An
    unmarked line that starts an HTML block ends the quote, and until the next blank line `>`
    lines are HTML text, not quotes (HTML blocks that end earlier are treated the same way)."""
    ranges: list[tuple[int, int]] = []
    offset = 0
    inside = False
    open_paragraph = False
    container = False
    html_block = False
    fence: tuple[str, int] | None = None
    for line in LINE.findall(scan):
        if not line.strip():
            inside = html_block = False
        elif QUOTE_MARKER.match(line) and not html_block:
            if not inside:
                open_paragraph, fence, container = False, None, False
            inside = True
            position = 0
            while True:
                marker = QUOTE_MARKER.match(line, position)
                if not marker:
                    break
                position = marker.end()
            container = container or (not fence and _starts_container(line[position:]))
            open_paragraph, fence = _quote_content_state(line[position:], open_paragraph, fence)
        elif inside and open_paragraph and not container and not (
                BLOCK_START.match(line) or HTML_BLOCK_START.match(line)
                or THEMATIC_BREAK.fullmatch(line.rstrip("\r\n"))):
            pass  # lazy continuation of the open paragraph
        else:
            inside = False
            html_block = html_block or bool(HTML_BLOCK_START.match(line))  # runs to the next blank line
        if inside:
            if ranges and ranges[-1][1] == offset:
                ranges[-1] = (ranges[-1][0], offset + len(line))
            else:
                ranges.append((offset, offset + len(line)))
        offset += len(line)
    return ranges


def _skip_emphasis(text: str, i: int, step: int) -> str:
    """The character at `i`, looking past a run of `*` and `_` (Markdown emphasis delimiters)."""
    while 0 <= i < len(text) and text[i] in EMPHASIS:
        i += step
    return text[i] if 0 <= i < len(text) else ""


def _straight_opener(text: str, i: int) -> bool:
    before = _skip_emphasis(text, i - 1, -1)
    after = _skip_emphasis(text, i + 1, 1)
    if (i and text[i - 1] == "\\") or not after or after.isspace():
        return False
    return before == "" or before.isspace() or before in STRAIGHT_OPEN_AFTER


def _straight_closer(text: str, i: int) -> bool:
    before = _skip_emphasis(text, i - 1, -1)
    after = _skip_emphasis(text, i + 1, 1)
    if (i and text[i - 1] == "\\") or not before or before.isspace():
        return False
    return after == "" or after.isspace() or after in STRAIGHT_CLOSE_BEFORE


def _quotation_ranges(paragraph: str, base: int) -> list[tuple[int, int]]:
    """Closed quotations inside one paragraph; an unclosed quotation exempts nothing.

    A straight quote opens a quotation when the next character is not a space and the previous
    one is the start of the text, a space, or one of `( [ { « “ „ — – - / :`. It closes one when
    the previous character is not a space and the next one is the end of the text, a space, or
    one of `. , ; : ! ? ) ] } » ” … — – - '`; an opening bracket after it closes nothing, so
    `"Version 2"[3]` is not a quotation. Runs of `*` and `_` next to the quote are looked past
    (`**"text"**`), and an inline code span counts as a non-space character (the caller passes
    `quote_scan`): inside a quotation it does not hide the edge, outside it is a boundary like
    a space. A backslash-escaped quote does neither. After a digit
    a quote never opens a quotation (`6"` is an inch mark) but can close one, so "version 2" is
    a quotation and an inch mark inside an open quotation ends it.
    """
    ranges: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []
    for i, char in enumerate(paragraph):
        if stack and char in stack[-1][0]:
            if char != '"' or _straight_closer(paragraph, i):
                _, start = stack.pop()
                ranges.append((base + start, base + i + 1))
                continue
        if char in CURLY_CLOSERS:
            stack.append((CURLY_CLOSERS[char], i))
        elif char == '"' and _straight_opener(paragraph, i):
            stack.append(('"', i))
    return ranges


def quoted_ranges(scan: str) -> list[tuple[int, int]]:
    """Offsets of blockquote paragraphs and closed quotations (may span lines)."""
    ranges = _blockquote_ranges(scan)
    for start, paragraph in _paragraphs(scan):
        ranges.extend(_quotation_ranges(paragraph, start))
    return ranges


def _range_lookup(ranges: list[tuple[int, int]]):
    """A function `(start, end) -> bool`: does some range contain [start, end]? Ranges may nest or
    overlap; the lookup is a bisect over their starts and the furthest end reached so far."""
    ordered = sorted(ranges)
    starts = [start for start, _ in ordered]
    reach = list(accumulate((end for _, end in ordered), max))

    def contains(start: int, end: int) -> bool:
        at = bisect_right(starts, start)
        return at > 0 and end <= reach[at - 1]

    return contains


def lint_detailed(path: Path) -> list[tuple[int, str, str, bool]]:
    """Findings as (line, label, excerpt, quoted); quoted matches sit in a quotation."""
    text = path.read_text(encoding="utf-8")
    scan = strip_code_fences(text)
    url_scan = mask_code(text, mask_urls=False)
    ranges = quoted_ranges(quote_scan(text))  # links stay visible so a quote that closes after a link is found
    in_quote = _range_lookup(ranges)
    newlines = [match.start() for match in re.finditer("\n", text)]  # `scan` and `url_scan` keep every "\n"
    detailed: list[tuple[int, str, str, bool]] = []
    for source, patterns in ((scan, PATTERNS), (url_scan, URL_PATTERNS)):
        for label, pattern in patterns:
            for match in pattern.finditer(source):
                line = bisect_left(newlines, match.start()) + 1
                excerpt = " ".join(match.group(0).split())
                quoted = in_quote(match.start(), match.end())
                detailed.append((line, label, excerpt, quoted))
    detailed.extend((line, label, excerpt, False) for line, label, excerpt in _structural(scan, newlines))
    detailed.sort(key=lambda item: (item[0], item[1], item[2]))
    return detailed


def lint(path: Path) -> list[tuple[int, str, str]]:
    return [(line, label, excerpt) for line, label, excerpt, _ in lint_detailed(path)]


def _structural(scan: str, newlines: list[int]) -> list[tuple[int, str, str]]:
    findings: list[tuple[int, str, str]] = []

    for number, line_text in enumerate(scan.splitlines(), 1):
        if BOLD_LABEL.search(line_text):
            findings.append((number, "bold-label bullet", line_text.strip()))
        if TITLE_CASE_HEADING.search(line_text):
            findings.append((number, "title-case heading", line_text.strip()))

    for match in STACKED_SHORT.finditer(scan):
        line = bisect_left(newlines, match.start()) + 1
        excerpt = " / ".join(part.strip() for part in match.group(0).splitlines() if part.strip())
        findings.append((line, "stacked short-sentence rhythm", excerpt[:220]))

    findings.extend(uniform_heading_geometry(scan))
    return findings


LABELS = frozenset(label for label, _ in PATTERNS + URL_PATTERNS) | {
    "bold-label bullet",
    "title-case heading",
    "stacked short-sentence rhythm",
    "uniform heading geometry",
}


def _annotation_value(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _annotation_property(value: str) -> str:
    return _annotation_value(value).replace(":", "%3A").replace(",", "%2C")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog=Path(argv[0]).name if argv else "prose_lint.py")
    parser.add_argument("files", nargs="+", metavar="file")
    parser.add_argument("--fail-on", action="append", default=[], metavar="LABEL",
                        help="treat matches of this label as blocking; repeatable")
    parser.add_argument("--github-annotations", action="store_true",
                        help="also print GitHub Actions ::error/::warning annotations")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as exc:
        return 2 if exc.code else 0
    unknown = sorted(set(args.fail_on) - LABELS)
    if unknown:
        print(f"unknown --fail-on label(s): {', '.join(unknown)}; known: {', '.join(sorted(LABELS))}",
              file=sys.stderr)
        return 2
    blocking_labels = set(args.fail_on)

    total = 0
    blocking = 0
    had_error = False
    for raw in args.files:
        path = Path(raw)
        if not path.is_file():
            print(f"{path}: not a file", file=sys.stderr)
            had_error = True
            continue
        try:
            findings = lint_detailed(path)
        except (OSError, UnicodeError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            had_error = True
            continue

        print(f"{path}: {len(findings)} candidate(s)")
        for line, label, excerpt, quoted in findings:
            is_blocking = label in blocking_labels and not quoted
            marker = " [blocking]" if is_blocking else (" [quoted]" if quoted else "")
            print(f"  L{line}: {label}{marker}: {excerpt}")
            if args.github_annotations:
                level = "error" if is_blocking else "warning"
                print(f"::{level} file={_annotation_property(str(path))},line={line}::"
                      f"{_annotation_value(f'{label}: {excerpt}')}")
            blocking += is_blocking
        total += len(findings)

    print(f"Total candidates: {total}; blocking: {blocking}")
    if had_error:
        return 2
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
