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
- **Verification:** The deterministic linter reports possible style issues; it cannot prove that meaning was preserved. The mechanical fidelity check (added 7 November 2026) compares meaning-bearing items between source and edit; it cannot see tense, aspect, moved conditions, or actor changes without a pronoun. The repository includes **117 automated tests** (47 for the linter, 70 for the fidelity check) and **12 manual semantic regression cases**, which are bounded checks, not a universal fidelity or legal-safety certification.

## Use and attribution

These sources are acknowledged to make the editorial basis inspectable. They are not a mandate to copy another author's phrasing, imitate a specific voice without permission, erase legitimate signals of uncertainty, or optimize for AI-detector scores.

For the open-source projects' copyright and MIT notices, see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Wikipedia material is linked for reference rather than reproduced.

## Engineering-rigor skills

### 7. Lauren Tan, pstack `unslop` skill

- **Source:** [cursor/plugins pstack `unslop` at commit c742dd6](https://github.com/cursor/plugins/blob/c742dd61706fbacc1b95f1a20b7b988cf096ce6c/pstack/skills/unslop/SKILL.md), reviewed 1 November 2026.
- **Type:** Open-source agent skill (MIT) inside an engineering-rigor plugin.
- **Used for:** Rules 26 (abstract metaphor nouns), 27 (say what it does, not how it feels), and 33 (over-compression), adapted into `references/patterns.md`, and a report-only lint category for a few abstract nouns.
- **Limit:** The upstream rules are an author's style list, not an evaluated detector. Its absolute bans on em dashes and mid-sentence colons were not adopted.

## Review of 7 November 2026

This review covered WikiProject AI Cleanup and fifteen other writing-cleanup projects. Each source was read at the pinned revision below. Stars, benchmarks, and claims made by these projects decided what was worth reading; they are not evidence for Humanizer.

### Wikipedia sources

| Page | Revision | Used for |
|---|---|---|
| [WikiProject AI Cleanup](https://en.wikipedia.org/w/index.php?title=Wikipedia:WikiProject_AI_Cleanup&oldid=1383956021) | 1383956021 | Project goals; signs are symptoms of unverified content, not the problem to fix |
| [Guide and resources](https://en.wikipedia.org/w/index.php?title=Wikipedia:WikiProject_AI_Cleanup/Guide_and_resources&oldid=1383438332) | 1383438332 | Source checking is the most reliable test; signs combine probabilistically; as of August 2026 many listed signs are outdated for recent models |
| [Signs of AI writing](https://en.wikipedia.org/w/index.php?title=Wikipedia:Signs_of_AI_writing&oldid=1384165696) | 1384165696 | Citation-markup leaks, AI referral parameters, placeholders, mid-2026 corrective disclaimers, procedural edit summaries, signs of human writing, ineffective indicators, dated vocabulary eras |
| [Signs of AI use in comments](https://en.wikipedia.org/w/index.php?title=Wikipedia:Signs_of_AI_use_in_comments&oldid=1384071329) | 1384071329 | Correspondence signs (deferred) |
| [Writing articles with large language models](https://en.wikipedia.org/w/index.php?title=Wikipedia:Writing_articles_with_large_language_models&oldid=1384147012) | 1384147012 | English Wikipedia policy context for a later encyclopedic mode |
| [LLM-assisted translation](https://en.wikipedia.org/w/index.php?title=Wikipedia:LLM-assisted_translation&oldid=1382711327) | 1382711327 | Same |
| [Википедия:Нейросеть](https://ru.wikipedia.org/w/index.php?title=Википедия:Нейросеть&oldid=152348305) | 152348305 | Russian Wikipedia policy context for a later encyclopedic mode |

Policy context, as read on 7 November 2026: English Wikipedia's content guideline prohibits using an LLM to generate or rewrite article text, except for spelling and grammar suggestions on the editor's own writing and for reviewed translation from another Wikipedia whose source article is not LLM-generated. Russian Wikipedia's guideline allows LLM-assisted text that the editor fully checks against the rules before publishing and takes full responsibility for, recommends disclosure in the main namespace, and requires it in discussions. Wikimedia's Terms of Use require disclosure of paid contributions on every project.

### Writing-cleanup projects

| Project | Commit | License | Ideas taken or considered |
|---|---|---|---|
| [conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing/tree/30971f1c50c6412a0c414e8c7b15032a32b21939) | 30971f1 | MIT | Editing contract (candidate → finding → edit), clean no-op, preservation validator, hash-only human-control corpus, self-scan budgets, ignore markers |
| [ormeilu/avoid-ai-writing-russian](https://github.com/ormeilu/avoid-ai-writing-russian/tree/a4a862aef0ef894bd6ef089cfea926da5d8bc41a) | a4a862a | MIT | `validate` for numbers, links, citations, quotations and hedges; Russian calques and context profiles |
| [ilyautov/humanizer-ru](https://github.com/ilyautov/humanizer-ru/tree/b6df5d9b87d47ca288cce3a02da007da33221626) | b6df5d9 | MIT | Fact check against the source (hedges kept, no new names or numbers); competitor review; measured rejection of an "overcorrection" detector |
| [Nanako0129/sepia](https://github.com/Nanako0129/sepia/tree/0eb11d6c64c962fcc35f596c167c6e38045d6cb8) | 0eb11d6 | MIT | Defect list before rewriting; deletion over addition; rhythm evidence review; domain passes for release notes, PR replies, and postmortems |
| [seyedehsanhadi/sloptrim](https://github.com/seyedehsanhadi/sloptrim/tree/9b3e2efe6ab64d9b60c214ad1213b2b30bbddb27) | 9b3e2ef | Apache-2.0 | Diff-anchored writing, prompt echo, model-family dialects, metronomic sentence alternation, passive-voice drift in both directions |
| [eric-tramel/slop-guard](https://github.com/eric-tramel/slop-guard/tree/7ef2113c52f1b4765287f90ac0741b2051d66fcb) | 7ef2113 | MIT | Rule thresholds fitted on public-domain human newspapers |
| [adewale/anti-slop-writing](https://github.com/adewale/anti-slop-writing/tree/70f9803b4c717a98c713706101638f2406105a40) | 70f9803 | MIT | Ablation before adopting a borrowed rule, held-out evaluation split, rejected-edits record |
| [ItsssssJack/SlopMonster](https://github.com/ItsssssJack/SlopMonster/tree/3fc9787d9337b57c599a80afbefbbb3be5a8eb0b) | 3fc9787 | MIT | Second pass by a different model family |
| [epoko77-ai/im-not-ai](https://github.com/epoko77-ai/im-not-ai/tree/b37e0206d31fffd9149bf57168d4d62eb2086bee) | b37e020 | MIT | Corpus study: model output vs pre-2022 human prose, log-likelihood per pattern, rejected rules recorded |
| [hardikpandya/stop-slop](https://github.com/hardikpandya/stop-slop/tree/8da1f030185bdfe8471220585162991eaeb970e9) | 8da1f03 | MIT | False agency; its blanket bans were not adopted |
| [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop/tree/000650b156983f5159695b441477f4e63b25dc85) | 000650b | MIT | Proportional cutting; "would the writer recognize it" final check |
| [EveryInc/compound-writing](https://github.com/EveryInc/compound-writing/tree/8fd0ec88c00976cf0274cb76552dc7ad9405ca92) | 8fd0ec8 | none stated | Structural overcompletion (idea only; no text used) |
| [ilien-dev/quiron](https://github.com/ilien-dev/quiron/tree/9bedfd53438b25085d5b420945358e1c0bf4d317) | 9bedfd5 | AGPL-3.0 | Weekly upstream intake gated by own measurement (idea only; no code used) |
| [blader/humanizer](https://github.com/blader/humanizer/tree/0ef9fe5bc3572734fd3ae6c448fe00a30cd5dcf0) | 0ef9fe5 | MIT | No content change since the reviewed 3.1.0 |
| [phuryn/work-humanizer](https://github.com/phuryn/work-humanizer/tree/0a9065791d021f3dda695f3887cb2ae4c0eacbcf) | 0a90657 | MIT | One new brief-to-email experiment; no skill change |

The pstack `unslop` skill had no change after the 1 November review. No upstream text or code was copied; the rules and scripts here are written for Humanizer.

### Measurement

The editors of *Signs of AI writing* highlight the AI phrases in their examples. Run over the 880 highlighted phrases at revision 1384165696, the linter before this change flagged 14, and 10 of the 347 phrases relevant outside Wikipedia. After it, the counts are 26 and 14; most highlighted phrases are vocabulary or fragments that the linter does not target. On the full text of the page and its markup subpage, all 86 `chatbot artifact` and `placeholder text` matches were artifacts the page documents; none was ordinary prose.

### Adopted in this change

- The editing contract and clean no-op in `SKILL.md`.
- `scripts/fidelity_check.py`, a mechanical source/edit comparison, and its pointer in `SKILL.md`.
- Linter labels `chatbot artifact` (high precision, suitable for blocking), `placeholder text`, `corrective disclaimer`, and `procedural assurance`, with new `chatbot residue` phrases.
- `references/patterns.md` sections on machine artifacts, evidence limits and corrective disclaimers, and change reports.

### Deferred

Human-control corpus and self-scan budgets; dated vocabulary by model generation; structural overcompletion; rhythm checks for runs of similar sentence lengths and metronomic alternation; new patterns (diff-anchored writing, prompt echo, model-family dialects, Russian calques); genre profiles; correspondence signs; domain passes; a second pass by a different model family; an encyclopedic mode for Wikipedia and knowledge pages.

### Not adopted

Lowering scores from AI detectors or plagiarism systems; blanket bans on adverbs, passive voice, or dashes; numeric self-scores; deliberately added roughness or errors; code or text from projects without a compatible license.
