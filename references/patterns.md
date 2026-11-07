# Humanizer prose-pattern reference

Load this reference for substantive rewrite, red-pen review, or final prose lint when AI-pattern cleanup is required.

Treat individual words and constructions as signals, not bans. Rewrite when patterns accumulate or materially weaken the text.

Prioritize structural problems over vocabulary: repeated setup, an invented objection, a decorative contrast, or a closer that duplicates the point. A single word, transition, dash, short sentence, formal register, or unsourced passage does not establish AI authorship. Edit for a concrete reader benefit; do not chase a detector score or make deliberate human writing uniformly plain.

## Concrete language

For public, client, commercial, website, proposal, and explanatory prose, ask whether the reader can identify the actor, action, object, practical change, and visible result. Replace hidden abstraction with concrete business language when the source supports it.

Professional shorthand such as `outcome`, `operating condition`, `capability`, `workflow`, `operating model`, `transformation`, `mandate`, `surface`, `context`, or `owner dependency` may be valid internally but normally needs unpacking for buyers.

Customer-facing repeat-back test: could a normal buyer explain the sentence to a colleague without first learning our terminology?

Say what a thing does rather than how it feels. `The database stays close at hand` names a feeling; `a column rename fails the build` names the mechanism. If a sentence cannot be restated as a concrete instruction, fact, or number, or could appear unchanged in another project's documents, it says nothing about this one: make it specific from the source or cut it.

Review abstract metaphor nouns that sound technical but hide a plainer word: `substrate`, `locus`, `nexus`, `bedrock`, `north star`, `flywheel`, `wedge`, `vantage`, and `scaffolding`, `harness`, or `ratchet` used as metaphors. Keep a term when the target document defines it or uses it as accepted terminology.

## Empty framing and chatbot residue

Remove generic scene-setting, reassurance, announcements, summaries, sign-offs, and service phrases that add no information. Keep an author's actual apology, thanks, request, invitation, or relational closing when it carries their intended stance or purpose. Do not add one to make the text warmer. Examples of removable framing include `Here's the thing`, `Let's dive in`, `Hope this helps`, `After careful consideration`, `It is important to note`, `The real question is`, and `At its core` when they perform no real function.

## Machine artifacts

Remove chat-interface leftovers that reached the document: citation markup (`contentReference[oaicite:1]`, `turn0search0`, `[cite: 2]`, `【3†source】`, `grok_card`), AI referral parameters in links (`utm_source=chatgpt.com`, `utm_source=openai`, `utm_source=copilot.com`, `referrer=grok.com`; drop only that parameter and keep the rest of the URL), unfilled placeholders (`INSERT_SOURCE_URL`, `[Company Name]`, `[Название компании]`, `2026-xx-xx`, `example.com/source1`), and instructions addressed to the chat user (`Would you like me to…`, `Delete this section before submission`, `Хотите, я подготовлю…`). A referral parameter shows that a chatbot found the link, not that it wrote the sentence. Markup leaks and unfilled placeholders mean the surrounding claims were never checked against a source: trace them before keeping them.

## Inflated vocabulary and significance

Review clusters built around decorative terms such as `delve`, `crucial`, `pivotal`, `foundational`, `tapestry`, `robust`, `seamless`, `landscape`, `realm`, `vibrant`, `groundbreaking`, or `transformative`. Keep them only when precise.

Cut unsupported claims that something is a turning point, broader trend, major shift, new era, strategic milestone, or proof of commitment.

## Formulaic contrast and manufactured rhythm

Reduce repeated `not X, but Y`, `not just X`, `not only X`, and similar rhetorical contrast when the distinction itself is not necessary.

Check the same pattern across sentences and paragraphs, including `не X, а Y`, `дело не в X`, and negative tails. Keep both halves when they distinguish real alternatives, correct a documented misconception, or preserve a boundary the reader needs. Remove an imagined objection only when no material claim is lost; preserve an actual refusal or disagreement.

Rewrite stacked slogan sentences, pseudo-profound punchlines, forced groups of three, decorative symmetry, repeated paragraph openings, and adverb-heavy mood-setting. Vary rhythm according to subject rather than template.

Review one-line morals after examples (`That distinction matters`, `В этом и заключается главное`) and theatrical candor (`Honestly?`, `Давайте начистоту`). Keep a short line when it adds a fact, consequence, or intentional author emphasis. Keep every distinct item in a genuine three-part list; changing rhythm must not remove a rank, comparison, sequence, or claim that events happened together.

## Template structure

Remove headings that only restate the next sentence, mechanical bold-label lists, decorative arrows when prose is clearer, and canned `Challenges`, `Opportunities`, `Key takeaways`, or `Conclusion` sections added only to complete an outline. Keep structure when it improves navigation, comparison, auditability, or source fidelity.

## Writing for the actual reader

For a reply with supplied conversation context, put the answer, decision, or request where the recipient can find it. Shorten repeated background when the user asked for a concise reply or the context makes that repetition dispensable. Keep new evidence, conditions, deadlines, and any explanation needed to assess the decision. A standalone email or document may need context that a thread reply does not. Do not infer what the reader knows from the genre alone or drop material source claims during an ordinary rewrite.

## Over-compression

