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

## Day 7: Portfolio Proposal And Paper-Trade Review Flow

Status: `Completed`

### Goal

Build the first risk-aware downstream proposal layer on top of the current signal and backtesting foundation.

### Plan Focus

- signal-to-position mapping
- inspectable portfolio proposals
- explicit risk checks
- paper-trade candidate creation
- human review hooks with no live execution path

### Implemented

- refined `PositionIdea`, `PortfolioProposal`, `RiskCheck`, `ReviewDecision`, and `PaperTrade`
- added `PortfolioExposureSummary`
- added shared review-transition helpers for position ideas, proposals, and paper trades
- built deterministic portfolio loaders, construction logic, local artifact storage, and `PortfolioConstructionService.run_portfolio_workflow()`
- built explicit Day 7 risk rules under `services/risk_engine/`
- refined `PaperExecutionService` to consume full `PortfolioProposal` objects and emit paper-only trade candidates
- added `pipelines/portfolio/run_portfolio_review_pipeline()`
- persisted Day 7 artifacts under `artifacts/portfolio/`
- added schema, workflow, and end-to-end integration tests
- updated agent spec and Day 7 risk docs

### Key Decisions

- candidate signals may enter Day 7 proposals, but they remain visibly provisional and trigger warnings
- blocking risk checks cannot be silently bypassed
- proposal approval and paper-trade approval remain separate states
- no broker path or live execution path exists in the Day 7 flow

### Carry-Forward

- reviewed signal-evaluation and promotion gates
- trade-level review workflow
- richer multi-name portfolio constraints and holdings-aware turnover logic

## Week 1 Review

Status: `Completed`

### Goal

Review the full Day 1 through Day 7 foundation as one system before Week 2 work begins.

### Plan Focus

- schema consistency and lifecycle clarity
- lineage completeness from evidence to paper-trade candidate
- temporal correctness across downstream proposal layers
- explicit separation between candidate and validated artifacts
- remaining review, validation, and risk-control gaps

### Implemented

- reviewed the full Week 1 stack against `AGENTS.md` and `PLAN.md`
- added explicit `as_of_time` cutoffs to feature, signal, and portfolio workflows
- made local audit persistence operational and wired audit events into major workflows
- replaced placeholder API listing endpoints with artifact-backed inspection reads
- clarified the meaning of `artifacts/`, `storage/`, and `research_artifacts/`
- updated stale docs and metadata to match the actual Week 1 repo state

### Key Decisions

- fix honesty gaps before adding new capability
- keep latest-artifact loading only as an explicit local-dev convenience
- defer instrument mastering, duplication cleanup, and trade-level approvals rather than patching them badly

### Carry-Forward

- explicit snapshot selection across the research-to-portfolio chain
- real review-state persistence and promotion gates
- first-class instrument/reference contracts
- harder adversarial replay tests

## Day 8: Experiment Registry And Dataset Snapshot Spine

Status: `Completed`

### Goal

Add the reproducibility spine so workflow outputs are tied to explicit config, dataset references, artifacts, and metrics.

### Plan Focus

- experiment registry foundation
- dataset manifest and snapshot-reference metadata
- reproducible run recording
- first workflow integration through backtesting

### Implemented

- added a local `experiment_registry` service and storage path under `artifacts/experiments/`
- exported the full experiment-registry and dataset-reference contract surface through `libraries/schemas`
- integrated the Day 6 backtesting workflow with:
  - `ExperimentConfig`
  - `RunContext`
  - `DatasetManifest`
  - `DatasetPartition`
  - `SourceVersion`
  - `DatasetReference`
  - `Experiment`
  - `ExperimentArtifact`
  - `ExperimentMetric`
- refined backtest snapshot metadata to carry `event_time_start`, `ingestion_cutoff_time`, and `source_families`
- added schema, workflow, and integration tests for reproducible experiment recording
- added Day 8 docs for experiment registry and dataset snapshot policy

### Key Decisions

