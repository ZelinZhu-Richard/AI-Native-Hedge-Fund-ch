# Work Log

This file is the rolling build log for the repository.

It should be updated at the end of each meaningful workday or phase checkpoint so the project history stays in the repo, not only in chat history.

## Status Legend

- `Completed`: implemented and validated in the repo
- `In Progress`: partially implemented or recently refined
- `Planned`: next target, not implemented yet

## Day 1: Foundation And Architecture

Status: `Completed`

### Goal

Create the Day 1 repo foundation for a serious AI-native hedge fund research OS.

### Plan Focus

- disciplined monorepo structure
- typed schema foundation
- service boundaries and stubs
- local FastAPI app
- quality tooling
- architecture, risk, eval, and contract documentation

### Implemented

- monorepo scaffold across `apps/`, `services/`, `agents/`, `libraries/`, `pipelines/`, `docs/`, and `tests/`
- core Pydantic schema layer for documents, evidence, research, portfolio, risk, audit, and system metadata
- service stubs for ingestion, parsing, orchestration, features, signals, risk, portfolio, paper execution, memo, and audit
- API boot surface under `apps/api`
- local dev tooling with `ruff`, `mypy`, `pytest`, `pre-commit`, `.env.example`, and `Makefile`
- architecture, data-contract, risk, and eval docs

### Key Decisions

- no live trading path
- paper-trading-first safety posture
- provenance and explicit time handling as first-class design requirements
- service boundaries favored over convenience coupling

### Carry-Forward

- real ingestion and normalized artifacts
- document intelligence on top of those normalized artifacts

## Day 2: Ingestion And Normalization

Status: `Completed`

### Goal

Build the first trustworthy local ingestion and normalization backbone.

### Plan Focus

- fixture-backed source loaders
- canonical IDs
- source and document timestamp handling
- raw vs normalized storage separation
- company and source-reference normalization

### Implemented

- local ingestion foundation for SEC filings, transcripts, news, company metadata, and price-series metadata placeholders
- sample fixtures under `tests/fixtures/ingestion/`
- canonical object normalization into `SourceReference`, `Company`, `Filing`, `EarningsCall`, `NewsItem`, and `PriceSeriesMetadata`
- file-backed artifact persistence under `artifacts/ingestion/raw/` and `artifacts/ingestion/normalized/`
- timestamp parsing and normalization utilities
- fixture and normalization tests

### Key Decisions

- local fixture flow first, no provider integrations yet
- preserve source identifiers, publication times, retrieval times, and ingestion times explicitly
- keep raw and normalized layers physically separate

### Carry-Forward

- convert normalized text into parser-owned evidence artifacts

## Day 3: Document Intelligence And Evidence Extraction

Status: `Completed`

### Goal

Turn normalized source artifacts into exact-span evidence that later workflows can trust.

### Plan Focus

- parser-owned text artifacts
- document segmentation
- structured extraction
- provenance-preserving exact evidence spans
- lightweight extraction evals

### Implemented

- parser-owned `ParsedDocumentText` and `DocumentSegment`
- exact `EvidenceSpan` with canonical offsets and segment linkage
- structured extraction for `ExtractedClaim`, `ExtractedRiskFactor`, `GuidanceChange`, and `ToneMarker`
- deterministic segmentation for filings, transcripts, and news
- evidence-bundle eval hooks
- file-backed parsing artifacts under `artifacts/parsing/`
- fixture-based segmentation and extraction tests

### Key Decisions

- no summarizer layer
- extraction stays modest and exact-span grounded
- parser output remains downstream of normalized documents and upstream of research artifacts

### Carry-Forward

- hypothesis generation and critique should consume persisted parsing artifacts, not raw documents

## Day 4: Research Workflow Foundation

Status: `Completed`

### Goal

Build the first disciplined research workflow on top of the evidence layer.

### Plan Focus

- evidence-backed hypotheses
- structured critiques
- support grading
- memo-ready research artifacts
- deterministic workflow orchestration

### Implemented

- research-layer schemas for `Hypothesis`, `CounterHypothesis`, `SupportingEvidenceLink`, `EvidenceAssessment`, and `ResearchBrief`
- deterministic workflow components for thesis generation, evidence grading, critique, and brief construction
- `ResearchOrchestrationService.run_research_workflow()`
- local daily research pipeline entrypoint
- draft memo skeleton generation from `ResearchBrief`
- persisted research artifacts under `artifacts/research/`
- schema, workflow, and end-to-end integration tests

### Key Decisions

- deterministic workflow first, no model-backed generation yet
- `ResearchBrief` is the primary Day 4 review artifact
- `Memo` remains a render target, not the system of record for research logic
- hypotheses do not become signals directly

### Carry-Forward

- formal review and validation gate before any feature mapping

## Day 4 Refinement: Validation Lifecycle Separation

Status: `Completed`

### Goal

Tighten the existing research workflow so human review status and validation status are separate concepts.

### Plan Focus

- explicit validation lifecycle
- schema contract refinement
- memo skeleton visibility of lifecycle state
- docs and tests aligned to the refined workflow

### Implemented

