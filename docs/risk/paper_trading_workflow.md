# Paper Trading Workflow

## Purpose

Day 7 creates paper-trade candidates only from approved portfolio proposals.

This layer exists to preserve auditability and review structure.
It does not connect to a broker.
It does not imply autonomous execution.

## Input Boundary

The paper-trade flow consumes a full `PortfolioProposal`, not loose position rows.

Accepted proposal statuses:

- `approved`

Pending-review, rejected, or revision-needed proposals do not create paper trades.
Proposals with blocking risk checks do not create paper trades.

## Trade Candidate Rules

For each non-flat `PositionIdea` in an eligible proposal:

- `notional_usd = target_nav_usd * abs(proposed_weight_bps) / 10_000`
- `execution_mode = paper_only`
- `status = proposed`
- `review_decision_ids = []` at creation time

If a caller supplies an `assumed_reference_price_usd`, the workflow also materializes:

- `quantity = notional_usd / assumed_reference_price_usd`

If no reference price is provided, quantity remains `null`.

## Review Boundary

Proposal approval does not auto-approve trades.

Paper trades remain separate review objects with their own lifecycle:

- `proposed`
- `approved`
- `rejected`
- `simulated`
- `cancelled`

Day 7 only creates `proposed` paper trades.

## Auditability

Each `PaperTrade` preserves:

- `portfolio_proposal_id`
- `position_idea_id`
- `symbol`
- `side`
- `notional_usd`
- optional `assumed_reference_price_usd`
- optional `quantity`
- explicit `execution_notes`
- provenance back to the proposal, position idea, and signal

## Non-Goals

Day 7 does not include:

- broker adapters
- exchange connectivity
- order-state machines
- fill simulation beyond the existing backtesting layer
- holdings reconciliation

## Current Limitations

- Quantity is only available when a caller passes a reference price.
- Trade-level review exists through the generic operator review layer, but there is still no dedicated console or richer operator workflow for it.
- Day 7 does not simulate paper-trade fills from this workflow.
