# Proof Artifact Inventory

This inventory is a grounded map of what the repo can already prove through code, docs, tests, and interface surfaces. It is not a marketing list.

## Capability Anchors

These names are taken directly from `anhf capabilities --json` and anchor the inventory to the live interface surface:

- `ingestion`
- `parsing`
- `data_quality`
- `evaluation`
- `operator_review`
- `paper_ledger`
- `reporting`
- `signal_arbitration`
- `daily_workflow`
- `demo_end_to_end`

## Core Schemas

### Typed research, signal, and downstream artifact contracts

- Area or capability: typed research, signal, proposal, review, validation, reporting, and ledger contracts
- Strongest proof artifacts: `Hypothesis`, `EvidenceAssessment`, `Signal`, `PortfolioProposal`, `ValidationGate`, `ProposalScorecard`, `PaperPositionState`
- Key files/docs/tests: `libraries/schemas/research.py`, `libraries/schemas/portfolio.py`, `libraries/schemas/data_quality.py`, `libraries/schemas/reporting.py`, `libraries/schemas/paper_ledger.py`, `tests/unit/test_schemas.py`, `tests/unit/test_data_quality_schemas.py`, `tests/unit/test_reporting_schemas.py`
- Status: real
- Main caveat: strong typed contracts exist, but the full policy-driving downstream eligibility gate is still missing

## End-To-End Workflows

### Deterministic local demo and daily operating path

- Area or capability: end-to-end workflow wiring from fixtures to review-bound proposal and paper-trade surfaces
- Strongest proof artifacts: `demo manifest`, `final proof manifest`, `WorkflowExecution`, `RunSummary`, `PortfolioProposal`, `PaperPositionState`, `ReviewQueueItem`
- Key files/docs/tests: `pipelines/demo/end_to_end_demo.py`, `pipelines/demo/final_30_day_proof.py`, `pipelines/daily_operations/daily_workflow.py`, `docs/product/end_to_end_demo.md`, `docs/reviews/final_30_day_review.md`, `docs/architecture/daily_orchestration.md`, `tests/integration/test_end_to_end_demo.py`, `tests/integration/test_final_30_day_proof.py`, `tests/integration/test_daily_workflow.py`
- Status: real
- Main caveat: the workflows are honest local proofs, not production deployment paths, and the paper-ledger appendix still relies on explicit approvals and manual local lifecycle events

## Reproducibility Support

### Artifact roots, experiment registry, and explicit run context

- Area or capability: reproducible local runs with persisted artifacts, experiment recording, and explicit workflow context
- Strongest proof artifacts: `Experiment`, `ExperimentArtifact`, `DatasetReference`, `RunSummary`, deterministic local artifact roots
- Key files/docs/tests: `services/experiment_registry/service.py`, `libraries/schemas/base.py`, `libraries/core/local_artifacts.py`, `docs/research/experiment_registry.md`, `tests/unit/test_local_artifacts.py`, `tests/unit/test_experiment_registry_schemas.py`
- Status: real
- Main caveat: snapshot-native selection is still incomplete and persistence remains local-filesystem based

## Evaluation Support

### Structural evaluation, robustness checks, and red-team layers

- Area or capability: evaluation and adversarial inspection for research, signals, backtests, and proposals
- Strongest proof artifacts: `EvaluationReport`, `FailureCase`, `RobustnessCheck`, `RedTeamCase`, `GuardrailViolation`
- Key files/docs/tests: `services/evaluation/service.py`, `services/red_team/service.py`, `docs/research/evaluation_and_failure_analysis.md`, `docs/risk/red_team_and_guardrails.md`, `tests/unit/test_evaluation_service.py`, `tests/integration/test_red_team_suite.py`
- Status: partial
- Main caveat: evaluation is implemented, but it is not yet the hard downstream promotion policy

## Monitoring And Reporting

### Run summaries, health checks, alerts, and grounded reports

