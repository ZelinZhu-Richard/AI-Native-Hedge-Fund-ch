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

Day 24 also records explicit paper-side realism artifacts:

- `ExecutionTimingRule`
- `FillAssumption`
- `CostModel`
- `RealismWarning`

These artifacts make the current paper assumptions inspectable. They do not simulate execution.

Day 26 adds a separate post-approval paper-ledger layer:

- approved `PaperTrade` objects can be admitted into `PaperPositionState`
- lifecycle events are recorded as `PositionLifecycleEvent`
- append-only paper-book rows are recorded as `PaperLedgerEntry`
- post-trade assessments are recorded as `TradeOutcome`
- backward lineage is preserved through `OutcomeAttribution`
- open post-trade actions are recorded as `ReviewFollowup`
- local paper-book status can be summarized through `DailyPaperSummary`

## Review Boundary

Proposal approval does not auto-approve trades.

Paper trades remain separate review objects with their own lifecycle:

- `proposed`
- `approved`
- `rejected`
- `simulated`
- `cancelled`

Day 7 only creates `proposed` paper trades.

Day 26 does not change that.
It adds a tracked paper-position lifecycle only after explicit paper-trade approval.

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
- optional `execution_timing_rule_id`
- optional `fill_assumption_id`
- optional `cost_model_id`
- optional `paper_position_state_id`
- optional `latest_trade_outcome_id`
- provenance back to the proposal, position idea, and signal

Paper-trade proposal responses now also surface the paper-side timing rule, fill assumption, cost model, and realism warnings directly.

Approved paper trades can now later accumulate:

- `paper_position_states/`
- `paper_ledger_entries/`
- `position_lifecycle_events/`
- `trade_outcomes/`
- `outcome_attributions/`
- `review_followups/`
- `daily_paper_summaries/`

## Non-Goals

Day 7 does not include:

- broker adapters
- exchange connectivity
- order-state machines
- fill simulation beyond the existing backtesting layer
- holdings reconciliation
- multi-fill execution accounting
- realized performance reporting

## Current Limitations

- Quantity is only available when a caller passes a reference price.
- Trade-level review exists through the generic operator review layer, but there is still no dedicated console or richer operator workflow for it.
- Day 7 does not simulate paper-trade fills from this workflow.
- Costs remain estimate-only.
- Human approval delay is explicit but still not modeled as a simulated fill path.
- Day 26 placeholder PnL is still reference-price-based bookkeeping only.
- `PaperTrade` is still not a holdings engine; one approved trade maps to one local paper-position state.
