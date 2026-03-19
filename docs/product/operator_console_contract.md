# Operator Console Contract

## Scope

Day 11 does not build a polished UI. It defines the service and API contract a future operator console will consume.

The console contract is built around two concepts:

- queue listing
- target-specific review context

## Service Surface

`OperatorReviewService` exposes:

- `sync_review_queue(...)`
- `list_review_queue(...)`
- `get_review_context(...)`
- `add_review_note(...)`
- `assign_review(...)`
- `apply_review_action(...)`

## API Surface

The API now exposes:

- `GET /reviews/queue`
- `GET /reviews/context/{target_type}/{target_id}`
- `POST /reviews/notes`
- `POST /reviews/assignments`
- `POST /reviews/actions`

The API is thin. It delegates to the operator review service and does not implement separate review logic.

## Queue Payload

Each queue row is a `ReviewQueueItem` with:

- target type and target ID
- queue status
- current target status
- title
- summary
- escalation status
- action recommendation
- linked note IDs
- linked decision IDs
- active assignment ID if present

This is enough for a future console list view to show:

- what needs attention
- why it is in queue
- whether it is assigned
- whether it is blocked or escalated

## Context Payload

`ReviewContext` is the derived console read model.

Depending on target type, it can include:

- `ResearchBrief`
- linked `Hypothesis`
- linked `CounterHypothesis`
- linked `EvidenceAssessment`
- exact `SupportingEvidenceLink` rows
- `Signal`
- `PortfolioProposal`
- `PaperTrade`
- related `RiskCheck` rows
- related `PositionIdea` rows
- related `Signal` rows
- review notes
- review decisions
- recent audit logs
- current action recommendation

## Minimum Console Views

### Research Review

Display:

- brief title and summary
- core hypothesis
- counter-hypothesis summary
- evidence assessment
- exact supporting evidence links
- notes, decisions, and audit history

### Signal Review

Display:

- thesis summary
- stance and score
- lineage and upstream research artifact IDs
- visible uncertainties
- notes, decisions, and audit history

### Portfolio Review

Display:

- proposal summary
- position ideas
- exposure summary
- risk checks
- blocking issues
- notes, decisions, and audit history

### Paper Trade Review

Display:

- trade side, symbol, notional, and execution mode
- parent proposal status
- source position idea
- related risk checks
- notes, decisions, and audit history

## Constraints

The console contract intentionally does not provide:

- silent approval
- live execution
- broker routing
- automatic promotion based only on UI interaction

## Known Gaps

- no dedicated trade-level dashboard exists yet
- no bulk actions exist yet
- no persistent reviewer inbox or escalation workflow beyond queue state exists yet
- downstream eligibility gating is still incomplete
