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
verbs, negation (a free-standing word and a Russian `не-` on a word the other
side has without it), first-person words, apologies and thanks, and names. Each finding gives the
count on both sides.

A finding asks for a sentence-level comparison; it is not proof of drift.
Removing a stacked hedge or a formulaic "not only" changes counts on purpose,
and a date rewritten from digits to words (or back) shows up as a change.
A clean result is not proof of fidelity either: the check cannot see tense or
aspect ("refunding" vs "refunded"), a changed actor without a pronoun, a
condition moved to another clause, numbers swapped between objects ("5000 to
Alice, 3000 to Bob" and the reverse), or a changed scope; it ignores numbers
written as words; and it does not compare a name that only opens a sentence,
a paragraph, a list item or a heading, or that follows an abbreviation it does
not know. Russian names are compared as whole words, with only an enumerated
case ending allowed to differ, and a mention must be capitalized (so «Роман»
does not match «романом»). English month names count in either case; "March"
counts only capitalized, so the verb is not a date, and "May" counts as a
modal verb, not a month. A capitalized Russian month form is a person's name,
not a date, unless a day number, a year or a preposition of time marks it
(«Договор подписал Август», «Марта пришла»; but «5 Августа», «Август 2026»,
«в Августе» stay dates). Text inside fenced code and inline code spans is
compared as code only; indented (four-space) code blocks are read as prose, and
a fence inside a blockquote is compared as part of the quotation. Quotation
detection is permissive: keep blockquote continuations after containers, inline
quotations across block starts within nonblank runs, and numeric endings after
sentence stops. The gate uses strict detection; this CLI's --strict controls
only the findings exit code.

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


MONTHS = [("january", r"январ\w*"), ("february", r"феврал\w*"),
          ("march", r"март|марта|марте|марту|мартом"), ("april", r"апрел\w*"),
          ("may", r"ма[йяе]|маю|маем"), ("june", r"июн\w*"), ("july", r"июл\w*"),
          ("august", r"август\w*"), ("september", r"сентябр\w*"), ("october", r"октябр\w*"),
          ("november", r"ноябр\w*"), ("december", r"декабр\w*")]
# Matched in lowercased text. Russian month patterns are closed where an open stem would swallow a
# longer word: «март\w*» would make the name Мартын March, and «ма[йяе]» without whole forms misses
# «маю» and «маем». "среда" also means "environment", so it counts only after a preposition
# that marks a day ("в среду", "до среды", "по средам").
MONTH_FORMS = [(month, re.compile(pattern)) for month, pattern in MONTHS]
DATE_WORDS = _lexicon({
    **{month: pattern for month, pattern in MONTHS},
    "monday": r"monday|понедельник\w*", "tuesday": r"tuesday|вторник\w*",
    "wednesday": r"wednesday|(?:(?<=в )|(?<=во ))(?:(?:эту|ту|прошлую|следующую|ближайшую|каждую) )?среду"
                 r"|(?<=на )(?:эту|ту|прошлую|следующую|ближайшую|каждую) среду|(?:(?<=до )|(?<=со )|(?<=с )|(?<=после ))среды"
                 r"|(?<=по )средам|(?<=к )среде", "thursday": r"thursday|четверг\w*",
    "friday": r"friday|пятниц\w*", "saturday": r"saturday|суббот\w*",
    "sunday": r"sunday|воскресень\w*",
    "today": r"today|tonight|сегодня", "tomorrow": r"tomorrow|завтра",
    "yesterday": r"yesterday|вчера", "day after tomorrow": r"послезавтра",
})
# English months count in either case, except "March": it stays capitalized so the verb is not a
# date. "May" is left to the modal verbs: it cannot be told apart from "May I…" at the start of a
# sentence.
EN_MONTHS = _lexicon({
    **{month: f"(?i:{month})" for month, _ in MONTHS if month not in ("may", "march")},
    "march": "March",
})
# A date marks a month form: a day number before it, a year after it, or a preposition that takes
# a month. Without one, a capitalized Russian month form is a person's name (see `_is_month_name`).
TIME_PREPOSITIONS = {"в", "во", "к", "ко", "до", "с", "со", "по", "на", "от", "ото"}
DAY_BEFORE = re.compile(r"(?<![\d.,])\d{1,2}[ \t]*$")
YEAR_AFTER = re.compile(r"[ \t]*,?[ \t]*(?:19|20)\d\d(?!\w)")
PREPOSITION_BEFORE = re.compile(r"(\w+)[ \t]*$")

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
    "может": r"может|можем|можете|можешь|могут|можно|могу|мог(?:ли|ла|ло)?",
    "планирует": r"планиру\w*|намерен[аы]?", "будет": r"будет|будем|будут|буду|будешь|будете",
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
# Russian unit patterns list the real paradigm; an open `\w*` stem would read «2 тысячелетия» as
# two thousand, «2 части» as two hours and «5 миллионеров» as five million.
UNITS = [(key, re.compile(r"(?i:" + pattern + r")")) for key, pattern in [
    ("%", r"%|percent|per cent|процент(?:а|ов|у|ом|е|ам|ами|ах)?"), ("‰", r"‰"), ("°C", r"°\s?C"), ("°F", r"°\s?F"),
    ("thousand", r"thousands?|тыс\.?|тысяч(?:а|и|у|ей|е|ам|ами|ах)?"),
    ("million", r"millions?|mln|mn|млн\.?|миллион(?:а|ов|у|ом|е|ам|ами|ах)?"),
    ("billion", r"billions?|bn|млрд\.?|миллиард(?:а|ов|у|ом|е|ам|ами|ах)?"),
    ("trillion", r"trillions?|трлн\.?|триллион(?:а|ов|у|ом|е|ам|ами|ах)?"),
    ("millisecond", r"milliseconds?|(?-i:ms|msecs?)|миллисекунд\w*|мс"),
    ("second", r"seconds?|(?-i:s|sec|secs)|секунд\w*|сек\.?"),
    ("minute", r"minutes?|mins?|минут\w*|мин\.?"),
    ("hour", r"hours?|hrs?|(?-i:h|ч)|час(?:а|ов|у|ом|е|ам|ами|ах)?"),
    ("day", r"days?|(?-i:d)|дн(?:я|ей|и)|день|сут(?:ок|ки)"), ("week", r"weeks?|(?-i:w)|недел\w*"),
    ("month", r"months?|месяц\w*|мес\.?"), ("year", r"years?|yrs?|(?-i:y)|год(?:а|у)?|лет"),
]]
PER_CENT = re.compile(r"per[\s\u00a0-]+cent", re.I)  # any case, spacing or hyphen: one percent sign
# "10 Per Cent" is a unit, not two names; "Per Hansen" and "50 Cent" stay names.
PERCENT_AFTER_NUMBER = re.compile(r"(?<=\d)(?:[ \t\u00a0-]*)(?:per[\s\u00a0-]+cent|percent)\b", re.I)
BUSINESS_PREFIX = re.compile(r"(?:business|working|рабоч\w+)\s+", re.I)
# Short forms that mean a magnitude or hours only when glued to the number ("5m", "4K", "5bn",
# "24h"). A single glued "b" is not billion: it is an outline or question label ("5b").
GLUED_UNITS = {"k": "thousand", "m": "million", "bn": "billion", "h": "hour"}
# "г" after a 3- or 4-digit number is the year abbreviation ("2024 г."); "5 г" (grams) stays a
# bare 5, the safe side of that limit.
YEAR_DIGITS = re.compile(r"\d{3,4}")
YEAR_ABBREVIATION = re.compile(r"г|гг", re.I)
# "calendar" and "full" days are days; "business" and "working" days are a different unit.
# The gap between a number and a word unit is same-line whitespace or hyphens, plus at most one line
# break whose next line does not start a blank line, list item, heading, quote or table row; symbol
# units (%, ‰, °C, °F) allow only one space or no-break space before the symbol
# ("10\n- Per cent growth" has no unit; "24\n-hour" and "10\nhours" do).
UNIT_GAP = (r"(?:(?:[^\S\r\n]|-)*(?:\r\n|\r|\n)"
            r"(?![^\S\r\n]*(?:[-*+](?:[^\S\r\n]|\r|\n|$)|[>#|]|\d+[.)][^\S\r\n]|\r|\n|$))(?:[^\S\r\n]|-)*"
            r"|(?:[^\S\r\n]|-)+)")
UNIT_AFTER = re.compile(r"([^\W\d_]+\b)|[ \u00a0]?(%|‰|°\s?[CF]\b)|" + UNIT_GAP + r"(?:(?:calendar|full|календарных|полных)\s+)?"
                        r"((?:(?:business|working|рабоч\w+)\s+)?(?:(?i:per[\s\u00a0-]+cent)\b|[^\W\d_]+)\.?)")

CONTRACTIONS = [
    (re.compile(r"\bwon['’]t\b"), "will not"), (re.compile(r"\bcan['’]t\b"), "can not"),
    (re.compile(r"\bcannot\b"), "can not"), (re.compile(r"\bshan['’]t\b"), "shall not"),
    (re.compile(r"n['’]t\b"), " not"), (re.compile(r"['’]ll\b"), " will"),
    (re.compile(r"['’]re\b"), " are"), (re.compile(r"['’]ve\b"), " have"),
    (re.compile(r"['’]m\b"), " am"),
]

URL_CHAR = r"[^\s<>()\[\]\"«»“”„]"
URL_PAREN = r"\([^\s()<>\[\]\"«»“”„]*\)"
# Balanced "(…)" keeps a Wikipedia title whole: «Альберт_(имя)» is one link, not a stem.
URL_OR_EMAIL = re.compile(
    r"https?://" + URL_CHAR + r"+(?:" + URL_PAREN + URL_CHAR + r"*)*"
    r"|www\." + URL_CHAR + r"+(?:" + URL_PAREN + URL_CHAR + r"*)*"
    r"|(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CITATION = re.compile(r"\[\d+(?:\s*[,–-]\s*\d+)*\]|\[@[\w:.-]+\]|\[\^[\w-]+\]")
NUMERIC_DATE = re.compile(r"(?<![\d.,/-])(?:\d{1,4}[./]\d{1,2}[./]\d{1,4}|\d{4}-\d{1,2}-\d{1,2})(?![\d.,/-]?\d)")
NUMBER = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:[\u00a0\u202f ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)")
COUNTRY_US = re.compile(r"(?<!\w)(?:US|ME)(?!\w)")
TOKEN = re.compile(r"\w+(?:['’-]\w+)*")
OPENERS = set("\"'«“„‘([{*_")
SENTENCE_END = set(".!?…•*#>-")  # a colon does not start a sentence: "Attendees: Anna"
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
    """Spaces group thousands; a comma does too in a Latin-script sentence, and is a decimal mark
    in a Cyrillic one ("1,500 кг" is 1.5 kg). Dots are never read as thousands separators, so an
    ambiguous "1.500" stays its own key and over-reports instead of hiding a 1000x change."""
    value = re.sub(r"[\u00a0\u202f ]", "", raw)
    if not decimal_comma and re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", value):
        value = value.replace(",", "")
    else:
        value = value.replace(",", ".")
    if value.isdigit():
        value = value.lstrip("0") or "0"
    return value


def _unit_after(prose: str, end: int, number: str = "") -> str:
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
    if PER_CENT.fullmatch(candidate.rstrip(".")):
        return prefix + "%"
    if (YEAR_DIGITS.fullmatch(re.sub(r"[\u00a0\u202f ]", "", number))
            and YEAR_ABBREVIATION.fullmatch(candidate.rstrip("."))):
        return prefix + "year"
    for key, pattern in UNITS:
        if pattern.fullmatch(candidate) or pattern.fullmatch(candidate.rstrip(".")):
            return prefix + key
    return ""


def _sign_before(prose: str, start: int) -> str:
    # An en or em dash is a printed minus sign; the range guard below still refuses one when a
    # number sits in front of the dash ("10–20").
    if start and prose[start - 1] in "-−+–—" and (start == 1 or prose[start - 2] in " \t\n([«\"“"):
        if re.search(r"(?:^|[^\d\s.,])[ \t]*(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d[\d.,]*)[ \t\u00a0]+$",
                     prose[max(0, start - 40):start - 1]):
            return ""  # "pages 10 -20" is a range; "readings 1 2 -20" keeps the sign
        return "+" if prose[start - 1] == "+" else "-"
    return ""


SENTENCE_STOP = re.compile(r"[.!?…]+")
CYRILLIC_LETTER = re.compile(r"[а-яё]", re.I)
LATIN_LETTER = re.compile(r"[a-z]", re.I)


def _sentence_rules(prose: str) -> tuple[list[int], list[bool]]:
    """Sentence start offsets and, for each, whether a comma in it is a decimal mark.

    True when Cyrillic letters outnumber Latin ones in that sentence, as the old document-wide
    count did. A sentence with no letters at all takes the document-wide reading."""
    starts = [0]
    letters: list[tuple[int, int]] = []
    begin = 0
    for stop in SENTENCE_STOP.finditer(prose):
        segment = prose[begin:stop.end()]
        letters.append((len(CYRILLIC_LETTER.findall(segment)), len(LATIN_LETTER.findall(segment))))
        starts.append(stop.end())
        begin = stop.end()
    tail = prose[begin:]
    letters.append((len(CYRILLIC_LETTER.findall(tail)), len(LATIN_LETTER.findall(tail))))
    total_cyrillic = sum(count[0] for count in letters)
    total_latin = sum(count[1] for count in letters)
    default = total_cyrillic > total_latin
    return starts, [cyrillic > latin if cyrillic or latin else default for cyrillic, latin in letters]


def _numbers(prose: str) -> tuple[Counter[str], Counter[str]]:
    """Numeric dates (ordered parts) and other numbers (with sign and unit), counted separately."""
    starts, rules = _sentence_rules(prose)  # `rest` below keeps every offset, so `starts` applies
    dates = Counter(".".join(part.lstrip("0") or "0" for part in re.split(r"[./-]", match.group(0)))
                    for match in NUMERIC_DATE.finditer(prose))
    rest = NUMERIC_DATE.sub(_blank, prose)
    numbers: Counter[str] = Counter()
    for match in NUMBER.finditer(rest):
        rule = rules[bisect.bisect_right(starts, match.start()) - 1]
        unit = _unit_after(rest, match.end(), match.group(0))
        value = _sign_before(rest, match.start()) + _canonical_number(match.group(0), rule)
        numbers[f"{value} {unit}" if unit else value] += 1
    return dates, numbers


def _lexicon_counts(prose: str, lexicon: list[tuple[str, re.Pattern[str]]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for key, pattern in lexicon:
        found = len(pattern.findall(prose))
        if found:
            counts[key] = found
    return counts


def _month_form_key(word: str) -> str | None:
    """The month key of a Russian month form («марта», «Августом»), or None."""
    lowered = word.lower().replace("ё", "е")
    for key, pattern in MONTH_FORMS:
        if pattern.fullmatch(lowered):
            return key
    return None


def _month_date_context(prose: str, start: int, end: int) -> bool:
    """Does a date mark this month form: a day number before («5 Августа»), a year after
    («Август 2026»), or one of the prepositions that take a month («в Августе»)?"""
    before = prose[max(0, start - 40):start]
    if DAY_BEFORE.search(before) or YEAR_AFTER.match(prose, end):
        return True
    word = PREPOSITION_BEFORE.search(before)
    return bool(word and word.group(1).lower().replace("ё", "е") in TIME_PREPOSITIONS)


def _is_month_name(prose: str, match: re.Match[str]) -> bool:
    """A capitalized Russian month form away from a date is a person's name.

    Russian dates are lowercase except when a sentence happens to start with one, so a capital
    alone does not make a date: «Договор подписал Август» and «Марта пришла» are names, while a
    day number, a year or a preposition of time keeps «5 Августа», «Август 2026» and «в Августе»
    dates. This only decides between a name and a date word; the other categories are unaffected."""
    word = match.group(0)
    return (_month_form_key(word) is not None and word[:1].isupper()
            and not _month_date_context(prose, match.start(), match.end()))


def _date_words(prose: str) -> Counter[str]:
    """Date words, without a capitalized Russian month form that is a name: a lost «Август» is a
    lost name, not a lost August."""
    counts = _lexicon_counts(_normalize_words(prose), DATE_WORDS) + _lexicon_counts(prose, EN_MONTHS)
    for match in TOKEN.finditer(prose):
        if _is_month_name(prose, match):
            counts[_month_form_key(match.group(0))] -= 1
    return +counts


def _normalize_words(prose: str) -> str:
    lowered = _lint.fold_spaces(prose).lower().replace("ё", "е").replace("’", "'")
    for pattern, replacement in CONTRACTIONS:
        lowered = pattern.sub(replacement, lowered)
    return lowered


def _name_key(word: str) -> str:
    word = re.sub(r"['’]s$", "", word)
    if word.isupper():
        return word
    return word.lower().replace("ё", "е")


# Only a common case ending may differ after the name itself ("Петров" / "Петровым"). Longest
# first, so «Дмитрий» and «Дмитрия» share the stem «дмитр». A name is not a five-letter prefix:
# «Александр» and «Алексей» stay different people.
CYRILLIC_ENDINGS = [
    "его", "ого", "ему", "ому", "ием", "еем", "ыми", "ими", "ами", "ями",
    "ея", "ею", "ее", "ия", "ию", "ии", "ий", "ой", "ей", "ая", "яя", "ое", "ые", "ие", "ый",
    "им", "ым", "ом", "ем", "ём", "ах", "ях", "ам", "ям", "ую", "юю", "ья", "ьи", "ье", "ью",
    "а", "я", "у", "ю", "е", "ы", "и",
]
CYRILLIC_INFLECTION = "(?:" + "|".join(CYRILLIC_ENDINGS) + ")?"


def _stem(word: str) -> str:
    """Drop one common case ending, so «Петров» and «Петровым» share a stem; a part shorter
    than two letters keeps its form."""
    parts = []
    for part in word.split("-"):
        for ending in CYRILLIC_ENDINGS:
            if part.endswith(ending) and len(part) - len(ending) >= 2:
                part = part[:-len(ending)]
                break
        parts.append(part)
    return "-".join(parts)


def _is_sentence_initial(text: str, start: int) -> bool:
    """True at the start of the text, a sentence, a paragraph, a list item, or a heading.

    A single line break inside a hard-wrapped paragraph does not start a sentence; a table
    cell does not either, so names in tables are compared. A dash starts a sentence only at
    the start of a line (dialogue): "друга — Анну" leaves Анну in the name set.
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
    if text[index] in "–—":
        return not text[text.rfind("\n", 0, index) + 1:index].strip()
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
        month_name = _is_month_name(prose, match)
        if not month_name and any(pattern.fullmatch(lowered) for _, pattern in DATE_WORDS):
            continue
        if any(pattern.fullmatch(word) for _, pattern in CURRENCY):
            continue
        if word.isupper() or month_name or not _is_sentence_initial(prose, match.start()):
            names.add(_name_key(word))
    return names


def _mention_count(prose: str, key: str) -> int:
    """How many times this name appears in the prose, so a count is not invented."""
    if key.isupper() and len(key) < 4:
        return len(re.findall(r"(?<!\w)" + re.escape(key) + r"(?!\w)", prose))
    all_caps = key.isupper()  # an all-caps spelling may be the same name in either case
    if all_caps:  # a longer all-caps name may change case: «РОМАШКА» and «Ромашка» are one company
        key = _name_key(key.capitalize())
    lowered = prose.lower().replace("ё", "е")
    if re.search(r"[а-я]", key):
        # Each hyphen part inflects on its own: «Где-то», «Петрова-Водкина».
        stem = "-".join(re.escape(part) + CYRILLIC_INFLECTION for part in _stem(key).split("-"))
        pattern = re.compile(r"(?<!\w)" + stem + r"(?!\w)")
        # A Russian name is written capitalized; «романом» for «Роман» is a common noun, not the
        # person. Lowering keeps the length of Cyrillic and Latin letters, so the offset holds.
        return sum(1 for match in pattern.finditer(lowered)
                   if 0 <= match.start() < len(prose)
                   and (all_caps or prose[match.start()].isupper()))
    return len(re.findall(r"(?<!\w)" + re.escape(key) + r"(?:['’]s)?(?!\w)", lowered))


def _mentions(prose: str, key: str) -> bool:
    return _mention_count(prose, key) > 0


def _words(prose: str) -> set[str]:
    return {token.lower().replace("ё", "е") for token in TOKEN.findall(prose)}


def _prefixed_negation(prose: str, other: str) -> Counter[str]:
    """A Russian `не-` on a word the other side has without it: «незаконно» against «законно».

    Not every word that starts with «не» is a negation, so the unprefixed word must be present on
    the other side («небо» against «облако» stays clean)."""
    other_words = _words(other)
    found = sum(1 for token in TOKEN.findall(prose)
                if (word := token.lower().replace("ё", "е")).startswith("не") and len(word) > 2
                and word[2:] in other_words)
    return Counter({"не-": found}) if found else Counter()


def _quotations(text: str) -> Counter[str]:
    """Blockquotes with inclusive unmarked continuations, and inline quotations outside them.

    Unlike the strict gate, permissive preservation keeps lazy lines after quoted containers,
    inline quotations across block starts and numeric endings after sentence stops. It can
    include more than CommonMark quotes so a blocking decision cannot silently hide an edit.
    """
    scan = _lint.quote_scan(text)
    blocks: list[list[int]] = []
    for start, end in _lint._blockquote_ranges(scan, inclusive=True):
        if blocks and start <= blocks[-1][1]:
            blocks[-1][1] = max(blocks[-1][1], end)
        else:
            blocks.append([start, end])
    block_starts = [start for start, _ in blocks]
    inline: list[tuple[int, int]] = []
    reach = -1
    for start, end in sorted(set(_lint.quoted_ranges(scan, strict=False)), key=lambda item: (item[0], -item[1])):
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
        "date word": _date_words(prose),
        "link": links,
        "code": _code(text),
        "quotation": _quotations(text),
        "citation": citations,
        "qualifier": _lexicon_counts(words, QUALIFIERS),
        "modality": _lexicon_counts(words, MODALITY),
        "negation": _lexicon_counts(words, NEGATION),
        "first person": _lexicon_counts(_normalize_words(COUNTRY_US.sub(_blank, prose)), FIRST_PERSON),
        "speech act": _lexicon_counts(words, SPEECH_ACTS),
        "name": Counter(_names(PERCENT_AFTER_NUMBER.sub(_blank, prose))),
    }


def compare(source: str, edit: str) -> list[dict[str, object]]:
    """Findings as dicts: category, change ("lost" or "added"), item, source and edit counts."""
    before, after = profile(source), profile(edit)
    source_prose, edit_prose = _prose(source), _prose(edit)
    findings: list[dict[str, object]] = []
    for category, counts in before.items():
        other = after[category]
        if category == "negation":
            counts = counts + _prefixed_negation(source_prose, edit_prose)
            other = other + _prefixed_negation(edit_prose, source_prose)
        if category == "name":
            for key in sorted(counts):
                if not _mentions(edit_prose, key):
                    findings.append({"category": category, "change": "lost", "item": key,
                                     "source": _mention_count(source_prose, key), "edit": 0})
            for key in sorted(other):
                if not _mentions(source_prose, key):
                    findings.append({"category": category, "change": "added", "item": key,
                                     "source": 0, "edit": _mention_count(edit_prose, key)})
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
