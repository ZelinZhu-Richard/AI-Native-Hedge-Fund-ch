from __future__ import annotations

from pathlib import Path

from pydantic import Field

from libraries.core import build_provenance, resolve_artifact_workspace_from_stage_root
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    CostModel,
    ExecutionTimingRule,
    FillAssumption,
    PaperTrade,
    PaperTradeStatus,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionSide,
    QualityDecision,
    RealismWarning,
    RefusalReason,
    StrictModel,
    ValidationGate,
)
from libraries.utils import make_canonical_id, make_prefixed_id
from services.backtest_reconciliation import BacktestReconciliationService
from services.data_quality import DataQualityService


class PaperTradeProposalRequest(StrictModel):
    """Request to translate an approved portfolio proposal into paper-trade candidates."""

    portfolio_proposal: PortfolioProposal = Field(
        description="Approved portfolio proposal to translate into paper trades."
    )
    assumed_reference_prices: dict[str, float] = Field(
        default_factory=dict,
        description="Optional symbol-to-price mapping used to materialize quantities.",
    )
    requested_by: str = Field(description="Requester identifier.")


class PaperTradeProposalResponse(StrictModel):
    """Response containing Day 7 paper-trade candidates."""

    trade_batch_id: str = Field(description="Identifier for the proposed paper-trade batch.")
    proposed_trades: list[PaperTrade] = Field(
        default_factory=list,
        description="Proposed paper trades.",
    )
    review_required: bool = Field(description="Whether trade-level approval is still required.")
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes describing skipped work or gating conditions.",
    )
    validation_gate: ValidationGate | None = Field(
        default=None,
        description="Data-quality gate recorded for paper-trade request or output validation.",
    )
    quality_decision: QualityDecision | None = Field(
        default=None,
        description="Overall decision emitted by the current paper-trade validation gate.",
    )
    refusal_reason: RefusalReason | None = Field(
        default=None,
        description="Primary refusal reason when paper-trade creation was blocked.",
    )
    execution_timing_rule: ExecutionTimingRule | None = Field(
        default=None,
        description="Explicit paper-side execution timing rule when recorded.",
    )
    fill_assumption: FillAssumption | None = Field(
        default=None,
        description="Explicit paper-side fill assumption when recorded.",
    )
    cost_model: CostModel | None = Field(
        default=None,
        description="Explicit paper-side cost model when recorded.",
    )
    realism_warnings: list[RealismWarning] = Field(
        default_factory=list,
        description="Structured realism warnings recorded for the paper path.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Data-quality artifact storage locations written while validating paper-trade creation.",
    )


