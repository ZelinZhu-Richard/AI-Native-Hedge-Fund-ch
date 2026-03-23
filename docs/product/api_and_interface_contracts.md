# API And Interface Contracts

## Purpose

The local interface layer is meant to be easy to consume without pretending the repo is a production platform.

The API and CLI are both:

- local
- deterministic where the underlying workflow is deterministic
- artifact-backed
- explicit about review-bound stops and missing downstream automation

They do **not** provide live trading, multi-user control-plane behavior, or hidden execution paths.

## Main Interface Surfaces

Primary local entrypoints:

- `make api`
- `anhf manifest`
- `anhf capabilities`
- `anhf demo run`
- `anhf daily run`
- `anhf review queue --json`
- `anhf monitoring recent-runs --json`

FastAPI remains the local inspection and coordination surface. The unified CLI is the primary command-line surface.

## Success Response Shape

Successful API responses now use `APIResponseEnvelope[T]`:

- `status`
- `data`
- `warnings`
- `notes`
- `generated_at`

Important rule:

- `data` is the typed payload
- `warnings` are visible caveats, not hidden log-only conditions
- `notes` are explanatory text only
- the envelope does not replace the underlying domain artifact

## Error Response Shape

Non-success API responses now use `ErrorResponse`:

- `status="error"`
- `error_code`
- `message`
- `details`
- `path`
- `timestamp`

Current stable error-code families:

- `validation_error`
- `invalid_request`
- `not_found`
- `http_error`

The API no longer falls back to unstructured FastAPI detail strings for the documented error paths.

For workflow invocation responses, `attention_required` means the workflow stopped in a visible manual-attention state. Inspect notes and any linked manual-intervention requirements to distinguish a healthy review-bound stop from a harder blocked stop.

## Canonical Routes

Preferred canonical routes:

- `GET /system/health`
- `GET /system/health/details`
- `GET /system/version`
- `GET /system/capabilities`
- `GET /system/manifest`
- `GET /monitoring/run-summaries/recent`
- `GET /monitoring/failures/recent`
- `GET /monitoring/services`
- `POST /documents/ingest`
- `GET /research/hypotheses`
- `GET /research/briefs`
- `GET /portfolio/proposals`
- `GET /portfolio/paper-trades`
- `GET /reviews/queue`
- `GET /reviews/context/{target_type}/{target_id}`
- `POST /reviews/notes`
- `POST /reviews/assignments`
- `POST /reviews/actions`
- `GET /reports/daily-system/latest`
- `GET /reports/proposals/{portfolio_proposal_id}/scorecard`
- `GET /reports/review-queue/latest`
- `POST /workflows/demo/run`
- `POST /workflows/daily/run`

Compatibility aliases still exist for older unscoped paths such as `/health`, `/version`, `/hypotheses`, `/portfolio-proposals`, and `/paper-trades/proposals`, but the canonical namespaced routes are preferred.

`/system/manifest` and `anhf capabilities --json` should advertise the canonical namespaced routes only. Compatibility aliases remain in the route layer and are not the primary documented interface.

## Capability And Manifest Surfaces

`GET /system/capabilities` returns normalized `CapabilityDescriptor` rows across:

- services
- agents
- workflow entrypoints

`GET /system/manifest` returns a `ServiceManifest` with:

- project and environment metadata
- resolved artifact root
- normalized capability descriptors
- current config surface
- explicit interface warnings

This manifest is descriptive only. It is not a permissions or policy system.

## Workflow Entry Points

The API intentionally exposes only two runnable workflow entrypoints:

- `POST /workflows/demo/run`
- `POST /workflows/daily/run`

These endpoints are honest local wrappers over the existing demo and daily workflows. They return compact interface-facing results:

- `DemoRunResult`
- `WorkflowInvocationResult`

They do **not** expose arbitrary service execution or hidden workflow controls.

## Current Limits

- the API is still local and unauthenticated
- the CLI is still a thin local wrapper, not a job runner
- workflow invocation remains synchronous
- listing endpoints are artifact-root based, not database-backed
- legacy aliases still exist during the cleanup transition