Write whole sentences with their articles and verbs. Dropped articles, verbless fragments, arrows, symbol-speak, and private abbreviations make the reader decode instead of read: `Parser rejects bad date → exit 2, no write` becomes `The parser rejects a bad date, exits with code 2, and writes nothing.` Tables, logs, commit subjects, identifiers, and established shorthand of the genre may stay compact. In Russian, the same applies to telegraphic noun chains and dash-linked fragments.

## Text about its own preparation

Remove redundant narration of assembly, layout, or editing (`the table below compares`, `этот раздел организован по темам`) when the result is already visible. Preserve methodology, provenance, disclosure, evidence limits, version changes, and conventions the reader needs. A dated or source-scoped statement can be essential: `not verified`, `as of 9 October`, and `в доступных источниках не найдено` must not become certainty or disappear as chatbot residue. Reporting limits does not justify adding a plausible explanation.

## Evidence limits and corrective disclaimers

A real evidence limit belongs once, plainly, at the claim it qualifies, with its basis: `The 2019 registry extract lists him as director; no later extract was found.` Keep it wherever a reader would otherwise take the claim as broader, newer, or more certain than the source supports.

Cut generic advice about how to read the information when the limit is already stated or no claim depends on it: `should be treated as X rather than Y`, `does not by itself establish`, `based on available information`, `while specific details are limited`, `следует рассматривать как X, а не Y`, `само по себе не доказывает`, `на основе доступной информации`. Wikipedia's AI cleanup editors list these corrective framings among the most common signs of text generated since mid-2026. Never fill a gap with what the missing fact probably is (`keeps a low profile`, `likely reflects`). Add `should not be confused with` only when a reader could plausibly confuse the two.

## Authority, uncertainty, and abstraction

Do not write `experts say`, `research shows`, `observers note`, or similar authority claims without task-supplied or verified support. Do not replace `unknown` with a plausible explanation or inference with fact.

Repeat the correct noun when precision benefits from repetition. Do not cycle synonyms merely to avoid repetition. Prefer concrete verbs to nominalizations and abstract helper verbs when the source supports a named actor.

Name a relationship only to the precision the source supports. `Associated with the board` / `связан с советом директоров` does not establish membership. Retain a vague material relationship when no specific one is supplied. Keep idioms, mixed feelings, genuine asides, and natural variation when they carry the author's meaning or voice.

## Change reports

Commit messages, PR descriptions, changelogs, log entries, edit summaries, and audit reports say what changed in the content: `Added the 2019 directorship and its registry extract`, not `Revised the section to improve clarity and ensure accuracy while preserving the original meaning`. When a rule motivated the change, name it specifically (`per AGENTS.md → Placement`) instead of appealing to guidelines, neutrality, or quality in general.

Mention something left unchanged only when a reader would otherwise expect it to change, or when it is a checkable fact (`raw transcript hash verified`, `50 entries kept; the oldest moved unchanged`). Remove general assurances that an edit complied with, improved, enhanced, or preserved something; Wikipedia editors treat them as a strong sign of generated edit summaries. Keep what a reviewer needs: tests and commands run, counts, hashes, and open limits.

## Source calibration

Reviewed on 2026-10-09: [blader/humanizer 3.1.0](https://github.com/blader/humanizer/blob/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8/SKILL.md), [work-humanizer](https://github.com/phuryn/work-humanizer/blob/819ac9925fffc20f12931cdf7a447db69163cbb2/skills/work-humanizer/SKILL.md), and Wikipedia's [English](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) and [Russian](https://ru.wikipedia.org/w/index.php?title=Википедия:Признаки_сгенерированности_текста&oldid=155487940) essays. These are sources of editorial candidates, not authority to override this skill's fidelity rules. Wikipedia-specific conventions do not automatically apply to work writing; historical indicators and surface style cannot establish authorship.

Reviewed on 2026-11-01: rules 26, 27, and 33 of Lauren Tan's [pstack `unslop` skill](https://github.com/cursor/plugins/blob/c742dd61706fbacc1b95f1a20b7b988cf096ce6c/pstack/skills/unslop/SKILL.md) (MIT) informed the concrete-language, abstract-noun, and over-compression guidance. Its other rules were already covered here; its absolute bans (no em dashes, no colons mid-sentence) were not adopted, because this skill treats single signals as candidates rather than bans.

Reviewed on 2026-11-07: WikiProject AI Cleanup, its [guide](https://en.wikipedia.org/w/index.php?title=Wikipedia:WikiProject_AI_Cleanup/Guide_and_resources&oldid=1383438332) and [Signs of AI writing](https://en.wikipedia.org/w/index.php?title=Wikipedia:Signs_of_AI_writing&oldid=1384165696) informed the machine-artifact, evidence-limit, and change-report guidance; the editing contract and the mechanical check follow ideas from avoid-ai-writing, its Russian port, humanizer-ru, and sepia. Pinned revisions, measurements, and what was deferred or rejected are in `references/research.md` of the codxt/humanizer repository.

Emulate's [public API documentation](https://www.tryemulate.ai/docs/api) and [research note](https://www.tryemulate.ai/research/mode-collapse) were reviewed as vendor descriptions, not as an inspectable skill or independently verified behavior. No hosted service, detector, proprietary model, or paid API is required here.
