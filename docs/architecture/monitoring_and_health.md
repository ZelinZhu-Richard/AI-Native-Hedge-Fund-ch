# Monitoring And Health

## Purpose

Day 12 adds a local, metadata-first monitoring layer for the research OS.

It is designed to answer:

- what ran
- what succeeded
- what failed
- what needs attention
- what outputs were produced

It is not a full observability platform. There is no metrics backend, tracing stack, or streaming log pipeline in this repo today.

## Primary Artifacts

The monitoring layer lives under `artifacts/monitoring/` and currently persists:

- `run_summaries/`
- `pipeline_events/`
- `health_checks/`
- `alert_conditions/`
- `alert_records/`

`RunSummary` is the primary artifact.

Each `RunSummary` records:

- workflow name and workflow run ID
- owning service
- terminal workflow status
- requester
- start and completion times
- produced artifact IDs
- produced artifact counts by category
- storage locations written by the workflow
- linked pipeline events
- linked alerts
- failure messages and attention reasons

## Current Monitoring Coverage

Day 12 explicitly attaches monitoring to these workflows:

- fixture ingestion
- evidence extraction
- strategy ablation
- operator review actions

The monitoring path is intentionally selective. It records major workflow milestones and outcomes, not every internal function call.

## Health Model

Health is local and structural, not external-service-grade.

Current checks:

- artifact root resolved
- monitoring storage available
- service registry loaded
- review storage readable
- recent open alerts present

Current service-level status is derived from:

- recent health checks
- recent monitored run summaries
- currently open alerts

## Alerts

Day 12 records simple built-in alert conditions:

- `workflow_failed`
- `attention_required`
- `zero_outputs_when_outputs_expected`
- `health_check_failed`

Alerts are persisted as explicit artifacts. They are not email notifications, pager integrations, or dashboard events yet.

## Limits

The current layer does not provide:

- distributed tracing
- external dependency probes
- latency or resource metrics
- alert acknowledgment workflows
- operator dashboards

It is intentionally small and inspectable. The goal is to make the repo honest and reviewable before adding richer operational tooling.
