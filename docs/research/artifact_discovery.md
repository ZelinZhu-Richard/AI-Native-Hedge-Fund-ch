# Artifact Discovery

## Purpose

Artifact discovery is the practical read path behind research memory.

It defines where the retrieval layer looks, what it loads, and how it turns stored JSON artifacts into structured search results.

This is a discovery layer, not a generation layer.

## Local Roots Searched Today

By default the retrieval service scans these workspace-relative roots:

- `ingestion/normalized/filings`
- `ingestion/normalized/earnings_calls`
- `ingestion/normalized/news_items`
- `parsing/evidence_spans`
- `research/evidence_assessments`
- `research/hypotheses`
- `research/counter_hypotheses`
- `research/research_briefs`
- `research/memos`
- `experiments/experiments`
- `review/review_notes`

It also reads supporting roots for lineage resolution:

- `signal_generation/signals`
- `portfolio/portfolio_proposals`
- `portfolio/paper_trades`
- `backtesting/runs`

These supporting roots are used to resolve company lineage for review notes and experiments. They are not first-class searchable scopes in Day 18.

## Searchable Artifact References

Each discovered artifact becomes one `ResearchArtifactReference`.

That reference records:

- the memory scope
- the concrete artifact type
- the concrete artifact ID
- a real local file URI
- company lineage when one company resolves cleanly
- document lineage when one document resolves cleanly
- the primary timestamp used for sorting and time filters

The reference is the retrieval layer's contract with downstream workflows. Callers should consume references, not infer filesystem structure themselves.

## Primary Timestamps

The retrieval layer uses one explicit primary timestamp per artifact type:

- `EvidenceSpan`: `captured_at`
- `EvidenceAssessment`: `created_at`
- `Hypothesis`: `created_at`
- `CounterHypothesis`: `created_at`
- `ResearchBrief`: `created_at`
- `Memo`: `generated_at`
- `Experiment`: `started_at`
- `ReviewNote`: `created_at`

This is what time-window filtering and default ordering operate on.

## Document Kind Resolution

Document-kind filtering is conservative.

- evidence spans resolve directly through `document_id`
- higher-level artifacts resolve document kind only when their evidence lineage collapses to one concrete document kind
- artifacts without a clean document lineage are excluded by a document-kind filter instead of being assigned one loosely

This keeps retrieval honest when research artifacts cite multiple documents or mixed document families.

## Citing Evidence

Evidence search results are special:

- the primary hit is always a stored `EvidenceSpan`
- the result also includes `citing_artifact_references`

Those citation references are built from persisted artifacts that explicitly cite the evidence span through stored supporting-evidence links.

This makes it possible to inspect both:

- the exact quote
- the higher-level artifacts that already relied on it

## What Discovery Does Not Do

Artifact discovery does not:

- parse raw documents on the fly
- infer missing provenance
- guess company lineage when linkage is ambiguous
- create semantic similarity links
- mutate stored artifacts

If an artifact cannot be linked cleanly, it remains searchable only on the metadata that can be established honestly.

## Safe Usage Guidance

Later workflows should use retrieval results as context, not authority.

Good uses:

- show prior same-company evidence to a new research run
- show prior memos and review notes to an operator
- inspect whether a claim has already been studied

Unsafe uses:

- promoting a signal because retrieval found many related artifacts
- auto-linking retrieved artifacts as new supporting evidence
- treating retrieval rank as confidence or truth

Discovery is useful because it is explicit, inspectable, and traceable. It is not a substitute for validation.