- `DataSnapshot` remains owned by the producing workflow; the experiment registry references snapshots instead of duplicating them
- backtesting is the first integrated workflow because it already has explicit config and deterministic outputs
- registry storage stays metadata-first and local-filesystem-backed for now

### Carry-Forward

- snapshot-aware experiment recording for feature mapping and signal generation
- explicit artifact selection rather than cutoff-only loading
- promotion gates between exploratory and validated experiment runs

## Day 9: Baseline Strategy And Ablation Harness

Status: `Completed`

### Goal

Build an honest baseline strategy and ablation framework so text-derived candidate signals can be compared against simple alternatives instead of drifting into ungrounded complexity.

### Plan Focus

- comparable strategy contracts
- deterministic baseline variants
- shared evaluation slices and source snapshots
- child variant backtests plus parent ablation experiment recording
- structured comparison results with no fake “winner” language

### Implemented

- added `StrategySpec`, `StrategyVariant`, `StrategyVariantSignal`, `EvaluationSlice`, `AblationConfig`, `AblationVariantResult`, and `AblationResult`
- kept research `Signal` intact and introduced `StrategyVariantSignal` as the evaluation-layer comparable signal boundary
- built deterministic Day 9 variants for:
  - naive hold-cash baseline
  - price-only 3-bar momentum
  - text-only candidate adaptation
  - combined 50/50 text-plus-price baseline
- extended the backtest workflow to accept comparable preloaded signals without weakening the existing research-signal path
- added a local ablation pipeline that:
  - materializes variant signals
  - persists ablation artifacts under `artifacts/ablation/`
  - runs child backtests for each variant
  - records child experiments
  - records one parent ablation experiment
  - emits one structured `AblationResult`
- added schema, workflow, and end-to-end integration tests for the ablation layer
- added Day 9 docs for the baseline framework and strategy variants

### Key Decisions

- do not overload the evidence-linked research `Signal` contract to represent naive or price-only baselines
- compare variants at the signal boundary through a separate `StrategyVariantSignal`
- keep ordering mechanical and explicit rather than implying validated strategy selection
- reuse the Day 6 backtest engine and Day 8 experiment registry instead of creating parallel evaluation stacks

### Carry-Forward

- reviewed signal-evaluation artifacts and promotion gates
- snapshot-native selection upstream of feature and signal generation
- downstream enforcement so portfolio and paper-trade flows can reject unreviewed exploratory signals

## Day 10: Evaluation, Failure Analysis, And Robustness Layer

Status: `Completed`

### Goal

Build the first explicit evaluation layer that records structural quality, visible failures, and robustness checks instead of relying on loose summary prose.

### Plan Focus

- typed evaluation artifacts
- structured failure recording
- deterministic robustness checks
- first concrete workflow integration
- docs that say clearly what is and is not being evaluated

### Implemented

- added `MetricValue`, `EvaluationMetric`, `FailureCase`, `RobustnessCheck`, `ComparisonSummary`, `CoverageSummary`, and `EvaluationReport`
- added `EvaluationService` plus local storage under `artifacts/evaluation/`
- implemented deterministic checks for:
  - provenance completeness
  - hypothesis support quality
  - feature lineage completeness
  - signal generation validity
  - backtest artifact completeness
  - strategy comparison output
  - risk review coverage
- implemented explicit robustness checks for:
  - missing data sensitivity
  - timestamp anomalies
  - source inconsistency
  - incomplete extraction artifacts
  - invalid strategy config combinations
- integrated the evaluation layer into the Day 9 ablation workflow
- added schema, evaluation-logic, workflow, and integration tests
- fixed an evaluation artifact persistence bug where generic ID resolution would have overwritten files across categories
- added Day 10 docs for evaluation and robustness checks

### Key Decisions

- evaluation is stored as its own artifact layer, not hidden inside experiment metadata
- failures and robustness results are first-class outputs, not only notes
- the first integrated target is the Day 9 ablation workflow, not the entire repo
- passing evaluation checks does not imply validated edge or signal promotion

### Carry-Forward

- reviewed signal-evaluation decisions
- promotion gates from exploratory to downstream-eligible artifacts
- snapshot-native selection for evaluation and downstream enforcement

