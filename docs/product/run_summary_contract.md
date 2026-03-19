# Run Summary Contract

## Purpose

`RunSummary` is the operator-facing monitoring artifact for a workflow run.

It is meant to support future dashboards, postmortems, and attention queues without depending on raw logs or hidden internal state.

## What A Run Summary Contains

Each `RunSummary` records:

- `workflow_name`
- `workflow_run_id`
- `service_name`
- `status`
- `requested_by`
- `started_at`
- `completed_at`
- `produced_artifact_ids`
- `produced_artifact_counts`
- `storage_locations`
- `pipeline_event_ids`
- `alert_record_ids`
- `failure_messages`
- `attention_reasons`
- `notes`
- provenance

## Status Semantics

Current `WorkflowStatus` values:

- `queued`
- `running`
- `succeeded`
- `failed`
- `partial`
- `attention_required`

Important interpretation:

- `succeeded` means the workflow completed and did not raise an operational concern in the monitoring layer
- `failed` means the workflow raised and re-threw an exception
- `attention_required` means the workflow completed but produced a result that should be reviewed, such as an ablation run with structural warnings

## What Counts As “What Changed”

The Day 12 layer does not attempt full artifact diffs.

Instead, it records:

- exact produced artifact IDs when available
- high-level artifact counts by persisted category
- the storage locations that were written

That is enough to answer what the workflow materially produced without pretending to provide deep change attribution yet.

## Current Workflow Coverage

Day 12 run summaries are recorded for:

- fixture ingestion
- evidence extraction
- strategy ablation
- operator review actions

Other workflows may still produce artifacts and audit logs without emitting `RunSummary` yet.

## Limits

`RunSummary` is not:

- a replacement for `AuditLog`
- a full event stream
- a metrics time series
- a promotion or approval decision

It is the compact operational summary for one workflow execution.
