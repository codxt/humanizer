# Research and source references

This bibliography records the external material reviewed for the Humanizer update of **9 October 2026**. It distinguishes editorial observations, other skill implementations, self-reported evaluations, and vendor descriptions. The references inform the skill; they do not override its source-fidelity rules.

The linked articles and upstream projects remain on their respective websites. This repository does not republish their full texts, source files, or research data.

## Wikipedia editorial guides

### 1. Wikipedia: Signs of AI writing

- **Source:** [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
- **Type:** Community-maintained field guide and advice page, not Wikipedia policy or a peer-reviewed detector study.
- **Used for:** Candidate patterns in inflated importance claims, promotional framing, vague attribution, repeated rhetorical structures, outline-style closers, vocabulary, headings, and markup.
- **Limit:** The examples are primarily drawn from Wikipedia editing. A pattern appearing in a document is not proof that it was written by AI, and Wikipedia-specific formatting preferences do not automatically apply to other genres.

### 2. Википедия:Признаки сгенерированности текста

- **Source:** [Russian Wikipedia essay](https://ru.wikipedia.org/wiki/Википедия:Признаки_сгенерированности_текста); [revision referenced in the original review](https://ru.wikipedia.org/w/index.php?title=Википедия:Признаки_сгенерированности_текста&oldid=155487940)
- **Type:** Community essay on observed patterns in AI-assisted Wikipedia writing, not a general writing standard.
- **Used for:** Russian-language examples involving inflated claims, repeated formulae, weak attribution, overregular structure, decorative phrasing, and editorial context.
- **Limit:** The guidance is observational and Wikipedia-specific. It does not justify banning normal Russian punctuation, genuine contrasts, or sentences that preserve the author's intended meaning.

## Open-source skills and published evaluations

### 3. blader/humanizer, version 3.1.0

- **Source:** [blader/humanizer](https://github.com/blader/humanizer); [SKILL.md at reviewed commit 225a6f3](https://github.com/blader/humanizer/blob/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8/SKILL.md)
- **Type:** Open-source agent skill (MIT).
- **Used for:** Cross-checking candidate AI-writing patterns, including vocabulary inflation, mechanical contrasts, repetitive transitions, and document formatting.
- **Limit:** Pattern matching is an editorial aid, not a universal prohibition or reliable measure of authorship. The upstream skill is a reference, not a dependency.

### 4. phuryn/work-humanizer

- **Source:** [phuryn/work-humanizer](https://github.com/phuryn/work-humanizer); [SKILL.md at reviewed commit 819ac99](https://github.com/phuryn/work-humanizer/blob/819ac9925fffc20f12931cdf7a447db69163cbb2/skills/work-humanizer/SKILL.md); [published evaluation and methodology](https://github.com/phuryn/work-humanizer#what-the-test-found)
- **Type:** Open-source agent skill (MIT) with author-published evaluations.
- **Used for:** Challenging whether a natural-sounding rewrite preserves facts and commitments, including action status, deadlines, exceptions, goodwill offers, apologies, and the author's position. The published examples informed the decision to treat work-text fidelity as a separate explicit check.
- **Limit:** Benchmark comparisons and preference judgments are reported by that project's author; they are not independently validated performance guarantees for Humanizer or for arbitrary documents.

## Vendor publications

### 5. Emulate: Why AI writing all sounds the same

- **Source:** [Emulate research note on writing uniformity](https://www.tryemulate.ai/research/mode-collapse) (published 25 September 2026).
- **Type:** Vendor-authored explanatory research note, not an independent experimental validation of Humanizer.
- **Used for:** Considering repetitive rhythm, generic voice, and structurally homogeneous writing as editorial problems rather than merely replacing individual words.
- **Limit:** The vendor's conceptual explanation and product claims were not adopted as verified causal findings or detector-performance claims.

### 6. Emulate API documentation

- **Source:** [Emulate API documentation](https://www.tryemulate.ai/docs/api)
- **Type:** First-party product and API documentation.
- **Used for:** Understanding the distinction between hosted rewriting services and a local, instruction-based agent skill.
- **Limit:** API descriptions are vendor-maintained and can change. Humanizer does not call or require Emulate, any detector, or any paid rewriting service.

## What was carried into Humanizer

- **Editorial candidates:** Identify clusters of repeated scaffolding, overclaiming, canned transitions, decorative contrast, and unnecessary narration while preserving meaningful structure and native usage. See [patterns.md](patterns.md) and [language.md](language.md).
- **Fidelity controls:** Compare source and edit in both directions, protecting actors, commitments, status, conditionality, deadlines, attribution, uncertainty, and stance. See [work-fidelity.md](work-fidelity.md).
- **Verification:** The deterministic linter reports possible style issues; it cannot prove that meaning was preserved. The repository includes **12 automated linter tests** and **12 manual semantic regression cases**, which are bounded checks, not a universal fidelity or legal-safety certification.

## Use and attribution

These sources are acknowledged to make the editorial basis inspectable. They are not a mandate to copy another author's phrasing, imitate a specific voice without permission, erase legitimate signals of uncertainty, or optimize for AI-detector scores.

For the open-source projects' copyright and MIT notices, see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Wikipedia material is linked for reference rather than reproduced.
