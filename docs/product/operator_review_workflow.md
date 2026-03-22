# Operator Review Workflow

## Purpose

The repo includes a first-class operator review layer over research briefs, candidate signals, portfolio proposals, and paper trades.

The goal is explicit human workflow, not cosmetic UI:

- surface reviewable objects in one queue
- attach notes and assignments
- apply explicit review actions
- preserve queue state transitions
- record auditable before-and-after changes

## Reviewable Targets

The current workflow supports four target types:

- `research_brief`
- `signal`
- `portfolio_proposal`
- `paper_trade`

`ResearchBrief` is the primary research review object. Hypotheses, counter-hypotheses, evidence assessments, and evidence spans remain visible through derived review context rather than separate queue items.

## Core Objects

- `ReviewQueueItem`: persisted queue state for one target
- `ReviewContext`: derived inspection view built from current artifacts
- `ReviewNote`: operator note attached to one target
- `ReviewAssignment`: single active assignee for one queue item
- `ReviewDecision`: generic review decision reused across domains
- `ActionRecommendationSummary`: conservative recommendation shown to the operator

Artifacts are persisted under `artifacts/review/`:

- `queue_items/`
- `review_notes/`
- `review_assignments/`
- `review_decisions/`

## What Review Context Includes Today

Review context is no longer just the target object. Depending on the target type, it can include:

- related evidence and research artifacts
- signal arbitration context
- related prior work from metadata-first retrieval
- portfolio attribution
- position attributions
- stress-test runs and stress-test results
- risk checks and blocking issues

The context is built from persisted local artifacts, not from a database-backed read model.

## Queue Sync Rules

Queue sync materializes items for:

- `ResearchBrief` with `review_status in {pending_human_review, revision_requested}`
- `Signal` with `status = candidate`
- `PortfolioProposal` with `status in {pending_review, draft}`
- `PaperTrade` with `status = proposed`

The queue does not silently approve anything. It surfaces work and reflects explicit operator actions.

## Review Actions

Supported actions:

- `approve`
- `reject`
- `needs_revision`
- `escalate`

Target-specific transitions:

### Research Brief

- `approve` -> `approved_for_feature_work`
- `needs_revision` -> `revision_requested`
- `reject` -> `rejected`
- `escalate` -> keep research status unchanged

### Signal

- `approve` -> `approved`
- `needs_revision` -> remain `candidate`
- `reject` -> `rejected`
- `escalate` -> keep signal status unchanged

### Portfolio Proposal

- uses the existing proposal transition mapping
- blocking proposals cannot be approved

### Paper Trade

- uses the existing paper-trade transition mapping
- trade approval still requires an approved, non-blocked parent proposal

Queue-item transitions:

- new item -> `pending_review`
- assignment may move item -> `in_review`
- `approve` or `reject` -> `resolved`
- `needs_revision` -> `awaiting_revision`
- `escalate` -> `escalated`

## Auditability

Every material review action creates an `AuditLog` under `artifacts/audit/audit_logs/`.

Review audit events preserve:

- actor
- target type and target ID
- action
- rationale
- request or decision ID
- `status_before`
- `status_after`
- related artifact IDs

This applies to:

- queue item creation and refresh
- note creation
- assignment changes
- review action application
- escalation requests

## Current Limitations

- there is no frontend console yet
- assignment is still single-reviewer only
- review context is rebuilt from local filesystem artifacts
- approved state exists, but the full reviewed-and-evaluated downstream eligibility gate is still incomplete
- review history is durable locally, but not tamper-evident

## Correct Framing

The current review layer is real and useful. It should be described as:

- a local, artifact-backed human review workflow
- explicit queueing and decision state
- conservative downstream gating for paper-trade candidates

It should not be described as:

- a production operations console
- a complete downstream promotion-policy engine
- a substitute for stronger snapshot-native selection or instrument identity