- added `ResearchValidationStatus`
- added `validation_status` to `Hypothesis`, `CounterHypothesis`, `EvidenceAssessment`, and `ResearchBrief`
- set deterministic defaults:
  - `Hypothesis.validation_status = unvalidated`
  - `CounterHypothesis.validation_status = unvalidated`
  - `EvidenceAssessment.validation_status = pending_validation` for `strong` and `moderate`, otherwise `unvalidated`
  - `ResearchBrief.validation_status` mirrors the hypothesis
- updated memo skeleton output to surface both review status and validation status
- expanded schema and workflow tests to assert validation-state behavior
- updated research and agent docs to distinguish review from validation

### Key Decisions

- review status answers whether a human has accepted or blocked the artifact
- validation status answers whether the thesis or critique has actually been tested or invalidated by later work
- these remain separate lifecycles

### Current Sample Output

- hypothesis review status: `pending_human_review`
- hypothesis validation status: `unvalidated`
- evidence assessment grade: `strong`
- evidence assessment validation status: `pending_validation`

## Day 5: Feature And Candidate Signal Pipeline

Status: `Completed`

### Goal

Convert structured research artifacts into typed candidate features and candidate signals without pretending those signals are already validated or portfolio-ready.

### Plan Focus

- refine feature and signal contracts
- preserve exact lineage from research artifacts into candidate features
- build deterministic feature mapping from the Day 4 research slice
- build deterministic candidate signal generation with conservative confidence
- establish ablation hooks without faking non-text baselines

### Implemented

- added `FeatureDefinition`, `FeatureValue`, `FeatureLineage`, `SignalLineage`, `FeatureFamily`, `AblationView`, and `DerivedArtifactValidationStatus`
- upgraded `Feature`, `SignalScore`, and `Signal` into provenance-aware Day 5 artifacts
- replaced `Signal.direction` with `Signal.stance` so signals remain non-portfolio-facing
- built `FeatureStoreService.run_feature_mapping_workflow()` for deterministic Day 5 feature generation
- built `SignalGenerationService.run_signal_generation_workflow()` for deterministic candidate signal generation
- added local artifact persistence under `artifacts/signal_generation/`
- added the end-to-end `pipelines/signal_generation/run_feature_signal_pipeline()`
- added schema, workflow, and integration tests for the new feature and signal layer

### Key Decisions

- candidate feature generation is allowed before the formal review gate exists, but outputs remain provisional and unvalidated
- only `text_only` is populated on Day 5; price, fundamentals, and macro remain future family hooks
- Day 5 scoring is deterministic and explicitly non-empirical
- signals remain candidate research artifacts, not position instructions

### Carry-Forward

- temporally honest candidate-signal evaluation
- ablation infrastructure
- explicit promotion gate before any portfolio or paper-trading work

## Day 6: Honest Backtesting And Simulation Skeleton

Status: `Completed`

### Goal

Build the first explicit backtesting and simulation boundary with strong temporal discipline.

### Plan Focus

- explicit backtest configuration and execution assumptions
- point-in-time snapshots for signals and prices
- deterministic unit-position decisioning
- next-bar execution with transaction-cost and slippage placeholders
- mechanical benchmarks and persisted simulation artifacts

### Implemented

- refined backtesting contracts with `BacktestConfig`, `ExecutionAssumption`, `StrategyDecision`, `SimulationEvent`, `PerformanceSummary`, and `BenchmarkReference`
- expanded `BacktestRun` to carry config, snapshot, benchmark, and temporal-hygiene metadata
- added `DataSnapshot.information_cutoff_time` and validation
- built a deterministic local backtesting workflow under `services/backtesting/`
- added synthetic daily price fixture support for mechanical end-to-end tests
- persisted exploratory backtest artifacts under `artifacts/backtesting/`
- added unit and integration tests for schema validity, feature-availability gating, execution lag, transaction-cost handling, reproducibility, and benchmark output
- added architecture and temporal-correctness docs for the new boundary

### Key Decisions

- candidate Day 5 signals are allowed as explicit dev-only inputs, but every run is marked `exploratory_only`
- the first engine is daily-bar, one-company-at-a-time, and unit-position only
- fills occur at next-bar open only
- benchmarks are mechanical baselines, not investment claims
- synthetic prices are test infrastructure only and clearly labeled as such

### Carry-Forward

- richer signal-evaluation artifacts
- ablation-aware replay
- explicit promotion gate from exploratory artifacts into reviewed validation work

## Day 7: Signal Evaluation And Promotion Gate

Status: `Planned`

### Goal

Build the first reviewed signal-evaluation and promotion workflow on top of the Day 6 exploratory backtest boundary.

### Planned Focus

- typed signal-evaluation artifacts
- snapshot-aware replay checks
- ablation coverage across future signal slices
- explicit promotion guardrails before portfolio logic or paper execution

## Maintenance Rule

When future work is completed:

1. add a new dated or day-numbered section here
2. mark whether the work is `Completed`, `In Progress`, or `Planned`
3. summarize the plan focus, implemented result, key decisions, and carry-forward
4. keep this log concise and cumulative rather than rewriting past sections
