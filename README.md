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

For a CI gate, make only high-precision labels blocking and keep the rest as review candidates. `--fail-on LABEL` (repeatable) exits 1 when that label matches; `--github-annotations` adds GitHub Actions annotations. Two labels are meant for blocking: `assistant residue` (for example "as an AI language model", "hope this helps", "отличный вопрос") and `chatbot artifact` (chat-interface citation markup such as `contentReference[oaicite:1]` or `turn0search0`, and AI referral parameters such as `utm_source=chatgpt.com` in links). `placeholder text`, `corrective disclaimer`, and `procedural assurance` are review candidates. Text inside code spans and fences is not scanned. A match inside a closed quotation (straight, «», “”, „“, possibly across lines within a paragraph) or a blockquote paragraph is reported as `[quoted]` and never blocks, so preserved quotations stay intact. An unclosed quotation exempts nothing, and `6"` counts as an inch mark, not a quote.

```bash
python3 scripts/prose_lint.py --github-annotations --fail-on "assistant residue" --fail-on "chatbot artifact" changed.md
```

## Mechanical fidelity check

`scripts/fidelity_check.py` compares a source with its edit and lists meaning-bearing items whose count changed: numbers with their sign and a following unit or magnitude (`4 500`, `4,500` and `4500` count as equal; `30 days` and `30 weeks` do not), numeric dates as ordered parts (`12.10.2026` and `10.12.2026` differ), currency (`£`, `GBP` and "45 pounds" count as equal), month and weekday names, relative dates, links and e-mail addresses, code (indentation included), quotations, bracketed citations, qualifiers (`at least`, `usually`, `если`, `не позднее`), modal verbs (`may`, `must`, `можем`, `обязаны`), negation, first-person words, apologies and thanks, and names.

```bash
python3 scripts/fidelity_check.py source.md edit.md
python3 scripts/fidelity_check.py --strict --json source.md edit.md
```

A finding asks for a sentence-level comparison; removing a stacked hedge or a formulaic "not only" changes counts on purpose, and a date rewritten from digits to words (or back) shows up as a change. A clean result does not prove fidelity: the check cannot see tense or aspect ("refunding" vs "refunded"), an actor change without a pronoun, a condition moved to another clause, or a changed scope; it ignores numbers written as words; and it does not compare a name that only opens a sentence, a paragraph, a list item, or a heading. Russian names are matched by stem, so names that differ only by an ending (Александр, Александров) count as one. Russian names inside «» are also compared as quotations, so an inflected company name shows up as a changed quotation. «Среда» counts as Wednesday only after a preposition that marks a day («в среду», «до среды»). English "May" counts as a modal verb, not a month, and `¥` is reported separately because it can mean yen or yuan. `--strict` exits 1 on any finding; errors exit 2.

The included manual regression cases in `tests/fidelity_cases.json` cover semantic edge cases in the currently supported languages. Passing a style lint or model check does not guarantee legal correctness or authenticity.

## Research and references

The [research and source references](references/research.md) document the Wikipedia editorial guides, open-source skills, and vendor publications reviewed for Humanizer, including how each was used and its evidence limits. These sources inform the editorial method; they do not establish AI authorship or guarantee semantic fidelity.

## Provenance and license

MIT licensed. Third-party attribution and license notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This repository is published as a standalone snapshot of the Codxt Humanizer skill; no private BRAIN history or operational materials are included.

Contributions and issue reports should include a minimal, synthetic before/after example and the precise meaning that must survive.
