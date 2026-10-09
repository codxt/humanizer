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

The included manual regression cases in `tests/fidelity_cases.json` cover semantic edge cases in the currently supported languages. Passing a style lint or model check does not guarantee legal correctness or authenticity.

## Research and references

The [research and source references](references/research.md) document the Wikipedia editorial guides, open-source skills, and vendor publications reviewed for Humanizer, including how each was used and its evidence limits. These sources inform the editorial method; they do not establish AI authorship or guarantee semantic fidelity.

## Provenance and license

MIT licensed. Third-party attribution and license notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This repository is published as a standalone snapshot of the Codxt Humanizer skill; no private BRAIN history or operational materials are included.

Contributions and issue reports should include a minimal, synthetic before/after example and the precise meaning that must survive.
