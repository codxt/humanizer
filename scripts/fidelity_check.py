#!/usr/bin/env python3
"""Mechanical preservation check between a source text and its edit.

Usage:
    python3 -S scripts/fidelity_check.py [--strict] [--json] SOURCE EDIT

The script never rewrites text. It lists meaning-bearing items whose count
changed between SOURCE and EDIT: numbers with their sign and a following
percent, temperature, time or magnitude unit ("30 days", "10 business days",
"-5 °C", "1.5 million", "5 %"; other units such as kg or km are not compared),
numeric dates as ordered parts, currency, month and weekday names, relative
dates, links and e-mail addresses, code (indentation included, fence tag and
backtick width ignored), quotations, bracketed citations, qualifiers, modal
verbs, negation, first-person words, apologies and thanks, and names. Each finding gives the count on both sides.

A finding asks for a sentence-level comparison; it is not proof of drift.
Removing a stacked hedge or a formulaic "not only" changes counts on purpose,
and a date rewritten from digits to words (or back) shows up as a change.
A clean result is not proof of fidelity either: the check cannot see tense or
aspect ("refunding" vs "refunded"), a changed actor without a pronoun, a
condition moved to another clause, numbers swapped between objects ("5000 to
Alice, 3000 to Bob" and the reverse), or a changed scope; it ignores numbers
written as words; and it does not compare a name that only opens a sentence,
a paragraph, a list item or a heading, or that follows an abbreviation it does
not know. Russian names are matched by stem, so
names that differ only by an ending count as one. English "May" counts as a
modal verb, not a month. Text inside code is compared as code only.

Exit codes: 0 report, 1 findings with --strict, 2 usage or read error.
"""

from __future__ import annotations

import argparse
import bisect
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


MONTHS = [("january", "январ"), ("february", "феврал"), ("march", "март"), ("april", "апрел"),
          ("may", "ма[йяе]"), ("june", "июн"), ("july", "июл"), ("august", "август"),
          ("september", "сентябр"), ("october", "октябр"), ("november", "ноябр"), ("december", "декабр")]
# Matched in lowercased text. "среда" also means "environment", so it counts only after a preposition
# that marks a day ("в среду", "до среды", "по средам").
DATE_WORDS = _lexicon({
    **{month: stem if stem.endswith("]") else stem + r"\w*" for month, stem in MONTHS},
    "monday": r"monday|понедельник\w*", "tuesday": r"tuesday|вторник\w*",
    "wednesday": r"wednesday|(?:(?<=в )|(?<=во ))(?:(?:эту|ту|прошлую|следующую|ближайшую|каждую) )?среду"
                 r"|(?<=на )(?:эту|ту|прошлую|следующую|ближайшую|каждую) среду|(?:(?<=до )|(?<=со )|(?<=с )|(?<=после ))среды"
                 r"|(?<=по )средам|(?<=к )среде", "thursday": r"thursday|четверг\w*",
    "friday": r"friday|пятниц\w*", "saturday": r"saturday|суббот\w*",
    "sunday": r"sunday|воскресень\w*",
    "today": r"today|tonight|сегодня", "tomorrow": r"tomorrow|завтра",
    "yesterday": r"yesterday|вчера", "day after tomorrow": r"послезавтра",
})
# English months count only when capitalized, so the verb "march" is not a date. "May" is left
# to the modal verbs: it cannot be told apart from "May I…" at the start of a sentence.
EN_MONTHS = _lexicon({month: month.capitalize() for month, _ in MONTHS if month != "may"})

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

# Counted with the tokens "US" and "ME" blanked (country, state code), so they are not "us"/"me";
# "i.e." is not "I". All-caps "WE" and "МЫ" still count.
FIRST_PERSON = _lexicon({
    "i/me/my": r"i(?!\.\w)|me|my|mine|myself",
    "we/us/our": r"we|us|our|ours|ourselves",
    "я/мой": r"я|меня|мне|мной|мною|мой|моя|мое|мои|моего|моей|моему|моим|моих|мою|моем",
    "мы/наш": r"мы|нас|нам|нами|наш|наша|наше|наши|нашего|нашей|нашему|нашим|наших|нашу|нашем",
})

