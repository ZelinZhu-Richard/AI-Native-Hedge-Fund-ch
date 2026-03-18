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
- `chyp_...` for `CounterHypothesis`
- `sel_...` for `SupportingEvidenceLink`
- `eass_...` for `EvidenceAssessment`
- `rbrief_...` for `ResearchBrief`
- `fdef_...` for `FeatureDefinition`
- `fval_...` for `FeatureValue`
- `feat_...` for `Feature`
- `flin_...` for `FeatureLineage`
- `sscore_...` for `SignalScore`
- `sig_...` for `Signal`
- `slin_...` for `SignalLineage`
- `idea_...` for `PositionIdea`
- `proposal_...` for `PortfolioProposal`
- `risk_...` for `RiskCheck`
- `trade_...` for `PaperTrade`
- `memo_...` for `Memo`
- `audit_...` for `AuditLog`
- `snap_...` for `DataSnapshot`
- `pxmeta_...` for `PriceSeriesMetadata`
- `store_...` for `ArtifactStorageLocation`
- `pdoc_...` for `ParsedDocumentText`
- `seg_...` for `DocumentSegment`
- `claim_...` for `ExtractedClaim`
- `rfact_...` for `ExtractedRiskFactor`
- `gchg_...` for `GuidanceChange`
- `tone_...` for `ToneMarker`

IDs should be immutable once assigned. Upstream vendor IDs may be stored separately, but they are not substitutes for canonical IDs.

Current Day 2 ID rules:

- `Company.company_id` uses CIK when available, otherwise stable identity parts such as ticker, legal name, and country of risk
- `SourceReference.source_reference_id` is deterministic from source type plus upstream identity and URI
- `Document.document_id` is deterministic from document kind plus source reference and upstream document identity
- `PriceSeriesMetadata.price_series_metadata_id` is deterministic from company, dataset name, and symbol

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

Schemas reject naive datetimes at validation time so timezone assumptions are explicit rather than implicit.

Current ingestion rule:

- raw fixture files preserve the original serialized timestamp strings
- normalized canonical objects convert timestamp fields to UTC at rest

## Event Time vs Ingestion Time vs Processing Time

- Event time is a property of the world.
- Ingestion time is a property of our system boundary.
- Processing time is a property of our transformation pipeline.

These must not be conflated. A delayed source can have an old event time and a recent ingestion time. Backtests and feature computation must reason about both.

Current ingestion examples:

- `Filing.filing_date` is not a substitute for `SourceReference.retrieved_at`
- `EarningsCall.call_datetime` is event time, while transcript publication time is a separate source timestamp
- company metadata may have `as_of_time` that is earlier than fixture ingestion time

Current parsing examples:

- `ParsedDocumentText` is the canonical text coordinate space for extraction offsets
- `DocumentSegment` and `EvidenceSpan` offsets are relative to that canonical text, not segment-local text
- extracted claims and other evidence-derived artifacts inherit source availability from the upstream document and span lineage

## Raw vs Normalized vs Derived Data

- Raw: unmodified payloads from upstream sources
- Normalized: cleaned or structured representations preserving source meaning
- Derived: hypotheses, critiques, evidence assessments, research briefs, features, signals, scores, proposals, and memos built from normalized inputs

Every artifact should declare its `DataLayer` or be inferable from its entity type.

Repository layout should respect the same split:

- raw machine inputs belong under `storage/raw/`
- normalized machine-readable documents belong under `storage/normalized/`
- derived machine-readable artifacts belong under `storage/derived/`
- human-facing review bundles belong under `research_artifacts/`

## Runtime Materialization vs Storage Conventions

Week 1 uses three different top-level concepts:

- `artifacts/`: the current local runtime materialization root used by deterministic workflows and tests
- `storage/`: future durable dataset-layout and storage conventions
- `research_artifacts/`: future review-bundle conventions for human-facing packages

Current runtime writes should be interpreted as the local source of truth for generated outputs. `storage/` and `research_artifacts/` remain specification layers, not the active runtime write path.

Current local ingestion runs materialize under `artifacts/ingestion/` using the same layered split:

- `artifacts/ingestion/raw/` for exact fixture payload copies
- `artifacts/ingestion/normalized/` for canonical typed outputs

Current Day 5 feature and signal runs materialize under `artifacts/signal_generation/`:

- `feature_definitions/`
- `feature_values/`
- `features/`
- `signal_scores/`
- `signals/`

Current Day 6 and Day 7 runs materialize under:

- `artifacts/backtesting/`
- `artifacts/portfolio/`
- `artifacts/audit/`

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

Current normalization also records:

- transformation name
- configuration version hooks
- fixture path notes for local replay and debugging

If provenance is incomplete, downstream consumers should degrade trust and may require human escalation.

## Evidence-Linking Rules

- Claims that refer to textual evidence must link to `EvidenceSpan`
- `EvidenceSpan` must link to `SourceReference`
- parser-emitted `EvidenceSpan` should also link to a concrete `DocumentSegment` when exact segment regions exist
- `Hypothesis`, `CounterHypothesis`, and `ResearchBrief` should cite textual support through `SupportingEvidenceLink`
- If a hypothesis, critique, or memo contains a substantive assertion with no evidence span, it must be marked as an assumption, open question, or missing evidence
- Evidence excerpts should preserve offsets, page numbers, or speaker labels when available

## Versioning Rules

- Schema evolution must be explicit and additive when possible
- Breaking contract changes should be versioned and called out in docs
- Dataset snapshots should carry a dataset version and schema version
- Dataset manifests should exist once a dataset spans multiple storage locations or partitions
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

When future storage metadata becomes concrete, `DatasetManifest`, `DatasetPartition`, and storage location records should be the machine-readable source of truth for how datasets are materialized.

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

Current ingestion-specific guardrails:

- do not replace source publication time with local ingestion time
- do not use filing period end dates as if they were publication timestamps
- do not collapse transcript event time and transcript availability time
- do not treat company reference-data `as_of_time` as equivalent to retrieval time

## Day 1 Contract Publication Strategy

Day 1 stores typed contracts in `libraries/schemas/`. Future machine-readable export formats should be published under `data_contracts/` so downstream services and external validation tooling can consume them without importing Python code directly.