class PaperExecutionService(BaseService):
    """Create human-reviewable paper trades without any live execution path."""

    capability_name = "paper_execution"
    capability_description = "Translates approved portfolio proposals into paper-only trade candidates."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["PortfolioProposal"],
            produces=["PaperTrade"],
            api_routes=["GET /portfolio/paper-trades"],
        )

    def propose_trades(
        self,
        request: PaperTradeProposalRequest,
        *,
        output_root: Path | None = None,
    ) -> PaperTradeProposalResponse:
        """Create Day 7 paper-trade candidates from an approved proposal."""

        proposal = request.portfolio_proposal
        notes: list[str] = []
        quality_service = DataQualityService(clock=self.clock)
        reconciliation_root = (
            resolve_artifact_workspace_from_stage_root(output_root).reconciliation_root
            if output_root is not None
            else None
        )
        trade_batch_id = make_prefixed_id("tradebatch")
        pre_validation = quality_service.validate_paper_trade_request(
            portfolio_proposal=proposal,
            proposed_trades=None,
            workflow_run_id=trade_batch_id,
            requested_by=request.requested_by,
            output_root=output_root,
            raise_on_failure=False,
        )
        storage_locations = list(pre_validation.storage_locations)

        def build_realism_bundle(*, proposed_trades: list[PaperTrade]) -> tuple[
            ExecutionTimingRule,
            FillAssumption,
            CostModel,
            list[RealismWarning],
            list[ArtifactStorageLocation],
            list[str],
        ]:
            realism_bundle = BacktestReconciliationService(clock=self.clock).build_paper_realism_context(
                portfolio_proposal=proposal,
                proposed_trades=proposed_trades,
                trade_batch_id=trade_batch_id,
                output_root=reconciliation_root,
                workflow_run_id=trade_batch_id,
            )
            return (
                realism_bundle.execution_timing_rule,
                realism_bundle.fill_assumption,
                realism_bundle.cost_model,
                realism_bundle.realism_warnings,
                realism_bundle.storage_locations,
                realism_bundle.notes,
            )

        if proposal.status is not PortfolioProposalStatus.APPROVED:
            (
                execution_timing_rule,
                fill_assumption,
                cost_model,
                realism_warnings,
                realism_storage_locations,
                realism_notes,
            ) = build_realism_bundle(proposed_trades=[])
            storage_locations.extend(realism_storage_locations)
            notes.append(
                "Portfolio proposal is not approved, so zero paper-trade candidates were created."
            )
            notes.append(
                "This is a review-bound stop, not a silent success or autonomous execution path."
            )
            notes.append(f"proposal_status={proposal.status.value}")
            notes.extend(realism_notes)
            return PaperTradeProposalResponse(
                trade_batch_id=trade_batch_id,
                proposed_trades=[],
                review_required=True,
                notes=notes,
                validation_gate=pre_validation.validation_gate,
                quality_decision=pre_validation.validation_gate.decision,
                refusal_reason=pre_validation.validation_gate.refusal_reason,
                execution_timing_rule=execution_timing_rule,
                fill_assumption=fill_assumption,
                cost_model=cost_model,
                realism_warnings=realism_warnings,
                storage_locations=storage_locations,
            )
        if proposal.blocking_issues or any(check.blocking for check in proposal.risk_checks):
            (
                execution_timing_rule,
                fill_assumption,
                cost_model,
                realism_warnings,
                realism_storage_locations,
                realism_notes,
            ) = build_realism_bundle(proposed_trades=[])
            storage_locations.extend(realism_storage_locations)
            notes.append("Proposal has blocking risk checks and cannot create paper trades.")
            notes.append(
                "This is a blocked stop, not the normal review-bound zero-trade outcome."
            )
            notes.extend(realism_notes)
            return PaperTradeProposalResponse(
                trade_batch_id=trade_batch_id,
                proposed_trades=[],
                review_required=True,
                notes=notes,
                validation_gate=pre_validation.validation_gate,
                quality_decision=pre_validation.validation_gate.decision,
                refusal_reason=pre_validation.validation_gate.refusal_reason,
                execution_timing_rule=execution_timing_rule,
                fill_assumption=fill_assumption,
                cost_model=cost_model,
                realism_warnings=realism_warnings,
                storage_locations=storage_locations,
            )

        now = self.clock.now()
        trades: list[PaperTrade] = []
        for idea in proposal.position_ideas:
            if idea.side is PositionSide.FLAT:
                continue
            reference_price = request.assumed_reference_prices.get(idea.symbol)
            notional_usd = proposal.target_nav_usd * abs(idea.proposed_weight_bps) / 10_000.0
            quantity = (
                notional_usd / reference_price
                if reference_price is not None and reference_price > 0.0
                else None
            )
            trades.append(
                PaperTrade(
                    paper_trade_id=make_canonical_id(
                        "trade",
                        proposal.portfolio_proposal_id,
                        idea.position_idea_id,
                    ),
                    portfolio_proposal_id=proposal.portfolio_proposal_id,
                    position_idea_id=idea.position_idea_id,
                    symbol=idea.symbol,
                    side=idea.side,
                    execution_mode="paper_only",
                    quantity=quantity,
                    notional_usd=notional_usd,
                    assumed_reference_price_usd=reference_price,
                    time_in_force="day",
                    status=PaperTradeStatus.PROPOSED,
                    submitted_at=now,
                    approved_at=None,
                    simulated_fill_at=None,
                    requested_by=request.requested_by,
                    approved_by=None,
                    review_decision_ids=[],
                    execution_notes=[
                        "Simulated only. No live routing.",
                        "Trade candidate requires separate human review.",
                        f"proposal_status={proposal.status.value}",
                        *(
                            [f"portfolio_selection_summary_id={proposal.portfolio_selection_summary_id}"]
                            if proposal.portfolio_selection_summary_id is not None
                            else []
                        ),
                        *(
                            [f"construction_decision_id={idea.construction_decision_id}"]
                            if idea.construction_decision_id is not None
                            else []
                        ),
                        *(
                            [f"position_sizing_rationale_id={idea.position_sizing_rationale_id}"]
                            if idea.position_sizing_rationale_id is not None
                            else []
                        ),
                    ],
                    slippage_bps_estimate=5.0,
                    provenance=build_provenance(
                        clock=self.clock,
                        transformation_name="day7_paper_trade_translation",
                        source_reference_ids=idea.provenance.source_reference_ids,
                        upstream_artifact_ids=[
                            proposal.portfolio_proposal_id,
                            idea.position_idea_id,
                            idea.signal_id,
                            *(
                                [proposal.portfolio_selection_summary_id]
                                if proposal.portfolio_selection_summary_id is not None
                                else []
                            ),
                            *(
                                [idea.construction_decision_id]
                                if idea.construction_decision_id is not None
                                else []
                            ),
                            *(
                                [idea.position_sizing_rationale_id]
                                if idea.position_sizing_rationale_id is not None
                                else []
                            ),
                        ],
                        notes=[
                            "execution_mode=paper_only",
                            (
                                f"reference_price_used={reference_price:.4f}"
                                if reference_price is not None
                                else "reference_price_used=none"
                            ),
                        ],
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
        (
            execution_timing_rule,
            fill_assumption,
            cost_model,
            realism_warnings,
            realism_storage_locations,
            realism_notes,
        ) = build_realism_bundle(proposed_trades=trades)
        storage_locations.extend(realism_storage_locations)
        notes.extend(realism_notes)
        trades = [
            trade.model_copy(
                update={
                    "execution_timing_rule_id": execution_timing_rule.execution_timing_rule_id,
                    "fill_assumption_id": fill_assumption.fill_assumption_id,
                    "cost_model_id": cost_model.cost_model_id,
                    "slippage_bps_estimate": (
                        cost_model.slippage_bps
                        if cost_model.slippage_bps is not None
                        else trade.slippage_bps_estimate
                    ),
                    "execution_notes": [
                        *trade.execution_notes,
                        f"execution_timing_rule_id={execution_timing_rule.execution_timing_rule_id}",
                        f"fill_assumption_id={fill_assumption.fill_assumption_id}",
                        f"cost_model_id={cost_model.cost_model_id}",
                    ],
                    "updated_at": now,
                }
            )
            for trade in trades
        ]
        if not trades:
            notes.append("No directional position ideas were eligible for paper-trade creation.")
        post_validation = quality_service.validate_paper_trade_request(
            portfolio_proposal=proposal,
            proposed_trades=trades,
            workflow_run_id=trade_batch_id,
            requested_by=request.requested_by,
            output_root=output_root,
            raise_on_failure=False,
        )
        storage_locations.extend(post_validation.storage_locations)
        if post_validation.validation_gate.decision in {
            QualityDecision.REFUSE,
            QualityDecision.QUARANTINE,
        }:
            notes.append(
                "Generated paper-trade candidates were blocked by data-quality validation and were not returned."
            )
            notes.append(
                "This is a blocked stop, not the normal review-bound zero-trade outcome."
            )
            return PaperTradeProposalResponse(
                trade_batch_id=trade_batch_id,
                proposed_trades=[],
                review_required=True,
                notes=notes,
                validation_gate=post_validation.validation_gate,
                quality_decision=post_validation.validation_gate.decision,
                refusal_reason=post_validation.validation_gate.refusal_reason,
                execution_timing_rule=execution_timing_rule,
                fill_assumption=fill_assumption,
                cost_model=cost_model,
                realism_warnings=realism_warnings,
                storage_locations=storage_locations,
            )
        return PaperTradeProposalResponse(
            trade_batch_id=trade_batch_id,
            proposed_trades=trades,
            review_required=True,
            notes=notes,
            validation_gate=post_validation.validation_gate,
            quality_decision=post_validation.validation_gate.decision,
            refusal_reason=post_validation.validation_gate.refusal_reason,
            execution_timing_rule=execution_timing_rule,
            fill_assumption=fill_assumption,
            cost_model=cost_model,
            realism_warnings=realism_warnings,
            storage_locations=storage_locations,
        )
