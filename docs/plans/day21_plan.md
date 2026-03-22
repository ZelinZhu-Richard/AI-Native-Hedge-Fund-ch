# Day 21 Plan

## Goal

Turn the current research platform into a more repeatable daily operating workflow.

The target is not production infra. The target is a clean local orchestration path plus an explicit operator runbook.

## What Day 21 Adds

### Orchestration Contracts

Day 21 adds a dedicated orchestration schema module with:

- `WorkflowDefinition`
- `ScheduledRunConfig`
- `RunStep`
- `RunbookEntry`
- `RetryPolicy`
- `RunFailureAction`
- `ManualInterventionRequirement`
- `WorkflowExecution`

Artifacts persist under `artifacts/orchestration/`.

### Daily Orchestration Service

Day 21 adds `DailyOrchestrationService` plus a thin pipeline wrapper and CLI entrypoint.

The implemented order is:

1. fixture refresh and normalization
2. evidence extraction
3. research workflow
4. feature, signal, and arbitration pipeline
5. portfolio workflow
6. review queue sync
7. paper-trade candidate generation
8. operations summary

### Failure And Stop-State Rules

Day 21 makes step behavior explicit:

- ingestion and parsing steps retry once automatically
- research, signal, and portfolio failures hard-fail the workflow
- review queue sync failures stop in `attention_required`
- paper-trade generation stops in `attention_required` when proposal approval is missing
- operations summary failures after retry leave the workflow in `partial`

### Runbook Support

Day 21 persists code-owned `RunbookEntry` artifacts and adds a human-readable operator runbook doc.

Both describe:

- what runs
- in what order
- what outputs to expect
- what operators should inspect
- how failures should be triaged
- where manual review gates still exist

## What Day 21 Does Not Add

Day 21 does not add:

- cron scheduling
- distributed workers
- resumable job orchestration
- automatic approval paths
- live execution
- a completed reviewed-and-evaluated eligibility gate

## Why This Matters

Without explicit daily orchestration, the current stack can run, but it is too easy for operators to run steps in inconsistent order or miss review boundaries.

Day 21 makes the local workflow:

- explicit
- inspectable
- review-facing
- failure-aware
- repeatable

## Best Follow-On Target

The next highest-leverage step after Day 21 is to connect this orchestration layer to the real reviewed-and-evaluated eligibility gate, so the daily workflow stops for explicit policy reasons instead of relying mainly on proposal status and operator convention.