SPEECH_ACTS = _lexicon({
    "apology": r"sorry|apolog(?:y|ies|i[sz](?:e|es|ed|ing))|regret(?:s|ted|ting|tably|ful|fully)?"
               r"|извин\w*|прошу прощения|прости(?:те)?|сожале\w*",
    "thanks": r"thank(?:s|ed|ing|ful)?|thankful|grateful|gratitude|appreciat(?:e|es|ed|ing|ive)"
              r"|appreciation(?= (?:for|of (?:your|our|their|his|her)))"
              r"|благодар\w*|спасибо|признательн\w*",
})

CURRENCY = [(key, re.compile(pattern)) for key, pattern in {
    "GBP": r"£|\bGBP\b|(?i:\bpounds? sterling\b|(?<=\d )pounds?\b)",
    "USD": r"\$|\bUSD\b|(?i:\bdollars?\b|(?<!\w)доллар\w*)",
    "EUR": r"€|\bEUR\b|(?i:\beuros?\b|(?<!\w)евро(?!\w))",
    "RUB": r"₽|\bRU[BR]\b|(?i:\br[o]?ubles?\b|(?<!\w)руб(?:\.|(?!\w))|(?<!\w)рубл(?:ь|я|ю|ем|ём|е|ей|ям|ях|ями|и)(?!\w)|(?<!\w)рубл[её]в(?:ый|ая|ое|ые|ого|ому|ым|ом|ой|ою|ых|ыми|ую|ей|их)(?!\w)|(?<!\w)(?-i:рубл[её]в)(?!\w))",
    "KZT": r"₸|\bKZT\b|(?i:\btenge\b|(?<!\w)тенге(?!\w))",
    "AED": r"\bAED\b|(?i:\bdirhams?\b|(?<!\w)дирхам\w*)",
    "CHF": r"\bCHF\b",
    "CNY": r"\bCNY\b|\bRMB\b|(?i:\byuan\b|(?<!\w)юан\w*)",
    "JPY": r"\bJPY\b|(?i:\byen\b|(?<!\w)[ий]ен[аыеу]?(?!\w))",
    "¥ (JPY or CNY)": r"¥",
}.items()]

# A unit or magnitude right after a number becomes part of its key: "30 days" and "30 weeks" differ.
UNITS = [(key, re.compile(r"(?i:" + pattern + r")")) for key, pattern in [
    ("%", r"%|percent|per cent|процент\w*"), ("‰", r"‰"), ("°C", r"°\s?C"), ("°F", r"°\s?F"),
    ("thousand", r"thousands?|тыс\.?|тысяч\w*"), ("million", r"millions?|mln|mn|млн\.?|миллион\w*"),
    ("billion", r"billions?|bn|млрд\.?|миллиард\w*"), ("trillion", r"trillions?|трлн\.?|триллион\w*"),
    ("millisecond", r"milliseconds?|(?-i:ms|msecs?)|миллисекунд\w*|мс"),
    ("second", r"seconds?|(?-i:s|sec|secs)|секунд\w*|сек\.?"),
    ("minute", r"minutes?|mins?|минут\w*|мин\.?"), ("hour", r"hours?|hrs?|(?-i:h|ч)|час\w*"),
    ("day", r"days?|(?-i:d)|дн(?:я|ей|и)|день|сут(?:ок|ки)"), ("week", r"weeks?|(?-i:w)|недел\w*"),
    ("month", r"months?|месяц\w*|мес\.?"), ("year", r"years?|yrs?|(?-i:y)|год(?:а|у)?|лет"),
]]
BUSINESS_PREFIX = re.compile(r"(?:business|working|рабоч\w+)\s+", re.I)
# Single letters that mean a magnitude or hours only when glued to the number ("5m", "4K", "24h").
GLUED_UNITS = {"k": "thousand", "m": "million", "bn": "billion", "b": "billion", "h": "hour"}
# "calendar" and "full" days are days; "business" and "working" days are a different unit.
UNIT_AFTER = re.compile(r"([^\W\d_]+\b)|[ \u00a0]?(%|‰|°\s?[CF]\b)|[\s\u00a0-]+(?:(?:calendar|full|календарных|полных)\s+)?"
                        r"((?:(?:business|working|рабоч\w+)\s+)?[^\W\d_]+\.?)")

