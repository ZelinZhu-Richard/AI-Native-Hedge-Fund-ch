# Operator Runbook

## Purpose

This runbook explains how to execute and review the current local daily workflow consistently.

It is paired with persisted `RunbookEntry` artifacts under `artifacts/orchestration/runbook_entries/`.

The doc is the human-readable reference. The artifacts are the code-owned per-step contract.

## How To Run The Workflow

Current local entrypoints:

- `make daily-run`
- `anhf daily run --artifact-root <path> --requested-by manual_local_run`
- legacy module entrypoint: `python -m pipelines.daily_operations.daily_workflow --artifact-root <path>`

Important defaults:

- run mode is local and manual
- default data refresh mode is `fixture_refresh`
- memo skeleton generation is enabled by default
- advisory retrieval context is enabled by default
- no step auto-approves a proposal or trade

## Expected Daily Order

1. Refresh fixtures and normalize canonical ingestion artifacts.
2. Extract evidence from normalized documents.
3. Run the research workflow.
4. Build features, signals, and arbitration artifacts.
5. Build the portfolio proposal and attach attribution, stress tests, and risk checks.
6. Sync the operator review queue.
7. Attempt paper-trade candidate generation without bypassing approval.
8. Collect health checks and recent run summaries.

## What To Check At Each Step

### 1. Fixture Refresh And Normalization

Check:

- the expected fixtures were discovered
- normalized artifacts exist under `artifacts/ingestion/`
- timing and entity-resolution notes do not show silent ambiguity

If it fails:

- verify the fixture root exists
- inspect ingestion run summaries
- fix malformed or missing fixture inputs before rerunning

### 2. Evidence Extraction

Check:

- parsing artifacts exist under `artifacts/parsing/`
- each document produced evidence spans
- timing anomalies or unresolved entity links are visible, not hidden

If it fails:

- verify the normalized document, source reference, and raw payload all exist
- inspect parsing run summaries for the failing document

### 3. Research Workflow

Check:

- an evidence assessment was produced
- when support is sufficient, hypothesis, counter-hypothesis, brief, and memo artifacts exist
- retrieval-context notes explain how prior work was surfaced

If it fails:

- check whether the parsing root contains multiple companies without a `company_id`
- inspect the research workflow run summary and audit records

Human review:

- operators should inspect the brief or evidence assessment before treating the research output as trustworthy downstream context

### 4. Feature Signal Pipeline

Check:

- features were mapped from explicit research artifacts
- candidate signals were emitted
- signal arbitration produced an inspectable bundle or visible no-op notes

If it fails:

- inspect research lineage, timing notes, and signal arbitration notes
- verify the upstream research artifacts are complete enough for feature and signal generation

Human review:

- arbitration does not replace human review or the later eligibility gate

### 5. Portfolio Workflow

Check:

- a portfolio proposal exists
- a risk summary and proposal scorecard were persisted under `artifacts/reporting/`
- attribution and stress artifacts are linked
- risk checks and blocking issues are visible

If it fails:

- inspect arbitration output and risk warnings
- verify the proposal still has valid portfolio inputs

Human review:

- proposal review remains mandatory

### 6. Review Queue Sync

Check:

- new research, signal, and portfolio items are in the review queue
- queue items show conservative recommendations and current statuses

If it fails:

- inspect review-root readability and queue persistence
- rerun sync after fixing the storage or artifact-loading issue

Human review:

- open the queue and inspect surfaced items before attempting downstream approvals

### 7. Paper-Trade Candidate Generation

Check:

- if the proposal is not approved, the step must stop with zero trades
- if trades are present, the parent proposal approval path must be explicit

Default expectation:

- this step usually ends in `attention_required`
- zero trades is the correct default outcome for unapproved proposals

If it fails or stops:

- inspect portfolio proposal status, blocking issues, and review decisions
- do not bypass the approval gate

### 8. Operations Summary

Check:

- health checks were persisted
- recent run summaries include the child workflows you expect
- open alerts or attention-required runs are reviewed before treating the day as healthy

If it fails:

- inspect the monitoring root and service registry health
- rerun health checks after fixing monitoring storage issues

## Manual Review Gates

Current explicit human review gates:

- research remains review-facing
- candidate signals remain review-facing
- portfolio proposals remain review-required
- paper-trade candidate generation does not bypass proposal approval

The daily workflow is not meant to run all the way to autonomous paper execution.

## What Counts As A Healthy Default Run

A healthy local default run usually means:

- ingestion, parsing, research, signals, and portfolio steps succeeded
- review queue sync succeeded
- paper-trade candidate generation stopped in `attention_required`
- operations summary completed

That is a correct review-facing outcome. It is not a failure.

## Current Limits

- no scheduler
- no resumable job graph
- no automatic approval path
- no production incident tooling
- no complete reviewed-and-evaluated policy gate yet

This runbook is for disciplined local operation, not production operations engineering.