## Day 11: Operator Review Workflow And Console Contract

Status: `Completed`

### Goal

Formalize the human operator workflow so research briefs, signals, portfolio proposals, and paper-trade candidates can be reviewed through one explicit contract instead of scattered domain-specific hooks.

### Plan Focus

- generic review-domain schemas
- persisted review queue, notes, assignments, and decisions
- console-ready derived review context
- explicit review actions and status transitions
- auditability for every review action

### Implemented

- added `libraries/schemas/review.py` with:
  - `ReviewTargetType`
  - `EscalationStatus`
  - `ReviewQueueStatus`
  - `ActionRecommendationSummary`
  - `ReviewNote`
  - `ReviewAssignment`
  - generic `ReviewDecision`
  - `ReviewQueueItem`
  - derived `ReviewContext`
- moved `ReviewDecision` out of the portfolio-only schema path and kept it exported through `libraries/schemas/__init__.py`
- added `services/operator_review/` with:
  - queue sync
  - queue listing
  - context assembly
  - note creation
  - assignment changes
  - review action application
- persisted review artifacts under `artifacts/review/`
- added operator-console API endpoints:
  - `GET /reviews/queue`
  - `GET /reviews/context/{target_type}/{target_id}`
  - `POST /reviews/notes`
  - `POST /reviews/assignments`
  - `POST /reviews/actions`
- extended audit artifacts with `status_before` and `status_after`
- routed the existing Day 7 portfolio review path through the generic operator review action flow
- added schema, service, API, and end-to-end integration tests for the review layer
- added Day 11 docs for operator workflow and console contract

### Key Decisions

- `ResearchBrief` remains the primary queued research review object
- `ReviewContext` is rebuilt on demand and is not persisted as a source-of-truth artifact
- no UI polish was added before the contract and audit path were explicit
- review state is now structurally real, but downstream gating is still the next step rather than being implied

### Carry-Forward

- reviewed-and-evaluated signal eligibility gates
- downstream enforcement for portfolio proposal and paper-trade eligibility
- snapshot-native input selection for stricter downstream workflows

## Day 12: Monitoring And Run-Summary Layer

Status: `Completed`

### Goal

Add a small but serious monitoring layer that makes key workflows inspectable without pretending the repo already has a full observability stack.

### Plan Focus

- operational monitoring contracts
- persisted run summaries
- local health and readiness checks
- explicit alert records
- API visibility for recent runs and failures

### Implemented

- extended `libraries/schemas/system.py` with:
  - `WorkflowStatus`
  - `HealthCheckStatus`
  - `PipelineEventType`
  - `AlertState`
  - `PipelineEvent`
  - `RunSummary`
  - `HealthCheck`
  - `AlertCondition`
  - `AlertRecord`
  - `ServiceStatus`
- added `services/monitoring/` with local storage under `artifacts/monitoring/`
- added monitoring integration for:
  - fixture ingestion
  - evidence extraction
  - strategy ablation
  - operator review actions
- added API endpoints for:
  - `GET /health/details`
  - `GET /monitoring/run-summaries/recent`
  - `GET /monitoring/failures/recent`
  - `GET /monitoring/services`
- added schema, service, API, and integration tests for the new monitoring layer
- added Day 12 monitoring and run-summary docs

### Key Decisions

- `RunSummary` is the primary monitoring artifact
- monitoring stays summary-oriented rather than becoming a noisy event stream
- `ServiceStatus` is derived on demand and not persisted
- health checks remain local and structural; there are no fake external dependency probes

### Carry-Forward

- operator-facing attention queues
- downstream enforcement based on reviewed, evaluated, and monitored state
- richer monitoring around stale workflows and blocked eligibility
- explicit snapshot selection tied into the monitoring surface

## Maintenance Rule

When future work is completed:

1. add a new dated or day-numbered section here
2. mark whether the work is `Completed`, `In Progress`, or `Planned`
3. summarize the plan focus, implemented result, key decisions, and carry-forward
4. keep this log concise and cumulative rather than rewriting past sections
