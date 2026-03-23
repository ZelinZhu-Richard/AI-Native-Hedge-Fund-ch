# Paper Ledger And Outcomes

## Purpose

Day 26 adds a paper-ledger layer that starts only after a `PaperTrade` is explicitly approved.

The goal is to make paper trading operationally visible and auditable:

- approved trades become tracked paper-position states
- lifecycle events are append-only and inspectable
- post-trade outcomes can be linked back to research, signals, construction, risk, and review
- daily summaries can surface open issues and incomplete mark coverage

This is still a paper-only workflow.
It does not connect to a broker.
It does not imply live fills or realized execution-quality PnL.

## Core Objects

The current paper-ledger layer persists these artifacts under `artifacts/portfolio/`:

- `paper_trades/`
- `paper_position_states/`
- `paper_ledger_entries/`
- `position_lifecycle_events/`
- `trade_outcomes/`
- `outcome_attributions/`
- `review_followups/`
- `daily_paper_summaries/`

Key roles:

- `PaperTrade`
  - reviewable candidate trade object
  - still created by `PaperExecutionService`
- `PaperPositionState`
  - current-state read model for one admitted paper position
- `PaperLedgerEntry`
  - append-only paper-book entry for one lifecycle event
- `PositionLifecycleEvent`
  - explicit state transition record
- `TradeOutcome`
  - post-trade outcome assessment
- `OutcomeAttribution`
  - backward-linking artifact from outcome to upstream lineage
- `ReviewFollowup`
  - explicit post-trade action item
- `DailyPaperSummary`
  - local summary of current paper-book state for one date

## How The Ledger Starts

`PaperTrade` remains a candidate artifact until an operator explicitly approves it through the existing operator-review flow.

On approval:

- `OperatorReviewService.apply_review_action()` still updates the `PaperTrade`
- `PaperLedgerService.admit_approved_trade()` then creates:
  - one `PaperPositionState`
  - one `PositionLifecycleEvent(event_type="approval_admitted")`
  - one `PaperLedgerEntry`
- the approved `PaperTrade` is updated with `paper_position_state_id`

If quantity or entry reference price is still missing:

- the position is admitted anyway
- the state remains explicit and incomplete
- one open `ReviewFollowup` is created
- the system does not invent quantity or placeholder PnL

## Lifecycle Events

Supported lifecycle events today:

- `approval_admitted`
- `simulated_fill_placeholder`
- `mark_updated`
- `closed`
- `cancelled`

Important behavior:

- there is still no automatic fill simulation in the paper workflow
- `simulated_fill_placeholder` is an explicit manual lifecycle event, not a hidden engine
- `closed` and `cancelled` are terminal paper-position states
- `PaperTrade.status` only changes where the legacy vocabulary is already honest:
  - simulated fill -> `simulated`
  - cancellation -> `cancelled`

`closed` is represented on `PaperPositionState`, not by overloading `PaperTradeStatus`

## Daily Summaries

`PaperLedgerService.generate_daily_paper_summary()` creates a local daily summary.

It records:

- open, closed, and cancelled counts
- lifecycle events seen on that date
- trade outcomes recorded on that date
- currently open followups
- optional aggregate placeholder mark PnL

Aggregate placeholder PnL is only emitted when mark coverage is sufficient.
If marks are missing, the summary records the gap explicitly instead of fabricating a number.

## What This Still Does Not Do

Day 26 does not add:

- live execution
- brokerage connectivity
- holdings reconciliation
- multi-fill order books
- realized performance reporting
- automatic causal inference about why a trade worked

The ledger is a local accountability layer.
It makes the workflow more inspectable.
It does not make paper trading equivalent to real execution.
