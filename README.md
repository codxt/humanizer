# Humanizer

**Natural writing. Meaning preserved.**

Humanizer is an open-source agent skill for editing prose without changing its facts, commitments, conditions, deadlines, attribution, uncertainty, or the author's position.

It is designed for professional correspondence, customer replies, public copy, technical and policy writing, and long-form editing. It reduces recognizable AI-writing patterns while preserving meaningful register, terminology, quotations, and nuance.

## Why fidelity matters

A smoother rewrite can accidentally change a promise. "We're refunding" is not "We've refunded"; "may" is not "will"; acknowledging a complaint is not an admission of fault. Humanizer requires a **two-way source/output comparison** before consequential edits.

## Modes

- **Rewrite:** return natural prose, preserving all material meaning.
- **Audit / red pen:** identify patterns and propose targeted changes.
- **Final lint:** polish a nearly complete draft without new claims.

## Supported languages

- English
- Russian

These languages currently have dedicated editing guidance and regression examples. Additional languages can be added as corresponding guidance and tests are developed. See `references/language.md` for language-specific conventions and `references/work-fidelity.md` for work-writing protection.

## Install

**ChatGPT:** Download this repository as a ZIP, with the `SKILL.md` folder as the skill root, and upload it to your Skills library. The `agents/openai.yaml` metadata is provided for ChatGPT.

**Claude Code / Codex / other agents:** Put the repository contents in your agent's skills directory as `humanizer/`. The skill entrypoint is `SKILL.md`.

## Use

```text
Use humanizer to polish this customer reply while preserving every commitment and condition: ...
Audit this memo for AI patterns without changing its factual claims: ...
Run final prose lint on this report: ...
```

## Deterministic lint

The optional Python linter reports possible stylistic patterns; it never rewrites files and does **not** prove semantic fidelity.

```bash
python3 scripts/prose_lint.py draft.md
python3 -m unittest discover -s tests -v
```

Every push and pull request runs the test suite in GitHub Actions (`.github/workflows/tests.yml`).

For a CI gate, make only high-precision labels blocking and keep the rest as review candidates. `--fail-on LABEL` (repeatable) exits 1 when that label matches; `--github-annotations` adds GitHub Actions annotations. Two labels are meant for blocking: `assistant residue` (for example "as an AI language model", "hope this helps", "отличный вопрос") and `chatbot artifact` (chat-interface citation markup such as `contentReference[oaicite:1]` or `turn0search0`, and AI referral parameters such as `utm_source=chatgpt.com` in links). `placeholder text`, `corrective disclaimer`, and `procedural assurance` are review candidates. Text inside inline code spans, top-level fences and four-space indented code blocks is not scanned; a fence inside a blockquote is part of the blockquote. Unicode no-break, narrow no-break and thin spaces and zero-width joiners read as an ordinary space, and a residue phrase still matches when a line break splits it. The gate uses strict quotation detection. A match inside a closed quotation (straight, «», “”, „“, possibly across ordinary paragraph lines, but not across block-start lines) or a blockquote paragraph is reported as `[quoted]` and never blocks, so preserved quotations stay intact; the structural labels follow the same exemption. An unclosed quotation exempts nothing. `*`/`_` emphasis right next to the quote mark is looked past (`**"text"**`; `"text"**Bold** end` is not a quotation boundary), inline code inside a quotation does not hide its edge, and code outside it acts as a boundary. A line without `>` continues a blockquote only while its content ends in an open paragraph, so a thematic break (`---`, `***`, `___`), a quoted heading, a setext underline, a code fence, indented code or an empty `>` line ends the exemption. Once a line of the blockquote starts a list item, an HTML block or a link reference definition, no unmarked line after it is exempt (CommonMark would sometimes still quote it; the gate prefers to block when nested structure is involved). An unmarked line that starts an HTML block ends the quote, and `>` lines inside a top-level HTML block are not quotes. Inside a blockquote, marked HTML continuation lines also receive no blockquote exemption until the HTML end condition, a blank content line for blank-terminated HTML, or missing quote markers at the containing depth end that quoted HTML block; its marked opening line remains exempt. HTML types 1–5 (raw `script`/`pre`/`style`/`textarea`, comments, processing instructions, declarations and CDATA) run through their closing delimiter even across blank lines; other HTML-looking blocks run to a blank line. Tabs are expanded to four-column stops when judging blockquote content. `6"` never opens a quotation (it is an inch mark), but a straight quote right after a digit closes a candidate only when it contains no `.`, `!`, `?` or `…` outside code: `"version 2"` stays a quotation; an inch mark after a sentence stop discards the candidate so it cannot rescue a stray opener.

