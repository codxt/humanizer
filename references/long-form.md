# Humanizer long-form structural audit

Load this reference for books, reports, doctrine, long articles, course compilations, and other multi-section documents where document geometry can remain model-shaped after sentence-level cleanup.

Review signals include:

- the same number of child sections repeated across many chapters without a source or genre reason;
- repeated paragraph counts or near-identical section lengths;
- recurring three-part decomposition imposed on unrelated topics;
- the same internal sequence, such as definition → example → implication → recap, repeated chapter after chapter;
- mirrored heading ladders added for visual balance rather than conceptual need;
- mechanically similar openings or endings;
- the same moral or summary after each example, including repeated contrasts split across paragraphs;
- regularity introduced during a rewrite even though the source is uneven.

Regular structure can be correct in specifications, checklists, legal forms, comparative reports, or deliberately parallel sources. Do not break symmetry merely to make prose look human. Restructure only when model/template pressure weakens the subject, source, or author's natural architecture.

Use the source's conceptual relationships to guide paragraph order. Keep distinct arguments, attribution, comparisons, sequence, and simultaneous events when merging or rearranging sections. Do not invent a causal link to make a fact list read like a narrative. Keep necessary methodology, source credits, disclosures, and evidence limits while removing redundant narration of the document's assembly.

For long-form work distinguish:

1. source/preflight contamination before drafting;
2. document-level architecture after a complete draft exists;
3. sentence/paragraph surface on the final semantic draft.

A material restructure, source-fidelity repair, merge/split, or argument reorder creates a new text state. Rerun Humanizer on the affected scope after semantic changes settle because the repair can introduce new symmetry, filler transitions, duplicated framing, or slogan rhythm. This is bounded revalidation, not permission for recursive polishing.

Optional report-only lint:

```text
python3 -S .agents/skills/humanizer/scripts/prose_lint.py <file>
```

The script flags candidate phrase clusters, formatting patterns, and simple Markdown heading-geometry regularity for review. A match is never automatic evidence of AI authorship and must not trigger blind replacement.
