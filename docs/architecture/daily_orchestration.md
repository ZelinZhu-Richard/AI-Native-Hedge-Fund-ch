# Daily Orchestration

## Purpose

The current repo includes a local orchestration layer that turns the research stack into a repeatable daily operating path.

This layer is deliberately small and explicit:

- local only
- manual invocation only
- no cron integration
- no workflow engine
- no hidden approval bypasses

The goal is not production scheduling. The goal is consistent sequencing, inspectable step state, explicit stop conditions, and a durable operator runbook.

## Primary Artifacts

The orchestration layer persists under `artifacts/orchestration/`:

- `workflow_definitions/`
- `scheduled_run_configs/`
- `workflow_executions/`
- `run_steps/`
- `runbook_entries/`

The key artifacts are:

- `WorkflowDefinition`: code-owned ordered step definition for the daily run
- `ScheduledRunConfig`: local run configuration and root paths
- `WorkflowExecution`: parent execution record for one daily run
- `RunStep`: per-step execution state, retries, notes, produced artifact IDs, and manual stops
- `RunbookEntry`: operator-facing explanation of each step, expected outputs, checks, and failure triage

## Current Daily Step Order

The implemented daily workflow is fixed and explicit:

1. `fixture_refresh_and_normalization`
2. `evidence_extraction`
3. `research_workflow`
4. `feature_signal_pipeline`
5. `portfolio_workflow`
6. `review_queue_sync`
7. `paper_trade_candidate_generation`
8. `operations_summary`

Current behavior by step:

- `fixture_refresh_and_normalization`
  - runs `run_fixture_ingestion_pipeline()` when `data_refresh_mode=fixture_refresh`
  - otherwise records reuse of the existing ingestion root
- `evidence_extraction`
  - runs `run_evidence_extraction_pipeline()`
- `research_workflow`
  - runs `run_hypothesis_workflow_pipeline()`
  - defaults to memo skeleton generation and advisory retrieval context
- `feature_signal_pipeline`
  - runs feature mapping, signal generation, and signal arbitration
- `portfolio_workflow`
  - runs portfolio construction, attribution, stress testing, and risk checks
- `review_queue_sync`
  - refreshes review queue items from research, signal, and portfolio artifacts
- `paper_trade_candidate_generation`
  - attempts paper-trade candidate creation
  - preserves the explicit review gate when the parent proposal is not approved
- `operations_summary`
  - runs health checks and lists recent run summaries

## Retry And Failure Rules

The current retry and stop behavior is code-owned and persisted into each `RunStep`.

Retryable steps:

- `fixture_refresh_and_normalization`
  - one automatic in-process retry
  - second failure -> workflow `failed`
- `evidence_extraction`
  - one automatic in-process retry
  - second failure -> workflow `failed`
- `operations_summary`
  - one automatic in-process retry
  - second failure -> workflow `partial`

Non-retryable hard-fail steps:

- `research_workflow`
- `feature_signal_pipeline`
- `portfolio_workflow`

These fail the workflow immediately when they raise after their single attempt.

Attention-required stop behavior:

- `review_queue_sync`
  - failure stops the workflow in `attention_required`
- `paper_trade_candidate_generation`
  - a non-approved proposal is not treated as a failure
  - the step records `attention_required`
  - a `ManualInterventionRequirement` is persisted
  - the workflow remains review-facing

## Workflow Status Semantics

Day 21 uses the existing `WorkflowStatus` values:

- `queued`
- `running`
- `succeeded`
- `failed`
- `partial`
- `attention_required`

Current interpretation:

- `succeeded`
  - every step completed without failure or explicit manual stop
- `failed`
  - a hard-fail step exhausted retries or raised without retry
- `partial`
  - core upstream work completed but `operations_summary` failed after retries
- `attention_required`
  - the workflow reached an explicit review or intervention stop
  - the default local path usually ends here because paper-trade creation remains approval-gated

## Monitoring And Linkage

The daily orchestration layer also records monitoring artifacts for the parent daily run:

- a `PipelineEvent` for start
- a terminal `PipelineEvent`
- a parent `RunSummary`

`RunStep` and `WorkflowExecution` link child `RunSummary` IDs when underlying services already emit monitoring artifacts.

This means the operator can inspect:

- the parent daily run state
- the per-step execution state
- the child workflow run summaries already emitted by ingestion, parsing, research, feature mapping, signal generation, and signal arbitration

## What Is Automated Today

Automated today:

- local fixture refresh or ingestion reuse
- parsing and evidence extraction
- research workflow execution
- feature, signal, and arbitration generation
- portfolio proposal construction
- review queue sync
- monitoring summary generation

Not automated today:

- production scheduling
- automatic approval of research, signals, or proposals
- automatic paper-trade promotion through the approval boundary
- policy-complete eligibility enforcement

## Main Limits

- no production scheduler or job queue
- no distributed orchestration or worker model
- no resumable workflow engine
- no policy-complete downstream approval gate yet
- default local run still depends on fixture-backed development flows

The current layer is an explicit local operator workflow, not infrastructure.
