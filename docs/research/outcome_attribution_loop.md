# Outcome Attribution Loop

## Purpose

Day 26 closes part of the loop between downstream paper-trade outcomes and upstream research artifacts.

The goal is not to claim causal truth.
The goal is to preserve structured linkage so researchers and reviewers can inspect:

- which signal led to a paper trade
- which research artifacts supported it
- which construction decisions shaped it
- which risk warnings applied
- which review decisions and notes were in the path
- what the operator later concluded about the outcome

## What Gets Linked

`OutcomeAttribution` currently links one `TradeOutcome` back to:

- `PaperTrade`
- `PaperPositionState`
- `PortfolioProposal`
- `PositionIdea`
- `Signal`
- signal `feature_ids`
- position-idea `research_artifact_ids`
- `PortfolioSelectionSummary`
- `ConstructionDecision`
- `PositionSizingRationale`
- proposal `RiskCheck` artifacts
- proposal and paper-trade `ReviewDecision` records
- related `ReviewNote` records
- `StrategyToPaperMapping` and `ReconciliationReport` when they exist

This creates a durable backward trail without pretending the system can infer the true driver automatically.

## What Is Human-Authored

`TradeOutcome` contains explicit human-authored judgment fields:

- thesis assessment
- whether prior risk warnings were relevant
- assumption notes
- learning notes

The system auto-links the lineage.
It does not auto-explain the result.

## What The Loop Improves Today

Day 26 makes it easier to inspect:

- whether a paper trade stayed aligned with the original thesis
- whether prior risk warnings mattered in hindsight
- whether a construction choice or sizing limit should be revisited
- whether follow-up research or review work is still open

This is a learning and accountability loop, not a performance-optimization shortcut.

## What Remains Simplified

- no semantic learning engine is added
- no automatic score update is pushed back into signals
- no promotion gate yet consumes trade outcomes directly
- no causal attribution model exists
- placeholder PnL remains reference-price-based only

The next serious step is to feed open followups and outcome artifacts into the Week 4 readiness and eligibility boundary, not to turn them into fake alpha labels.
