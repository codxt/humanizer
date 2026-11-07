#!/usr/bin/env python3
"""Mechanical preservation check between a source text and its edit.

Usage:
    python3 -S scripts/fidelity_check.py [--strict] [--json] SOURCE EDIT

The script never rewrites text. It lists meaning-bearing items whose count
changed between SOURCE and EDIT: numbers, currency, month and weekday names,
relative dates, links and e-mail addresses, code, quotations, bracketed
citations, qualifiers, modal verbs, negation, first-person words, apologies
and thanks, and names. Each finding gives the count on both sides.

A finding asks for a sentence-level comparison; it is not proof of drift.
Removing a stacked hedge or a formulaic "not only" changes counts on purpose.
A clean result is not proof of fidelity either: the check cannot see tense or
aspect ("refunding" vs "refunded"), a changed actor without a pronoun, a
condition moved to another clause, or a changed scope, and it ignores numbers
written as words. Text inside code is compared as code only.

Exit codes: 0 report, 1 findings with --strict, 2 usage or read error.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path


_spec = importlib.util.spec_from_file_location("prose_lint", Path(__file__).with_name("prose_lint.py"))
_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_lint)


def _lexicon(entries: dict[str, str]) -> list[tuple[str, re.Pattern[str]]]:
    return [(key, re.compile(r"(?<!\w)(?:" + pattern + r")(?!\w)")) for key, pattern in entries.items()]


MONTHS_EN = ["january", "february", "march", "april", "may", "june", "july",
             "august", "september", "october", "november", "december"]
MONTHS_RU = ["январ", "феврал", "март", "апрел", "ма[йяе]", "июн", "июл", "август",
             "сентябр", "октябр", "ноябр", "декабр"]
# "may" is counted as a modal verb, not as a month; "среда" is left out because it also means "environment".
DATE_WORDS = _lexicon({
    **{month: (MONTHS_RU[i] if MONTHS_RU[i].endswith("]") else MONTHS_RU[i] + r"\w*")
       + ("" if month == "may" else "|" + month) for i, month in enumerate(MONTHS_EN)},
    "monday": r"monday|понедельник\w*", "tuesday": r"tuesday|вторник\w*",
    "wednesday": r"wednesday", "thursday": r"thursday|четверг\w*",
    "friday": r"friday|пятниц\w*", "saturday": r"saturday|суббот\w*",
    "sunday": r"sunday|воскресень\w*",
    "today": r"today|tonight|сегодня", "tomorrow": r"tomorrow|завтра",
    "yesterday": r"yesterday|вчера", "day after tomorrow": r"послезавтра",
})

QUALIFIERS = _lexicon({key: key for key in [
    "usually", "typically", "generally", "normally", "often", "frequently", "sometimes",
    "occasionally", "rarely", "seldom", "approximately", "roughly", "nearly", "almost",
    "likely", "unlikely", "probably", "possibly", "perhaps", "apparently", "reportedly",
    "allegedly", "presumably", "estimated", "up to", "at least", "at most", "unless",
    "except", "only", "if", "subject to", "provided that",
    "обычно", "как правило", "чаще всего", "часто", "иногда", "редко", "примерно",
    "приблизительно", "почти", "вероятно", "возможно", "по-видимому", "предположительно",
    "по данным", "якобы", "видимо", "не менее", "не более", "не позднее", "не ранее",
    "если", "кроме", "за исключением", "при условии", "только", "лишь",
]} | {
    "about (number)": r"about(?= [$£€₽₸]?\d)", "around (number)": r"around(?= [$£€₽₸]?\d)",
    "no later than": r"(?:no|not) later than", "no earlier than": r"(?:no|not) earlier than",
    "no more than": r"(?:no|not) more than", "no less than": r"(?:no|not) less than",
    "около (number)": r"около(?= \d)", "порядка (number)": r"порядка(?= \d)",
    "до (number)": r"до(?= \d)", "от (number)": r"от(?= \d)", "свыше (number)": r"свыше(?= \d)",
})

MODALITY = _lexicon({key: key for key in [
    "must", "shall", "should", "will", "would", "can", "could", "may", "might",
    "need to", "needs to", "have to", "has to", "required", "requires", "obliged",
    "entitled", "allowed", "permitted",
    "следует", "необходимо", "нужно", "надо", "вправе", "разрешается", "запрещается",
]} | {
    "должен": r"долж(?:ен|на|но|ны)", "обязан": r"обязан[аоы]?|обязу\w*",
    "может": r"может|можем|можете|могут|можно|могу|мог(?:ли|ла|ло)?",
    "планирует": r"планиру\w*|намерен[аы]?", "будет": r"будет|будем|будут|буду",
})

NEGATION = _lexicon({key: key for key in [
    "not", "no", "never", "none", "nor", "neither", "without", "nobody", "nothing", "nowhere",
    "не", "нет", "ни", "никогда", "никто", "ничего", "нигде", "без",
]})

FIRST_PERSON = _lexicon({
    "i/me/my": r"i|me|my|mine|myself",
    "we/us/our": r"we|us|our|ours|ourselves",
    "я/мой": r"я|меня|мне|мной|мною|мой|моя|моё|мое|мои|моего|моей|моему|моим|моих|мою|моем|моём",
    "мы/наш": r"мы|нас|нам|нами|наш|наша|наше|наши|нашего|нашей|нашему|нашим|наших|нашу|нашем",
})

SPEECH_ACTS = _lexicon({
    "apology": r"sorry|apologi[sz]\w*|apology|regret\w*|извин\w*|прошу прощения|прости\w*|сожале\w*",
    "thanks": r"thank\w*|grateful|appreciate\w*|благодар\w*|спасибо|признательн\w*",
})

CURRENCY = [(key, re.compile(pattern)) for key, pattern in {
    "GBP": r"£|\bGBP\b|(?i:\bpounds? sterling\b)",
    "USD": r"\$|\bUSD\b|(?i:\bdollars?\b|(?<!\w)доллар\w*)",
    "EUR": r"€|\bEUR\b|(?i:\beuros?\b|(?<!\w)евро(?!\w))",
    "RUB": r"₽|\bRU[BR]\b|(?i:\br[o]?ubles?\b|(?<!\w)руб(?:\.|л\w*))",
    "KZT": r"₸|\bKZT\b|(?i:\btenge\b|(?<!\w)тенге(?!\w))",
    "AED": r"\bAED\b|(?i:\bdirhams?\b|(?<!\w)дирхам\w*)",
    "CHF": r"\bCHF\b",
    "CNY": r"¥|\bCNY\b|\bRMB\b",
}.items()]

CONTRACTIONS = [
    (re.compile(r"\bwon['’]t\b"), "will not"), (re.compile(r"\bcan['’]t\b"), "can not"),
    (re.compile(r"\bcannot\b"), "can not"), (re.compile(r"\bshan['’]t\b"), "shall not"),
    (re.compile(r"n['’]t\b"), " not"), (re.compile(r"['’]ll\b"), " will"),
    (re.compile(r"['’]re\b"), " are"), (re.compile(r"['’]ve\b"), " have"),
    (re.compile(r"['’]m\b"), " am"),
]

URL_OR_EMAIL = re.compile(r"https?://[^\s<>()\[\]]+|www\.[^\s<>()\[\]]+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CITATION = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]|\[@[\w:.-]+\]|\[\^[\w-]+\]")
DOTTED_DATE = re.compile(r"(?<![\d.,/])\d{1,4}[./]\d{1,2}[./]\d{1,4}(?![\d.,/]?\d)")
NUMBER = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:[\u00a0\u202f ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)")
WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
OPENERS = set("\"'«“„‘([{*_")
SENTENCE_END = set(".!?…—–-•*#>|")
POLITE_PRONOUNS = {"вы", "вас", "вам", "вами", "ваш", "ваша", "ваше", "ваши", "вашего",
                   "вашей", "вашему", "вашим", "ваших", "вашу", "вашем"}
TITLES = {"mr", "mrs", "ms", "dr", "prof", "sir"}
QUOTE_DELIMITERS = ("\"", "«", "»", "“", "”", "„")


def _canonical_number(raw: str) -> str:
    value = re.sub(r"[\u00a0\u202f ]", "", raw)
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", value):
        value = value.replace(",", "")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", value):
        value = value.replace(".", "").replace(",", ".")
    else:
        value = value.replace(",", ".")
    if value.isdigit():
        value = str(int(value))
    return value


def _numbers(prose: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for match in DOTTED_DATE.finditer(prose):
        counts.update(str(int(part)) for part in re.split(r"[./]", match.group(0)))
    rest = DOTTED_DATE.sub(lambda match: " " * len(match.group(0)), prose)
    counts.update(_canonical_number(match.group(0)) for match in NUMBER.finditer(rest))
    return counts


def _lexicon_counts(prose: str, lexicon: list[tuple[str, re.Pattern[str]]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for key, pattern in lexicon:
        found = len(pattern.findall(prose))
        if found:
            counts[key] = found
    return counts


def _normalize_words(prose: str) -> str:
    lowered = prose.lower().replace("ё", "е").replace("’", "'")
    for pattern, replacement in CONTRACTIONS:
        lowered = pattern.sub(replacement, lowered)
    return lowered


def _name_key(word: str) -> str:
    word = re.sub(r"['’]s$", "", word)
    if word.isupper() and len(word) >= 2:
        return word
    lowered = word.lower().replace("ё", "е")
    if re.search(r"[а-я]", lowered):
        return lowered[:5]
    return lowered


def _is_sentence_initial(text: str, start: int) -> bool:
    index = start - 1
    while index >= 0 and (text[index].isspace() or text[index] in OPENERS):
        if text[index] == "\n":
            return True
        index -= 1
    return index < 0 or text[index] in SENTENCE_END


def _names(prose: str) -> set[str]:
    names: set[str] = set()
    for match in WORD.finditer(prose):
        word = match.group(0)
        if len(word) < 2 or not word[0].isupper():
            continue
        lowered = word.lower().replace("’", "'")
        if lowered in POLITE_PRONOUNS or lowered in TITLES or lowered.startswith("i'"):
            continue
        if any(pattern.fullmatch(lowered) for _, pattern in DATE_WORDS):
            continue
        if any(pattern.fullmatch(word) for _, pattern in CURRENCY):
            continue
        if word.isupper() or not _is_sentence_initial(prose, match.start()):
            names.add(_name_key(word))
    return names


def _mentions(prose: str, key: str) -> bool:
    if key.isupper():
        return re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", prose) is not None
    lowered = prose.lower().replace("ё", "е")
    if re.search(r"[а-я]", key):
        return re.search(r"(?<!\w)" + re.escape(key), lowered) is not None
    return re.search(r"(?<!\w)" + re.escape(key) + r"(?:['’]s)?(?!\w)", lowered) is not None


def _quotations(text: str) -> Counter[str]:
    merged: list[list[int]] = []
    for start, end in sorted(_lint.quoted_ranges(_lint.strip_code_fences(text))):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    items: Counter[str] = Counter()
    for start, end in merged:
        value = re.sub(r"(?m)^[ \t]*(?:>[ \t]?)+", "", text[start:end]).strip()
        if len(value) >= 2 and value[0] in QUOTE_DELIMITERS and value[-1] in QUOTE_DELIMITERS:
            value = value[1:-1]
        value = " ".join(value.replace("’", "'").split())
        if value:
            items[value] += 1
    return items


def _blank(match: re.Match[str]) -> str:
    return " " * len(match.group(0))


def _prose(text: str) -> str:
    """Text with code, links and bracketed citations blanked; offsets are kept."""
    without_links = URL_OR_EMAIL.sub(_blank, _lint.mask_code(text, mask_urls=False))
    return CITATION.sub(_blank, without_links)


def profile(text: str) -> dict[str, Counter[str]]:
    """Counts of meaning-bearing items, by category."""
    code = Counter(" ".join(text[start:end].split()) for start, end in _lint.code_ranges(text))
    without_code = _lint.mask_code(text, mask_urls=False)
    links = Counter(match.group(0).rstrip(".,;:!?»”\"'") for match in URL_OR_EMAIL.finditer(without_code))
    citations = Counter(match.group(0) for match in CITATION.finditer(URL_OR_EMAIL.sub(_blank, without_code)))
    prose = _prose(text)
    words = _normalize_words(prose)
    return {
        "number": _numbers(prose),
        "currency": _lexicon_counts(prose, CURRENCY),
        "date word": _lexicon_counts(words, DATE_WORDS),
        "link": links,
        "code": code,
        "quotation": _quotations(text),
        "citation": citations,
        "qualifier": _lexicon_counts(words, QUALIFIERS),
        "modality": _lexicon_counts(words, MODALITY),
        "negation": _lexicon_counts(words, NEGATION),
        "first person": _lexicon_counts(words, FIRST_PERSON),
        "speech act": _lexicon_counts(words, SPEECH_ACTS),
        "name": Counter(_names(prose)),
    }


def compare(source: str, edit: str) -> list[dict[str, object]]:
    """Findings as dicts: category, change ("lost" or "added"), item, source and edit counts."""
    before, after = profile(source), profile(edit)
    source_prose, edit_prose = _prose(source), _prose(edit)
    findings: list[dict[str, object]] = []
    for category, counts in before.items():
        other = after[category]
        if category == "name":
            for key in sorted(counts):
                if not _mentions(edit_prose, key):
                    findings.append({"category": category, "change": "lost", "item": key,
                                     "source": 1, "edit": 0})
            for key in sorted(other):
                if not _mentions(source_prose, key):
                    findings.append({"category": category, "change": "added", "item": key,
                                     "source": 0, "edit": 1})
            continue
        for key in sorted(set(counts) | set(other)):
            source_count, edit_count = counts.get(key, 0), other.get(key, 0)
            if source_count != edit_count:
                findings.append({"category": category,
                                 "change": "lost" if edit_count < source_count else "added",
                                 "item": key, "source": source_count, "edit": edit_count})
    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog=Path(argv[0]).name if argv else "fidelity_check.py")
    parser.add_argument("source")
    parser.add_argument("edit")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any finding is reported")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    try:
        args = parser.parse_args(argv[1:])
    except SystemExit as exc:
        return 2 if exc.code else 0
    texts = []
    for raw in (args.source, args.edit):
        path = Path(raw)
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            return 2
    findings = compare(*texts)
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    else:
        print(f"{args.source} -> {args.edit}: {len(findings)} finding(s)")
        for item in findings:
            print(f"  {item['change']} {item['category']}: {item['item']} "
                  f"(source {item['source']}, edit {item['edit']})")
    return 1 if findings and args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