CONTRACTIONS = [
    (re.compile(r"\bwon['’]t\b"), "will not"), (re.compile(r"\bcan['’]t\b"), "can not"),
    (re.compile(r"\bcannot\b"), "can not"), (re.compile(r"\bshan['’]t\b"), "shall not"),
    (re.compile(r"n['’]t\b"), " not"), (re.compile(r"['’]ll\b"), " will"),
    (re.compile(r"['’]re\b"), " are"), (re.compile(r"['’]ve\b"), " have"),
    (re.compile(r"['’]m\b"), " am"),
]

URL_OR_EMAIL = re.compile(r"https?://[^\s<>()\[\]\"«»“”„]+|www\.[^\s<>()\[\]\"«»“”„]+|(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CITATION = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]|\[@[\w:.-]+\]|\[\^[\w-]+\]")
NUMERIC_DATE = re.compile(r"(?<![\d.,/-])(?:\d{1,4}[./]\d{1,2}[./]\d{1,4}|\d{4}-\d{1,2}-\d{1,2})(?![\d.,/-]?\d)")
NUMBER = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:[\u00a0\u202f ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)")
COUNTRY_US = re.compile(r"(?<!\w)(?:US|ME)(?!\w)")
TOKEN = re.compile(r"\w+(?:['’-]\w+)*")
OPENERS = set("\"'«“„‘([{*_")
SENTENCE_END = set(".!?…•*#>-–—")  # a colon does not start a sentence: "Attendees: Anna"
ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "st", "sr", "jr", "vs", "cf", "e.g", "i.e", "etc", "inc",
    "ltd", "co", "corp", "no", "vol", "fig", "approx", "dept", "gen", "col", "capt", "lt", "gov",
    "sen", "rep", "rev", "hon", "г", "гг", "т.е", "т.к", "т.н", "им", "ул", "д", "др", "проф",
    "акад", "тов", "ген", "г-н", "г-жа", "св", "см", "стр", "рис", "табл", "напр", "гл", "ст", "ч",
    "п", "пп", "тыс", "млн", "млрд", "руб", "коп", "долл",
}
NOT_NAMES = {
    "вы", "вас", "вам", "вами", "ваш", "ваша", "ваше", "ваши", "вашего", "вашей", "вашему",
    "вашим", "ваших", "вашу", "вашем", "mr", "mrs", "ms", "dr", "prof", "sir", "may",
    "the", "a", "an", "this", "that", "these", "those", "it", "its", "we", "you", "he", "she",
    "they", "our", "my", "your", "their", "his", "her", "and", "but", "or", "if", "when",
    "in", "on", "at", "for", "to", "of", "by", "with", "as", "there", "here", "then", "so",
    "no", "not", "all", "any", "each", "every", "please",
    "это", "этот", "эта", "эти", "мы", "я", "он", "она", "они", "оно", "в", "на", "по", "для",
    "с", "со", "к", "о", "об", "и", "а", "но", "или", "если", "когда", "как", "что", "при",
    "после", "до", "из", "у", "за", "не", "нет", "да", "так", "также", "однако",
}
QUOTE_DELIMITERS = ("\"", "«", "»", "“", "”", "„")
QUOTE_EDGE_PUNCTUATION = ".,;:!?… "


def _blank(match: re.Match[str]) -> str:
    return " " * len(match.group(0))


def _canonical_number(raw: str, decimal_comma: bool) -> str:
    """Spaces group thousands; a comma does too in Latin-script text, and is a decimal mark in
    Cyrillic text ("1,500 кг" is 1.5 kg). Dots are never read as thousands separators, so an
    ambiguous "1.500" stays its own key and over-reports instead of hiding a 1000x change."""
    value = re.sub(r"[\u00a0\u202f ]", "", raw)
    if not decimal_comma and re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", value):
        value = value.replace(",", "")
    else:
        value = value.replace(",", ".")
    if value.isdigit():
        value = value.lstrip("0") or "0"
    return value


def _unit_after(prose: str, end: int) -> str:
    match = UNIT_AFTER.match(prose, end)
    if not match:
        return ""
    glued, symbol, word = match.groups()
    if glued and glued.lower() in GLUED_UNITS:
        return GLUED_UNITS[glued.lower()]
    candidate = glued or symbol or word  # "10s", "10sec" and "10 s" go through the same table
    prefix = ""
    business = BUSINESS_PREFIX.match(candidate)
    if business:  # "10 working hours" is "10 business hour", not "10 hour"
        prefix, candidate = "business ", candidate[business.end():]
    for key, pattern in UNITS:
        if pattern.fullmatch(candidate) or pattern.fullmatch(candidate.rstrip(".")):
            return prefix + key
    return ""


