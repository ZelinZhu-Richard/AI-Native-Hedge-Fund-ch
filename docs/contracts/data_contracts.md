# Data Contracts

## Purpose

These rules define the canonical semantics for data and derived artifacts in the research platform. The goal is reproducibility, temporal discipline, and traceability across future ingestion, research, backtesting, and paper-trading workflows.

## Canonical Entity IDs

All first-class entities use explicit prefixed IDs. Examples:

- `co_...` for `Company`
- `src_...` for `SourceReference`
- `doc_...` for `Document`
- `evd_...` for `EvidenceSpan`
- `hyp_...` for `Hypothesis`
- `sig_...` for `Signal`
- `idea_...` for `PositionIdea`
- `proposal_...` for `PortfolioProposal`
- `risk_...` for `RiskCheck`
- `trade_...` for `PaperTrade`
- `memo_...` for `Memo`
- `audit_...` for `AuditLog`
- `snap_...` for `DataSnapshot`

IDs should be immutable once assigned. Upstream vendor IDs may be stored separately, but they are not substitutes for canonical IDs.

## Timestamp Semantics

Every timestamp must be timezone-aware UTC at rest.

The canonical timestamp types are:

- `event_time`: when the real-world event happened
- `published_at`: when a source was made available upstream
- `retrieved_at` or `ingested_at`: when the platform first retrieved or registered the source
- `processing_time` or `processed_at`: when a transformation completed
- `effective_at`: when an artifact should be considered actionable for research or simulation
- `available_at`: when a feature or derived signal becomes legally and operationally available for downstream use
- `as_of_time`: the maximum information boundary for a decision or computation

When the true value is unknown, store `null` and document the uncertainty. Do not infer timestamps from convenience.

## Event Time vs Ingestion Time vs Processing Time

- Event time is a property of the world.
- Ingestion time is a property of our system boundary.
- Processing time is a property of our transformation pipeline.

These must not be conflated. A delayed source can have an old event time and a recent ingestion time. Backtests and feature computation must reason about both.

## Raw vs Normalized vs Derived Data

- Raw: unmodified payloads from upstream sources
- Normalized: cleaned or structured representations preserving source meaning
- Derived: hypotheses, features, signals, scores, proposals, and memos built from normalized inputs

Every artifact should declare its `DataLayer` or be inferable from its entity type.

## Provenance Requirements

Derived artifacts must include a provenance record containing, where applicable:

- direct source reference IDs
- upstream artifact IDs
- transformation name
- transformation version
- code version or commit SHA
- data snapshot ID
- ingestion time
- processing time

If provenance is incomplete, downstream consumers should degrade trust and may require human escalation.

## Evidence-Linking Rules

- Claims that refer to textual evidence must link to `EvidenceSpan`
- `EvidenceSpan` must link to `SourceReference`
- If a hypothesis or memo contains a substantive assertion with no evidence span, it must be marked as an assumption or open question
- Evidence excerpts should preserve offsets, page numbers, or speaker labels when available

## Versioning Rules

- Schema evolution must be explicit and additive when possible
- Breaking contract changes should be versioned and called out in docs
- Dataset snapshots should carry a dataset version and schema version
- Transformation versions should change whenever logic meaningfully changes

## Reproducibility Expectations

A future research artifact should be reproducible from:

- canonical input artifact IDs
- a data snapshot ID
- transformation or workflow version
- code version
- model or prompt version where AI was involved

Reproducibility does not require bit-for-bit deterministic language output on Day 1, but it does require enough metadata to explain how the artifact was produced.

## Future Dataset Partitioning Rules

Future partitioning should preserve point-in-time retrieval and auditability. Default partition concepts:

- source type
- source event date
- ingestion date
- normalized publish date
- company ID or universe bucket
- dataset version

Partition design should make it easy to reconstruct the exact information set visible at a historical cutoff.

## Future Backtesting Temporal Boundaries

Backtests must define:

- universe construction timestamp
- feature availability timestamp
- signal decision timestamp
- portfolio rebalance timestamp
- simulated execution timestamp
- evaluation window

Using event time alone is insufficient. Data availability delay must be respected.

## Leakage and Look-Ahead Avoidance

To avoid leakage:

- never use revised filings as if the revision were known earlier
- never use normalized artifacts whose processing completed after the decision boundary unless the delay is modeled explicitly
- never use future universe membership or survivorship-biased company sets
- never score signals with features that became available after the stated `as_of_time`
- never train on labels or post-event summaries unavailable at decision time

## Day 1 Contract Publication Strategy

Day 1 stores typed contracts in `libraries/schemas/`. Future machine-readable export formats should be published under `data_contracts/` so downstream services and external validation tooling can consume them without importing Python code directly.