- Area or capability: operational visibility through monitoring artifacts and reporting scorecards
- Strongest proof artifacts: `RunSummary`, `HealthCheck`, `AlertRecord`, `ReviewQueueSummary`, `ExperimentScorecard`, `ProposalScorecard`, `DailySystemReport`
- Key files/docs/tests: `services/monitoring/service.py`, `services/reporting/service.py`, `docs/architecture/monitoring_and_health.md`, `docs/product/reporting_and_scorecards.md`, `tests/unit/test_monitoring_service.py`, `tests/unit/test_reporting_service.py`
- Status: real
- Main caveat: the reporting layer is grounded and useful, but still local and not yet policy-driving

## Review Workflow

### Review queue, context loading, assignments, notes, and decisions

- Area or capability: explicit human review workflow for research, signals, proposals, and paper trades
- Strongest proof artifacts: `ReviewQueueItem`, `ReviewContext`, `ReviewDecision`, `ReviewNote`, audit-linked review actions
- Key files/docs/tests: `services/operator_review/service.py`, `libraries/schemas/review.py`, `docs/product/operator_review_workflow.md`, `tests/unit/test_operator_review_workflow.py`, `tests/integration/test_operator_review_pipeline.py`, `tests/integration/test_api.py`
- Status: real
- Main caveat: review is coherent, but some readiness policy remains softer than it should be

## Paper-Trading And Ledger Support

### Approval-gated paper trades, ledger states, lifecycle events, and outcomes

- Area or capability: paper-trade candidate generation plus post-approval ledger and outcome tracking
- Strongest proof artifacts: `PaperTrade`, `PaperLedgerEntry`, `PaperPositionState`, `TradeOutcome`, `OutcomeAttribution`, `DailyPaperSummary`
- Key files/docs/tests: `services/paper_execution/service.py`, `services/paper_ledger/service.py`, `docs/risk/paper_trading_workflow.md`, `docs/risk/paper_ledger_and_outcomes.md`, `tests/unit/test_paper_ledger_schemas.py`, `tests/integration/test_paper_ledger_workflow.py`
- Status: real
- Main caveat: this is still paper-only bookkeeping with manual lifecycle inputs and no broker or live fill model

## Demo And Interface Entrypoints

### Unified CLI, local API, and honest workflow entrypoints

- Area or capability: local inspection and workflow invocation through CLI and API
- Strongest proof artifacts: `ServiceManifest`, `CapabilityDescriptor`, `DemoRunResult`, `WorkflowInvocationResult`
- Key files/docs/tests: `apps/cli/main.py`, `apps/api/main.py`, `libraries/schemas/interface.py`, `docs/product/api_and_interface_contracts.md`, `docs/product/demo_usability.md`, `tests/integration/test_cli.py`, `tests/integration/test_api.py`
- Status: real
- Main caveat: the interface layer is clean for local use, but not a production multi-user control plane

## Key Docs

### Architecture and operating docs that explain the current system honestly

- Area or capability: high-signal documentation for architecture, research discipline, risk flow, and interfaces
- Strongest proof artifacts: explicit docs on timing, validation, construction, paper ledger, reporting, and interfaces
- Key files/docs/tests: `AGENTS.md`, `PLAN.md`, `docs/reviews/week3_review.md`, `docs/reviews/final_30_day_review.md`, `docs/reviews/final_external_readiness_review.md`, `docs/research/temporal_correctness.md`, `docs/risk/portfolio_construction_v2.md`, `docs/product/api_and_interface_contracts.md`
- Status: real
- Main caveat: the docs are strong on internal structure, but still describe a local platform rather than a production deployment

## Key Tests

### Integration and unit tests that prove the system is more than a narrative

- Area or capability: tests that exercise service boundaries, workflow wiring, interface contracts, and artifact correctness
- Strongest proof artifacts: CLI/API smoke coverage, end-to-end workflow coverage, point-in-time checks, proposal and ledger workflow tests
- Key files/docs/tests: `tests/integration/test_end_to_end_demo.py`, `tests/integration/test_daily_workflow.py`, `tests/integration/test_point_in_time_availability.py`, `tests/integration/test_portfolio_review_pipeline.py`, `tests/integration/test_paper_ledger_workflow.py`, `tests/unit/test_interface_schemas.py`, `tests/unit/test_reporting_service.py`
- Status: real
- Main caveat: the test surface is meaningful, but it still validates a local research OS rather than production infrastructure
