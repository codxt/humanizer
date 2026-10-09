#!/usr/bin/env python3
"""Report-only prose lint for common AI-pattern candidates.

Usage:
    python3 -S .agents/skills/humanizer/scripts/prose_lint.py <file> [<file> ...]

The script never rewrites text. Matches are review candidates, not proof of AI
origination and not automatic replacement instructions.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path


PATTERNS = [
    ("chatbot residue", re.compile(r"\b(?:hope this helps|let(?:'|’)s dive in|here(?:'|’)s the thing|after careful consideration|i wanted to provide a quick update)\b", re.I)),
    ("inflated vocabulary", re.compile(r"\b(?:delve|crucial|pivotal|foundational|tapestry|robust|seamless|landscape|realm|vibrant|groundbreaking|transformative)\b", re.I)),
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
]

BOLD_LABEL = re.compile(r"^\s*[-*+]\s+\*\*[^*]{2,80}:\*\*\s+")
TITLE_CASE_HEADING = re.compile(r"^#{1,6}\s+(?:[A-Z][\w'-]+\s+){2,}[A-Z][\w'-]+\s*$")
STACKED_SHORT = re.compile(r"(?m)(?:^[^\n.!?]{1,45}[.!?]\s*$\n?){3,}")
MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def strip_code_fences(text: str) -> str:
    """Mask Markdown code while preserving source offsets and line numbers."""
    def mask(value: str) -> str:
        return "".join(char if char in "\r\n" else " " for char in value)

    lines: list[str] = []
    fence_char = ""
    fence_length = 0
    for line in text.splitlines(keepends=True):
        if fence_char:
            lines.append(mask(line))
            closing = re.fullmatch(r" {0,3}(" + re.escape(fence_char) + r"{"
                                   + str(fence_length) + r",})[ \t]*(?:\r?\n)?", line)
            if closing:
                fence_char = ""
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})([^\r\n]*)", line)
        if opening and (opening.group(1)[0] != "`" or "`" not in opening.group(2)):
            fence_char = opening.group(1)[0]
            fence_length = len(opening.group(1))
            lines.append(mask(line))
        else:
            lines.append(line)

    scan = "".join(lines)
    scan = re.sub(r"(?<!`)(`+)(?!`)[^\r\n]*?(?<!`)\1(?!`)",
                  lambda match: mask(match.group(0)), scan)
    return re.sub(r"https?://[^\s<>]+", lambda match: mask(match.group(0)), scan)


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


def lint(path: Path) -> list[tuple[int, str, str]]:
    text = path.read_text(encoding="utf-8")
    scan = strip_code_fences(text)
    findings: list[tuple[int, str, str]] = []

    for label, pattern in PATTERNS:
        for match in pattern.finditer(scan):
            line = scan.count("\n", 0, match.start()) + 1
            excerpt = " ".join(match.group(0).split())
            findings.append((line, label, excerpt))

    for number, line_text in enumerate(scan.splitlines(), 1):
        if BOLD_LABEL.search(line_text):
            findings.append((number, "bold-label bullet", line_text.strip()))
        if TITLE_CASE_HEADING.search(line_text):
            findings.append((number, "title-case heading", line_text.strip()))

    for match in STACKED_SHORT.finditer(scan):
        line = scan.count("\n", 0, match.start()) + 1
        excerpt = " / ".join(part.strip() for part in match.group(0).splitlines() if part.strip())
        findings.append((line, "stacked short-sentence rhythm", excerpt[:220]))

    findings.extend(uniform_heading_geometry(scan))
    findings.sort(key=lambda item: (item[0], item[1], item[2]))
    return findings


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: prose_lint.py <file> [<file> ...]", file=sys.stderr)
        return 2

    total = 0
    had_error = False
    for raw in argv[1:]:
        path = Path(raw)
        if not path.is_file():
            print(f"{path}: not a file", file=sys.stderr)
            had_error = True
            continue
        try:
            findings = lint(path)
        except (OSError, UnicodeError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            had_error = True
            continue

        print(f"{path}: {len(findings)} candidate(s)")
        for line, label, excerpt in findings:
            print(f"  L{line}: {label}: {excerpt}")
        total += len(findings)

    print(f"Total candidates: {total}")
    return 2 if had_error else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