def _sign_before(prose: str, start: int) -> str:
    if start and prose[start - 1] in "-−+" and (start == 1 or prose[start - 2] in " \t\n([«\"“"):
        if re.search(r"(?:^|[^\d\s.,])[ \t]*(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d[\d.,]*)[ \t\u00a0]+$",
                     prose[max(0, start - 40):start - 1]):
            return ""  # "pages 10 -20" is a range; "readings 1 2 -20" keeps the sign
        return "+" if prose[start - 1] == "+" else "-"
    return ""


def _numbers(prose: str) -> tuple[Counter[str], Counter[str]]:
    """Numeric dates (ordered parts) and other numbers (with sign and unit), counted separately."""
    decimal_comma = len(re.findall(r"[а-яё]", prose, re.I)) > len(re.findall(r"[a-z]", prose, re.I))
    dates = Counter(".".join(part.lstrip("0") or "0" for part in re.split(r"[./-]", match.group(0)))
                    for match in NUMERIC_DATE.finditer(prose))
    rest = NUMERIC_DATE.sub(_blank, prose)
    numbers: Counter[str] = Counter()
    for match in NUMBER.finditer(rest):
        unit = _unit_after(rest, match.end())
        value = _sign_before(rest, match.start()) + _canonical_number(match.group(0), decimal_comma)
        numbers[f"{value} {unit}" if unit else value] += 1
    return dates, numbers


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
    if word.isupper():
        return word
    lowered = word.lower().replace("ё", "е")
    if re.fullmatch(r"[а-я'-]+", lowered):
        return lowered[:5]
    return lowered


def _is_sentence_initial(text: str, start: int) -> bool:
    """True at the start of the text, a sentence, a paragraph, a list item, or a heading.

    A single line break inside a hard-wrapped paragraph does not start a sentence; a table
    cell does not either, so names in tables are compared.
    """
    index = start - 1
    while index >= 0 and (text[index].isspace() or text[index] in OPENERS):
        index -= 1
    if index < 0 or text.count("\n", index + 1, start) > 1:
        return True
    if text[index] == ".":
        token_start = index
        while token_start > 0 and (text[token_start - 1].isalpha() or text[token_start - 1] in ".-"):
            token_start -= 1
        token = text[token_start:index].lower()
        parts = token.split(".")
        dotted_short = len(parts) > 1 and all(0 < len(part) <= 2 for part in parts)
        if token in ABBREVIATIONS or (len(token) == 1 and token.isalpha()) or dotted_short:
            return False  # "Dr. Ivanov", "e.g. Acme", "U.S. Treasury", "И. Петров"
    return text[index] in SENTENCE_END


def _names(prose: str) -> set[str]:
    names: set[str] = set()
    for match in TOKEN.finditer(prose):
        word = match.group(0)
        if len(word) < 2 or not word[0].isupper() or re.search(r"[\d_]", word):
            continue
        lowered = word.lower().replace("’", "'")
        if lowered in NOT_NAMES or lowered.startswith("i'"):
            continue
        if any(pattern.fullmatch(lowered) for _, pattern in DATE_WORDS):
            continue
        if any(pattern.fullmatch(word) for _, pattern in CURRENCY):
            continue
        if word.isupper() or not _is_sentence_initial(prose, match.start()):
            names.add(_name_key(word))
    return names


def _mentions(prose: str, key: str) -> bool:
    if key.isupper() and len(key) < 4:
        return re.search(r"(?<!\w)" + re.escape(key) + r"(?!\w)", prose) is not None
    if key.isupper():  # a longer all-caps name may change case: «РОМАШКА» and «Ромашка» are one company
        key = _name_key(key.capitalize())
    lowered = prose.lower().replace("ё", "е")
    if re.search(r"[а-я]", key):
        return re.search(r"(?<!\w)" + re.escape(key), lowered) is not None
    return re.search(r"(?<!\w)" + re.escape(key) + r"(?:['’]s)?(?!\w)", lowered) is not None