Known limits: quotation and block detection are conservative heuristics, not a complete CommonMark parser. The digit rule also blocks genuine multi-sentence quotations ending in a number (and numeric endings after abbreviations or decimals); an inch mark before any `.`, `!`, `?` or `…` can still close a stray opener. Block-start-looking lines can split a genuine quotation even when CommonMark would keep the paragraph open, and HTML-looking inline tags at the start of a line can end the blockquote exemption. The sticky container rule above intentionally blocks some valid lazy blockquote continuations. Code masking is not aware of HTML block state: a fence-looking line inside an HTML block can mask later residue even though CommonMark treats it as HTML text.

```bash
python3 scripts/prose_lint.py --github-annotations --fail-on "assistant residue" --fail-on "chatbot artifact" changed.md
```

## Mechanical fidelity check

`scripts/fidelity_check.py` compares a source with its edit and lists meaning-bearing items whose count changed: numbers with their sign and a following percent, temperature, time, or magnitude unit (the comma rule follows the script of each sentence, so `4 500`, `4,500` and `4500` count as equal in a Latin-script sentence while `1,500` is 1.5 in a Russian one; `30 days`, `30 weeks`, `30 business days` and `30 working hours` do not; time units run from milliseconds to years), numeric dates as ordered parts (`12.10.2026` and `10.12.2026` differ), currency (`£`, `GBP` and "45 pounds" count as equal, so a weight in pounds also reads as GBP), month and weekday names (English months count in either case except `March`, which stays capitalized so the verb is not a date; a capitalized Russian month form is a person's name unless a day number, a year or a preposition of time marks it as a date), relative dates, links and e-mail addresses (a balanced `(…)` inside a URL stays part of the link), fenced and inline code (indentation included; the fence language tag and backtick width are style; four-space indented code blocks are read as prose), quotations, bracketed citations, qualifiers (`at least`, `usually`, `если`, `не позднее`), modal verbs (`may`, `must`, `можем`, `обязаны`), negation (a free-standing word, and a Russian `не-` on a word the other side has without it), first-person words, apologies and thanks, and names.

```bash
python3 scripts/fidelity_check.py source.md edit.md
python3 scripts/fidelity_check.py --strict --json source.md edit.md
```

For quotation preservation, fidelity groups a blockquote with all unmarked lines up to a blank line or an unmarked heading/list/fence marker or thematic break, including continuations after quoted lists, HTML or link definitions. This inclusive grouping can compare more than CommonMark would quote; it deliberately avoids inheriting the gate's sticky-container blocking bias. The gate is strict; fidelity quotation detection is permissive. Fidelity keeps inline quotations across block-start lines within a nonblank run and accepts digit-adjacent closers even after sentence stops. It uses the shared detector with `strict=False`; the fidelity CLI's `--strict` option controls only whether findings cause exit 1. This permissive comparison can flag changes in text the gate would refuse to exempt.

A finding asks for a sentence-level comparison; removing a stacked hedge or a formulaic "not only" changes counts on purpose, and a date rewritten from digits to words (or back) shows up as a change. A clean result does not prove fidelity: the check cannot see tense or aspect ("refunding" vs "refunded"), an actor change without a pronoun, a condition moved to another clause, numbers swapped between objects ("5000 to Alice, 3000 to Bob" and the reverse), units other than percent, temperature, time, and magnitude (`500 g` and `500 kg` look the same), or a changed scope; it ignores numbers written as words; and it does not compare a name that only opens a sentence, a paragraph, a list item, or a heading, or that follows an abbreviation it does not know (it knows common English and Russian ones such as `Dr.`, `e.g.`, `U.S.`, `См.`, and initials). Russian names are compared as whole words, so only a common case ending may differ: Александр and Алексей are different people and so are Александр and Александров, while Петров and Петровым are one name. A mention must be capitalized, so «Роман» does not match «романом». Russian names inside «» are also compared as quotations, so an inflected company name shows up as a changed quotation. «Среда» counts as Wednesday only in day phrases («в среду», «в эту среду», «до среды», «по средам»), because it also means "environment"; «на среду» alone is not counted. Numeric versions such as `3.10.2` are compared under `date`. A hyphen after a number and a space reads as a range (`pages 10 -20`, `10 000 -20 000`) unless another number comes right before that one (`1 2 -20`, `2024, 500 -20`); then it is a minus sign, and so is an en or em dash in the same position (`–5 °C`), which a range guard keeps from reading `10–20` as a sign. A glued unit reads like its spaced form (`10s` = `10 s`, `10msecs` = `10 msecs`, `10hr` = `10 h`); lowercase `s`, `ms`, `h`, `d`, `w`, `y` and `ч` count as time units either way (uppercase `10 H` has no unit, while glued `10H` is hours); `k` and `m` mean a magnitude only when glued, in either case (`5m` and `4K`; `5 m` has no unit), `bn` counts glued or spaced, and a single glued `b` is not a billion (`5b` is an outline or question label). Only CR, LF, and CRLF end a line inside code, as in CommonMark: a fence after a form feed or U+2028/U+2029 on the same line is content, so the block stays open and the rest of the text is treated as code. The tokens `US` and `ME` are not counted as first-person words. English "May" counts as a modal verb, not a month, and `¥` is reported separately because it can mean yen or yuan. A space, no-break space, or narrow no-break space groups thousands (other Unicode spaces, such as a thin space, split the number); a comma groups thousands in a Latin-script sentence and is a decimal mark in a Cyrillic one, judged per sentence (`1,5 кг` = `1.5 кг`, and mixed text keeps each sentence's reading); a dot never groups thousands, so `1.500` and `1500` are reported as different. `2024 г.` counts as a year, while `5 г` (grams) stays a bare number. `--strict` exits 1 on any finding; errors exit 2.

The included manual regression cases in `tests/fidelity_cases.json` cover semantic edge cases in the currently supported languages. Passing a style lint or model check does not guarantee legal correctness or authenticity.

## Human control

`scripts/human_control.py` runs the linter over human writing from before ChatGPT: Wikipedia revisions saved before 30 November 2022, pinned by revision id in `tests/human_control.json`. It reports each label's matches per 1,000 words by language and exits 1 if a blocking label (`assistant residue`, `chatbot artifact`) fires outside a quotation in that human text. Run it before making a label blocking or adding a pattern. The rates are observations for this sample of rendered encyclopedic paragraphs; link destinations, lists and headings are dropped (anchor text stays; blockquotes stay blockquotes), so URL and structural labels are barely exercised, and words are counted as Unicode `\w+` runs. The script fetches each revision once through the Wikipedia API and caches its plain text in `~/.cache/humanizer-human-control`; the CC BY-SA article text never enters this repository. It needs network access, so CI does not run it; the unit tests cover it offline.

```bash
python3 -S scripts/human_control.py
python3 -S scripts/human_control.py --offline
python3 -S scripts/human_control.py --resolve en.wikipedia.org "Tea"
```

Humanizer edits for the reader, not for AI detectors, and does not claim that an edited draft will pass one. The detector-bypass prompt reviewed on 18 November 2026 tells a model to assemble text only from copied human sentences, apart from gaps the author fills in, which passes off other people's writing and cannot say what the author means; it was not adopted. See `references/research.md` → Review of 18 November 2026.

## Research and references

The [research and source references](references/research.md) document the Wikipedia editorial guides, open-source skills, and vendor publications reviewed for Humanizer, including how each was used and its evidence limits. These sources inform the editorial method; they do not establish AI authorship or guarantee semantic fidelity.

## Provenance and license

MIT licensed. Third-party attribution and license notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This repository is published as a standalone snapshot of the Codxt Humanizer skill; no private BRAIN history or operational materials are included.

Contributions and issue reports should include a minimal, synthetic before/after example and the precise meaning that must survive.
