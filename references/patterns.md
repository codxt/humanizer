# Humanizer prose-pattern reference

Load this reference for substantive rewrite, red-pen review, or final prose lint when AI-pattern cleanup is required.

Treat individual words and constructions as signals, not bans. Rewrite when patterns accumulate or materially weaken the text.

Prioritize structural problems over vocabulary: repeated setup, an invented objection, a decorative contrast, or a closer that duplicates the point. A single word, transition, dash, short sentence, formal register, or unsourced passage does not establish AI authorship. Edit for a concrete reader benefit; do not chase a detector score or make deliberate human writing uniformly plain.

## Concrete language

For public, client, commercial, website, proposal, and explanatory prose, ask whether the reader can identify the actor, action, object, practical change, and visible result. Replace hidden abstraction with concrete business language when the source supports it.

Professional shorthand such as `outcome`, `operating condition`, `capability`, `workflow`, `operating model`, `transformation`, `mandate`, `surface`, `context`, or `owner dependency` may be valid internally but normally needs unpacking for buyers.

Customer-facing repeat-back test: could a normal buyer explain the sentence to a colleague without first learning our terminology?

## Empty framing and chatbot residue

Remove generic scene-setting, reassurance, announcements, summaries, sign-offs, and service phrases that add no information. Keep an author's actual apology, thanks, request, invitation, or relational closing when it carries their intended stance or purpose. Do not add one to make the text warmer. Examples of removable framing include `Here's the thing`, `Let's dive in`, `Hope this helps`, `After careful consideration`, `It is important to note`, `The real question is`, and `At its core` when they perform no real function.

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

## Text about its own preparation

Remove redundant narration of assembly, layout, or editing (`the table below compares`, `этот раздел организован по темам`) when the result is already visible. Preserve methodology, provenance, disclosure, evidence limits, version changes, and conventions the reader needs. A dated or source-scoped statement can be essential: `not verified`, `as of 9 October`, and `в доступных источниках не найдено` must not become certainty or disappear as chatbot residue. Reporting limits does not justify adding a plausible explanation.

## Authority, uncertainty, and abstraction

Do not write `experts say`, `research shows`, `observers note`, or similar authority claims without task-supplied or verified support. Do not replace `unknown` with a plausible explanation or inference with fact.

Repeat the correct noun when precision benefits from repetition. Do not cycle synonyms merely to avoid repetition. Prefer concrete verbs to nominalizations and abstract helper verbs when the source supports a named actor.

Name a relationship only to the precision the source supports. `Associated with the board` / `связан с советом директоров` does not establish membership. Retain a vague material relationship when no specific one is supplied. Keep idioms, mixed feelings, genuine asides, and natural variation when they carry the author's meaning or voice.

## Source calibration

Reviewed on 2026-10-09: [blader/humanizer 3.1.0](https://github.com/blader/humanizer/blob/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8/SKILL.md), [work-humanizer](https://github.com/phuryn/work-humanizer/blob/819ac9925fffc20f12931cdf7a447db69163cbb2/skills/work-humanizer/SKILL.md), and Wikipedia's [English](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) and [Russian](https://ru.wikipedia.org/w/index.php?title=Википедия:Признаки_сгенерированности_текста&oldid=155487940) essays. These are sources of editorial candidates, not authority to override this skill's fidelity rules. Wikipedia-specific conventions do not automatically apply to work writing; historical indicators and surface style cannot establish authorship.

Emulate's [public API documentation](https://www.tryemulate.ai/docs/api) and [research note](https://www.tryemulate.ai/research/mode-collapse) were reviewed as vendor descriptions, not as an inspectable skill or independently verified behavior. No hosted service, detector, proprietary model, or paid API is required here.
