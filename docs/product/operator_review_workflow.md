# Operator Review Workflow

## Purpose

Day 11 adds a first-class operator review layer on top of the existing research, signal, portfolio, and paper-trade artifacts.

The goal is explicit human workflow, not cosmetic UI:

- surface reviewable objects in one queue
- attach notes and assignments
- apply explicit review actions
- preserve queue state and status transitions
- record auditable before/after changes

## Reviewable Targets

The current workflow supports four target types:

- `research_brief`
- `signal`
- `portfolio_proposal`
- `paper_trade`

`ResearchBrief` is the primary research review object. Hypotheses, critiques, evidence assessments, and evidence links are shown through the derived review context, not queued as separate operator items.

## Core Objects

- `ReviewQueueItem`: persisted queue state for one target
- `ReviewContext`: derived console read model built from current artifacts
- `ReviewNote`: operator note attached to one target
- `ReviewAssignment`: single active assignee for one queue item
- `ReviewDecision`: generic review decision reused across domains
- `ActionRecommendationSummary`: conservative recommendation shown to the operator

Artifacts are persisted under `artifacts/review/`:

- `queue_items/`
- `review_notes/`
- `review_assignments/`
- `review_decisions/`

## Queue Sync Rules

Queue sync scans persisted artifacts and materializes reviewable items for:

- `ResearchBrief` with `review_status in {pending_human_review, revision_requested}`
- `Signal` with `status = candidate`
- `PortfolioProposal` with `status in {pending_review, draft}`
- `PaperTrade` with `status = proposed`

The queue does not silently approve anything. It only surfaces work and reflects explicit operator actions.

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

Every material review action creates an `AuditLog` artifact under `artifacts/audit/audit_logs/`.

Review audit events now preserve:

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
- assignment is single-reviewer only
- review context is rebuilt from local filesystem artifacts, not a database-backed read model
- reviewed state exists, but downstream enforcement is not complete yet
- review history is durable locally, but not tamper-evident

## Immediate Next Step

Day 12 should make reviewed and evaluated state operationally gate downstream workflows so exploratory signals and unreviewed proposals cannot drift into later stages by convention alone.
