# Portfolio And Risk Flow

## Purpose

Day 7 turns candidate or approved signals into reviewable `PositionIdea` and `PortfolioProposal` artifacts with explicit sizing rules, explicit constraints, explicit risk checks, and preserved lineage.

This is not portfolio optimization.
This is not autonomous execution.
This is the first inspectable proposal layer downstream of signals.

## Current Flow

1. Load persisted Day 5 `Signal` artifacts plus linked Day 4 research artifacts.
2. Prefer the latest same-company `SignalBundle` and `ArbitrationDecision` when available.
3. If arbitration selected a primary signal, consume only that signal.
4. If arbitration intentionally withheld a primary signal, produce no `PositionIdea`.
5. If no arbitration bundle exists, fall back to raw signals with an explicit warning note.
6. Skip non-directional stances: `mixed` and `monitor`.
7. Run explicit portfolio construction:
   - rank candidates deterministically
   - record same-company competition
   - record included and rejected decisions
   - apply explicit sizing and hard constraints
8. Assemble included ideas into one `PortfolioProposal`.
9. Compute a `PortfolioExposureSummary`.
10. Build proposal-level attribution and structured stress-test artifacts.
11. Run explicit `RiskCheck` rules, including non-blocking proposal fragility warnings.
12. Mark the proposal `pending_review`.
13. Allow downstream paper-trade candidate creation only after explicit proposal approval and only when blocking issues are absent.

## Signal To Position Mapping

- `positive` signal -> `long` position idea
- `negative` signal -> `short` position idea
- `candidate` or unvalidated signal -> `300 bps`
- `approved` and validated signal -> `500 bps`
- `max_weight_bps` is fixed at `500`

Each included `PositionIdea` preserves:

- `signal_id`
- `signal_bundle_id`
- `arbitration_decision_id`
- `construction_decision_id`
- `position_sizing_rationale_id`
- `supporting_evidence_link_ids`
- `evidence_span_ids`
- `research_artifact_ids`
- `selection_reason`

Day 25 also persists explicit construction artifacts for candidates that were not selected:

- `ConstructionDecision`
- `ProposalRejectionReason`
- `SelectionConflict`
- `PortfolioSelectionSummary`

When arbitration is used, the selected primary signal now outranks other same-company candidates instead of making them disappear silently.

The Day 7 implementation resolves symbols from normalized `Company` metadata. If no ticker is available, the workflow emits no position idea instead of inventing a tradable symbol.

## Default Constraints

When the caller does not provide explicit constraints, the workflow uses:

- single-name hard limit: `500 bps`
- gross exposure hard limit: `1500 bps`
- net exposure hard limit: `1000 bps`
- turnover hard limit: `1500 bps`

## Risk Rules

The risk engine emits full `RiskCheck` artifacts. It does not auto-approve or auto-reject proposals.

Blocking failures:

- missing signal linkage, evidence linkage, or rationale
- single-name weight above limit
- gross exposure above limit
- absolute net exposure above limit
- flat-start turnover assumption above limit
- `EvidenceAssessment.grade` of `weak` or `insufficient`

Warnings:

- candidate or unvalidated signal input
- `EvidenceAssessment.grade` of `moderate`
- signal arbitration context missing
- signal arbitration conflicts present
- portfolio analysis missing
- portfolio concentration fragility
- portfolio stress fragility

## Portfolio Analysis

Day 20 adds a deterministic proposal-analysis layer before risk review.

It persists:

- `PortfolioAttribution`
- `PositionAttribution`
- `ScenarioDefinition`
- `StressTestRun`
- `StressTestResult`

This layer explains:

- which signals and position ideas drove the proposal
- which constraints have headroom
- which positions dominate concentration
- how the proposal behaves under a few simple stress cases

The current stress set is intentionally simple:

- broad market drawdown
- sector-specific shock when sector metadata exists
- volatility-increase sizing stress
- tighter single-name concentration stress
- confidence degradation stress

These artifacts are review-facing and advisory.
They do not create a new approval gate by themselves.

Day 25 now feeds construction artifacts into attribution as well, so proposal analysis can explain not only what is in the proposal, but which construction decisions and binding constraints shaped it.

## Review Boundary

Portfolio proposals are created with:

- `status = pending_review`
- `review_required = true`

Optional `ReviewDecision` artifacts can move a proposal to:

- `approved`
- `draft`
- `rejected`

Approval is blocked when the proposal still carries blocking risk issues.

## Artifacts

Day 7 persists local artifacts under `artifacts/portfolio/`:

- `position_ideas/`
- `constraints/`
- `selection_rules/`
- `constraint_sets/`
- `constraint_results/`
- `position_sizing_rationales/`
- `construction_decisions/`
- `selection_conflicts/`
- `portfolio_selection_summaries/`
- `exposure_summaries/`
- `portfolio_proposals/`
- `risk_checks/`
- `review_decisions/`
- `paper_trades/`

Day 20 also persists local artifacts under `artifacts/portfolio_analysis/`:

- `position_attributions/`
- `portfolio_attributions/`
- `scenario_definitions/`
- `stress_test_runs/`
- `stress_test_results/`

## Current Limitations

- One-company local-dev flow only.
- No optimizer, covariance model, or holdings-aware turnover model.
- Turnover is still measured from a flat-start assumption.
- Sector, liquidity, and beta checks are not implemented yet.
- Construction still allows only one active idea per company and current symbol path.
- Stress testing is heuristic and deterministic, not a risk-model platform.
- Candidate signals are still allowed into proposals, but they remain visibly provisional and review-gated.
- Signal arbitration improves comparison and conflict visibility, but it is not the reviewed-and-evaluated eligibility gate yet.
- When no arbitration bundle exists, the workflow still falls back to raw signals with an explicit warning.
