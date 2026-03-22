# Day 18 Plan

## Goal

Build the first disciplined research memory layer for the research OS.

The objective is not to simulate agent memory. The objective is to let workflows and operators retrieve real prior work through explicit artifact references, exact filters, and preserved provenance.

## What Was Added

### Schemas

The retrieval contract now includes:

- `MemoryScope`
- `ResearchArtifactReference`
- `RetrievalQuery`
- `RetrievalResult`
- `EvidenceSearchResult`
- `RetrievalContext`

These contracts make result scope, artifact type, timestamps, storage location, and provenance explicit.

### Service

`ResearchMemoryService` now provides metadata-first retrieval over persisted local artifacts.

It scans real workspace roots on demand and builds an in-memory catalog for:

- evidence spans
- evidence assessments
- hypotheses
- counter-hypotheses
- research briefs
- memos
- experiments
- review notes

### Workflow integration

The retrieval layer now integrates into:

- research workflow responses as advisory `retrieval_context`
- memo generation provenance through retrieved artifact IDs
- operator review context as advisory `related_prior_work`

## What Retrieval Means Today

Retrieval is:

- metadata-first
- deterministic
- read-only
- advisory

Retrieval is not:

- semantic search
- vector retrieval
- similarity ranking
- auto evidence reuse
- promotion logic

`semantic_retrieval_used` is always `False` in the current implementation.

## Ranking And Filtering

Filtering is explicit and ordered:

1. scope
2. company
3. artifact type
4. document kind
5. time window
6. exact metadata filters
7. keyword filtering

Keyword search is case-insensitive substring matching over explicit artifact fields only.

## Strengths

- Retrieval results point to real stored artifact files.
- Evidence hits stay separate from higher-level research artifacts.
- Company and document lineage are resolved conservatively.
- Operator review and research workflows can inspect prior work without mutating the underlying artifacts.

## Weaknesses

- No persistent index yet
- No snapshot-aware retrieval boundary yet
- No semantic retrieval
- Ranking is mechanical, not learned
- Search still depends on local artifact layout

## Verification Added

The implementation is covered by:

- schema validation tests
- synthetic retrieval service tests over persisted artifacts
- integration coverage showing:
  - research workflow carries advisory retrieval context
  - memo provenance records retrieved artifact IDs
  - operator review context includes related prior work

## Best Next Target

The next best target is snapshot-aware retrieval.

The retrieval layer should operate against an explicit point-in-time artifact slice so that research reuse, replay, and downstream eligibility share the same selection boundary instead of scanning the latest local artifacts.