def _quotations(text: str) -> Counter[str]:
    """Blockquotes (consecutive lines joined) and inline quotations not inside them."""
    scan = _lint.mask_code(text, mask_urls=False)
    blocks: list[list[int]] = []
    for start, end in _lint._blockquote_ranges(scan):
        if blocks and start <= blocks[-1][1]:
            blocks[-1][1] = max(blocks[-1][1], end)
        else:
            blocks.append([start, end])
    block_starts = [start for start, _ in blocks]
    inline: list[tuple[int, int]] = []
    reach = -1
    for start, end in sorted(set(_lint.quoted_ranges(scan)), key=lambda item: (item[0], -item[1])):
        block = bisect.bisect_right(block_starts, start) - 1
        if block >= 0 and end <= blocks[block][1]:
            continue  # inside a blockquote, which is compared as a whole
        if end <= reach:
            continue  # nested inside an outer quotation
        inline.append((start, end))
        reach = end
    items: Counter[str] = Counter()
    for start, end in [tuple(block) for block in blocks] + inline:
        value = re.sub(r"(?m)^[ \t]*(?:>[ \t]?)+", "", text[start:end]).strip()
        if len(value) >= 2 and value[0] in QUOTE_DELIMITERS and value[-1] in QUOTE_DELIMITERS:
            value = value[1:-1]
        value = " ".join(value.replace("’", "'").split()).strip(QUOTE_EDGE_PUNCTUATION)
        if value:
            items[value] += 1
    return items


def _code_body(segment: str) -> str:
    """The code itself: fence lines and inline backtick delimiters removed."""
    lines = re.split(r"\r\n|\r|\n", segment)
    if lines and lines[-1] == "":
        lines = lines[:-1]
    opener = re.match(r" {0,3}(`{3,}|~{3,})([^\r\n]*)", lines[0]) if lines else None
    if opener and (opener.group(1)[0] != "`" or "`" not in opener.group(2)):  # as in prose_lint
        lines = lines[1:]
        if lines and re.fullmatch(r" {0,3}(?:`{3,}|~{3,})[ \t]*", lines[-1]):
            lines = lines[:-1]
    else:
        body = segment.strip("`")
        if len(body) > 2 and body.startswith(" ") and body.endswith(" ") and body.strip():
            body = body[1:-1]  # CommonMark drops one padding space on each side
        lines = [body]
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def _code(text: str) -> Counter[str]:
    """Code compared line by line; indentation counts, trailing spaces, CR/LF line endings, the
    fence language tag and the inline delimiter width do not. Only CR and LF end a line, as in
    CommonMark and `prose_lint.code_ranges`."""
    return Counter(_code_body(text[start:end]) for start, end in _lint.code_ranges(text))


def _prose(text: str) -> str:
    """Text with code, links and bracketed citations blanked; offsets are kept."""
    without_links = URL_OR_EMAIL.sub(_blank, _lint.mask_code(text, mask_urls=False))
    return CITATION.sub(_blank, without_links)


def profile(text: str) -> dict[str, Counter[str]]:
    """Counts of meaning-bearing items, by category."""
    without_code = _lint.mask_code(text, mask_urls=False)
    links = Counter(match.group(0).rstrip(".,;:!?»”\"'…—–") for match in URL_OR_EMAIL.finditer(without_code))
    citations = Counter(match.group(0) for match in CITATION.finditer(URL_OR_EMAIL.sub(_blank, without_code)))
    prose = _prose(text)
    words = _normalize_words(prose)
    dates, numbers = _numbers(prose)
    return {
        "date": dates,
        "number": numbers,
        "currency": _lexicon_counts(prose, CURRENCY),
        "date word": _lexicon_counts(words, DATE_WORDS) + _lexicon_counts(prose, EN_MONTHS),
        "link": links,
        "code": _code(text),
        "quotation": _quotations(text),
        "citation": citations,
        "qualifier": _lexicon_counts(words, QUALIFIERS),
        "modality": _lexicon_counts(words, MODALITY),
        "negation": _lexicon_counts(words, NEGATION),
        "first person": _lexicon_counts(_normalize_words(COUNTRY_US.sub(_blank, prose)), FIRST_PERSON),
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
