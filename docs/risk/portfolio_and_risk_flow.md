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
7. Map each eligible signal into one `PositionIdea`.
8. Assemble all position ideas into one `PortfolioProposal`.
9. Compute a `PortfolioExposureSummary`.
10. Run explicit `RiskCheck` rules.
11. Mark the proposal `pending_review`.
12. Allow downstream paper-trade candidate creation only after explicit proposal approval and only when blocking issues are absent.

## Signal To Position Mapping

- `positive` signal -> `long` position idea
- `negative` signal -> `short` position idea
- `candidate` or unvalidated signal -> `300 bps`
- `approved` and validated signal -> `500 bps`
- `max_weight_bps` is fixed at `500`

Each `PositionIdea` preserves:

- `signal_id`
- `signal_bundle_id`
- `arbitration_decision_id`
- `supporting_evidence_link_ids`
- `evidence_span_ids`
- `research_artifact_ids`
- `selection_reason`

When arbitration is used, `selection_reason` explicitly points to the arbitrated primary selection rather than implying that raw signal ranking alone chose the idea.

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
- `exposure_summaries/`
- `portfolio_proposals/`
- `risk_checks/`
- `review_decisions/`
- `paper_trades/`

## Current Limitations

- One-company local-dev flow only.
- No optimizer, covariance model, or holdings-aware turnover model.
- Turnover is still measured from a flat-start assumption.
- Sector, liquidity, and beta checks are not implemented yet.
- Candidate signals are still allowed into proposals, but they remain visibly provisional and review-gated.
- Signal arbitration improves comparison and conflict visibility, but it is not the reviewed-and-evaluated eligibility gate yet.
- When no arbitration bundle exists, the workflow still falls back to raw signals with an explicit warning.
