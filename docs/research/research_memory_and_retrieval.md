# Research Memory And Retrieval

## Purpose

The Day 18 retrieval layer gives the research OS a disciplined memory surface over real persisted artifacts.

It does not simulate vague agent memory. It does not generate new evidence. It does not do semantic search.

It performs read-only discovery over stored artifacts and returns structured references to real files.

## What Is Searchable Today

The retrieval layer currently supports:

- `EvidenceSpan`
- `EvidenceAssessment`
- `Hypothesis`
- `CounterHypothesis`
- `ResearchBrief`
- `Memo`
- `Experiment`
- `ReviewNote`

Every returned result includes a `ResearchArtifactReference` with:

- the concrete artifact type
- the concrete artifact ID
- a real local `storage_uri`
- primary timestamp used for ranking and filtering
- canonical `company_id` when it resolves cleanly
- document lineage when it resolves cleanly
- provenance for the retrieval result itself

Evidence hits are returned separately as `EvidenceSearchResult` so the caller can distinguish quoted evidence from higher-level research artifacts.

## Retrieval Model

Retrieval is metadata-first plus deterministic substring matching.

Supported filters:

- `company_id`
- `document_kinds`
- `artifact_types`
- `time_start` and `time_end`
- exact-match `metadata_filters`
- case-insensitive `keyword_terms`

Supported exact metadata filters today:

- `status`
- `review_status`
- `validation_status`
- `stance`
- `grade`
- `audience`

Unsupported metadata filter keys are rejected explicitly. They do not silently no-op.

## Ranking And Matching

Filtering order is explicit:

1. scope
2. company
3. artifact type
4. document kind
5. time window
6. exact metadata filters
7. keyword filtering

Keyword behavior is intentionally simple:

- case-insensitive substring matching only
- explicit searchable fields per artifact type
- all keyword terms must match somewhere on the artifact
- no embeddings
- no fuzzy similarity
- no semantic fallback

Sorting rules:

- with keywords: matched-field count descending, then primary timestamp descending, then artifact ID ascending
- without keywords: primary timestamp descending, then artifact ID ascending

`semantic_retrieval_used` is always `False` in this version.

## Lineage Resolution Rules

The retrieval layer does not invent entity or document lineage. It derives it conservatively from stored artifacts.

- `Hypothesis`, `EvidenceAssessment`, and `ResearchBrief` use direct `company_id`
- `CounterHypothesis` derives company via its parent `Hypothesis`
- `Memo` derives company via `related_hypothesis_ids`, with a conservative fallback through `related_portfolio_proposal_id`
- `Experiment` derives company from linked hypotheses, then falls back to linked backtest runs when needed
- `ReviewNote` derives company from its review target
- `EvidenceSpan` derives company and document kind through `document_id -> Document`

Artifacts without clean document lineage are excluded by document-kind filters instead of being guessed into a bucket.

## Workflow Integration

The retrieval layer is advisory and read-only.

### Research workflow

`RunResearchWorkflowRequest` now supports `include_retrieval_context`.

When enabled, the workflow retrieves same-company prior work strictly older than the workflow start time and returns it as `retrieval_context` on the workflow response.

This context may include:

- evidence
- evidence assessments
- hypotheses
- counter-hypotheses
- research briefs
- memos
- experiments

The workflow does not auto-create new evidence links from retrieved artifacts.

### Memo flow

`MemoGenerationRequest` now accepts optional `retrieval_context`.

The memo service remains generation-only. It does not perform retrieval itself and it does not silently merge retrieved content into memo text.

When retrieval context is supplied, the memo provenance preserves the retrieved artifact IDs so later reviewers can see what prior work was available to the workflow.

### Operator review

`ReviewContext` now includes optional `related_prior_work`.

The operator review service populates this with same-company prior work relevant to the review target. This is intended to help an operator inspect prior memos, research artifacts, experiments, and review notes without treating them as approval evidence by default.

## Safety Boundary

This layer is not a semantic memory system.

It does not:

- infer hidden relevance
- compare embeddings
- summarize retrieved artifacts automatically
- alter support grades
- promote signals
- replace human review

Retrieval gives workflows and reviewers structured access to prior work. It does not grant that prior work new authority.

## Current Limitations

- No persistent index is stored. Searches scan local artifact roots on demand.
- Retrieval is not snapshot-aware yet.
- Ranking is mechanical, not quality-aware.
- Searchable fields are explicit and narrow.
- Retrieval currently depends on local filesystem artifact layout.

## Best Next Step

The next high-leverage extension is snapshot-aware retrieval.

The retrieval layer should eventually search against an explicit snapshot or artifact slice so that replay, research reuse, and downstream eligibility all operate on the same point-in-time boundary.
