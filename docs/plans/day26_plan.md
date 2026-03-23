# Day 26 Plan

## Summary

Day 26 hardens paper trading into a more operationally real local workflow:

- approved paper trades now admit into a paper ledger
- lifecycle changes are explicit artifacts
- paper positions can receive structured outcomes
- outcomes now link back into research, construction, risk, review, and reconciliation context
- daily summaries can surface open followups and incomplete mark coverage

## Main Additions

- `libraries/schemas/paper_ledger.py`
- `services/paper_ledger/`
- new paper-ledger artifacts under `artifacts/portfolio/`
- operator-review integration that admits approved paper trades into the ledger
- review-context integration for paper-ledger and outcome artifacts

## Defaults

- `PaperTrade` remains the candidate artifact
- ledger tracking begins only after explicit trade approval
- no automatic fill engine is added
- placeholder PnL stays mark-based and local only
- no new queue target type is added for followups

## Non-Goals

- no live execution
- no brokerage adapters
- no holdings engine
- no realized performance reporting
- no automatic inference of why a trade worked

## Best Follow-On

Use `TradeOutcome`, `OutcomeAttribution`, and open `ReviewFollowup` artifacts as explicit readiness inputs for Week 4 policy and evaluation work, so paper-trade learning becomes part of downstream discipline instead of remaining local bookkeeping.
