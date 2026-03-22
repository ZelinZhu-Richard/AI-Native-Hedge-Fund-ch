from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from libraries.schemas import (
    AblationView,
    ConfidenceAssessment,
    DerivedArtifactValidationStatus,
    DocumentKind,
    EvidenceAssessment,
    EvidenceGrade,
    EvidenceLinkRole,
    Experiment,
    ExperimentStatus,
    FeatureFamily,
    PaperTrade,
    PaperTradeStatus,
    ParsedDocumentText,
    PortfolioExposureSummary,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionIdea,
    PositionIdeaStatus,
    PositionSide,
    ResearchBrief,
    ResearchReviewStatus,
    ResearchStance,
    ResearchValidationStatus,
    RiskCheck,
    RiskCheckStatus,
    RunSummary,
    Severity,
    Signal,
    SignalLineage,
    SignalScore,
    SignalStatus,
    StrictModel,
    SupportingEvidenceLink,
    WorkflowStatus,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.time import FrozenClock
from services.red_team.checks import LoadedRedTeamWorkspace, execute_red_team_scenario
from services.red_team.service import RedTeamService, RunRedTeamSuiteRequest

FIXED_NOW = datetime(2026, 3, 19, 15, 0, tzinfo=UTC)
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "red_team"


def test_unsupported_causal_claim_case_records_blocking_violation() -> None:
    workspace = _workspace()
    payload = json.loads((FIXTURE_ROOT / "unsupported_claim_payload.json").read_text(encoding="utf-8"))
    workspace.signals[0] = workspace.signals[0].model_copy(
        update={
            "thesis_summary": payload["summary"],
            "confidence": ConfidenceAssessment(
                confidence=payload["confidence"],
                uncertainty=payload["uncertainty"],
            ),
            "uncertainties": [],
        }
    )

    result = execute_red_team_scenario(
        scenario_name="unsupported_causal_claim",
        workspace=workspace,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="rtsuite_unit",
    )

    assert result is not None
    assert result.red_team_case.scenario_name == "unsupported_causal_claim"
    assert result.guardrail_violations[0].guardrail_name == "claim_strength_matches_support"
    assert result.guardrail_violations[0].blocking is True
    assert "must buy" in result.guardrail_violations[0].message.lower()


def test_malformed_portfolio_case_records_mitigation() -> None:
    workspace = _workspace()
    payload = json.loads(
        (FIXTURE_ROOT / "malformed_portfolio_payload.json").read_text(encoding="utf-8")
    )
    workspace.portfolio_proposals[0] = workspace.portfolio_proposals[0].model_copy(
        update={
            "status": PortfolioProposalStatus(payload["status"]),
            "position_ideas": payload["position_ideas"],
            "risk_checks": payload["risk_checks"],
            "review_decision_ids": payload["review_decision_ids"],
            "blocking_issues": payload["blocking_issues"],
        }
    )

    result = execute_red_team_scenario(
        scenario_name="malformed_portfolio_inputs",
        workspace=workspace,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="rtsuite_unit",
    )

    assert result is not None
    violation = result.guardrail_violations[0]
    assert violation.guardrail_name == "review_bypass_detected"
    assert violation.recommended_mitigations[0].blocking is True


def test_paper_trade_and_experiment_cases_use_fixture_payloads() -> None:
    workspace = _workspace()
    trade_payload = json.loads(
        (FIXTURE_ROOT / "paper_trade_approval_gap.json").read_text(encoding="utf-8")
    )
    experiment_payload = json.loads(
        (FIXTURE_ROOT / "experiment_missing_references.json").read_text(encoding="utf-8")
    )
    workspace.paper_trades[0] = workspace.paper_trades[0].model_copy(
        update={
            "status": PaperTradeStatus(trade_payload["status"]),
            "approved_at": trade_payload["approved_at"],
            "approved_by": trade_payload["approved_by"],
            "review_decision_ids": trade_payload["review_decision_ids"],
        }
    )
    workspace.experiments[0] = workspace.experiments[0].model_copy(
        update=experiment_payload
    )

    paper_trade_result = execute_red_team_scenario(
        scenario_name="paper_trade_missing_approval_state",
        workspace=workspace,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="rtsuite_unit",
    )
    experiment_result = execute_red_team_scenario(
        scenario_name="evaluation_missing_references",
        workspace=workspace,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="rtsuite_unit",
    )

    assert paper_trade_result is not None
    assert experiment_result is not None
    assert (
        paper_trade_result.guardrail_violations[0].guardrail_name
        == "paper_trade_approval_state_complete"
    )
    assert (
        experiment_result.guardrail_violations[0].guardrail_name
        == "evaluation_references_complete"
    )


def test_red_team_service_persists_outputs_and_monitoring(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    _persist_workspace(_workspace(), artifact_root=artifact_root)

    response = RedTeamService(clock=FrozenClock(FIXED_NOW)).run_red_team_suite(
        RunRedTeamSuiteRequest(
            parsing_root=artifact_root / "parsing",
            research_root=artifact_root / "research",
            signal_root=artifact_root / "signal_generation",
            portfolio_root=artifact_root / "portfolio",
            experiment_root=artifact_root / "experiments",
            review_root=artifact_root / "review",
            output_root=artifact_root / "red_team",
            monitoring_root=artifact_root / "monitoring",
            audit_root=artifact_root / "audit",
            requested_by="unit_test",
        )
    )

    assert response.red_team_cases
    assert response.guardrail_violations
    assert response.safety_findings
    assert response.run_summary is not None
    assert response.run_summary.status is WorkflowStatus.FAILED
    assert response.alert_records
    assert (artifact_root / "red_team" / "cases").exists()
    assert (artifact_root / "red_team" / "guardrail_violations").exists()
    assert (artifact_root / "red_team" / "safety_findings").exists()
    run_summaries = _load_models(artifact_root / "monitoring" / "run_summaries", RunSummary)
    assert run_summaries[-1].workflow_name == "red_team_suite"
    assert run_summaries[-1].produced_artifact_counts["cases"] == len(response.red_team_cases)


def test_red_team_service_infers_workspace_from_output_root(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    _persist_workspace(_workspace(), artifact_root=artifact_root)

    response = RedTeamService(clock=FrozenClock(FIXED_NOW)).run_red_team_suite(
        RunRedTeamSuiteRequest(
            output_root=artifact_root / "red_team",
            requested_by="unit_test",
        )
    )

    assert response.red_team_cases
    assert response.run_summary is not None
    assert (artifact_root / "monitoring" / "run_summaries").exists()
    assert (artifact_root / "audit" / "audit_logs").exists()


def test_red_team_service_rejects_mismatched_explicit_workspace_roots(tmp_path: Path) -> None:
    service = RedTeamService(clock=FrozenClock(FIXED_NOW))

    try:
        service.run_red_team_suite(
            RunRedTeamSuiteRequest(
                parsing_root=tmp_path / "workspace_one" / "parsing",
                output_root=tmp_path / "workspace_two" / "red_team",
                requested_by="unit_test",
            )
        )
    except ValueError as exc:
        assert "same artifact workspace" in str(exc)
    else:
        raise AssertionError("Expected mismatched explicit red-team roots to be rejected.")


def _workspace() -> LoadedRedTeamWorkspace:
    return LoadedRedTeamWorkspace(
        research_briefs=[_research_brief()],
        evidence_assessments=[_evidence_assessment()],
        signals=[_signal()],
        parsed_texts=[_parsed_text()],
        claims=[],
        portfolio_proposals=[_portfolio_proposal()],
        paper_trades=[_paper_trade()],
        review_decisions=[],
        experiments=[_experiment()],
    )


def _persist_workspace(workspace: LoadedRedTeamWorkspace, *, artifact_root: Path) -> None:
    research_brief = workspace.research_briefs[0]
    evidence_assessment = workspace.evidence_assessments[0]
    signal = workspace.signals[0]
    parsed_text = workspace.parsed_texts[0]
    proposal = workspace.portfolio_proposals[0]
    paper_trade = workspace.paper_trades[0]
    experiment = workspace.experiments[0]
    _write_model(
        artifact_root / "research" / "research_briefs",
        research_brief.research_brief_id,
        research_brief,
    )
    _write_model(
        artifact_root / "research" / "evidence_assessments",
        evidence_assessment.evidence_assessment_id,
        evidence_assessment,
    )
    _write_model(artifact_root / "signal_generation" / "signals", signal.signal_id, signal)
    _write_model(
        artifact_root / "parsing" / "parsed_text",
        parsed_text.parsed_document_text_id,
        parsed_text,
    )
    _write_model(
        artifact_root / "portfolio" / "portfolio_proposals",
        proposal.portfolio_proposal_id,
        proposal,
    )
    _write_model(
        artifact_root / "portfolio" / "paper_trades",
        paper_trade.paper_trade_id,
        paper_trade,
    )
    _write_model(
        artifact_root / "experiments" / "experiments",
        experiment.experiment_id,
        experiment,
    )
    (artifact_root / "review" / "review_decisions").mkdir(parents=True, exist_ok=True)


def _write_model(directory: Path, artifact_id: str, model: StrictModel) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{artifact_id}.json").write_text(model.model_dump_json(indent=2), encoding="utf-8")


def _load_models(directory: Path, model_cls: type[RunSummary]) -> list[RunSummary]:
    return [
        model_cls.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]


def _supporting_link() -> SupportingEvidenceLink:
    return SupportingEvidenceLink(
        supporting_evidence_link_id="sel_test",
        source_reference_id="src_test",
        document_id="doc_test",
        evidence_span_id="span_test",
        extracted_artifact_id=None,
        role=EvidenceLinkRole.SUPPORT,
        quote="Management maintained guidance.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _research_brief() -> ResearchBrief:
    return ResearchBrief(
        research_brief_id="brief_test",
        company_id="co_test",
        title="APEX research brief",
        context_summary="Current quarter context.",
        core_hypothesis="Execution remains on plan.",
        counter_hypothesis_summary="Demand may soften.",
        hypothesis_id="hyp_test",
        counter_hypothesis_id="counter_test",
        evidence_assessment_id="eass_test",
        supporting_evidence_links=[_supporting_link()],
        key_counterarguments=["Demand remains uncertain."],
        confidence=ConfidenceAssessment(confidence=0.55, uncertainty=0.45),
        uncertainty_summary="Demand remains uncertain.",
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        next_validation_steps=["Check next earnings call language."],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _evidence_assessment() -> EvidenceAssessment:
    return EvidenceAssessment(
        evidence_assessment_id="eass_test",
        company_id="co_test",
        hypothesis_id="hyp_test",
        grade=EvidenceGrade.MODERATE,
        supporting_evidence_link_ids=["sel_test"],
        support_summary="Support is moderate.",
        key_gaps=["Need another quarter of confirmation."],
        contradiction_notes=[],
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        confidence=ConfidenceAssessment(confidence=0.55, uncertainty=0.45),
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _signal() -> Signal:
    return Signal(
        signal_id="sig_test",
        company_id="co_test",
        hypothesis_id="hyp_test",
        signal_family="text_only_candidate_signal",
        stance=ResearchStance.POSITIVE,
        ablation_view=AblationView.TEXT_ONLY,
        thesis_summary="Execution remains on plan with moderate support.",
        feature_ids=["feat_test"],
        component_scores=[
            SignalScore(
                signal_score_id="score_test",
                metric_name="support_grade_component",
                value=0.6,
                scale_min=0.0,
                scale_max=1.0,
                validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
                source_feature_ids=["feat_test"],
                assumptions=["Unit test feature score."],
                rationale="Moderate support.",
                provenance=_provenance(),
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        ],
        primary_score=0.6,
        effective_at=FIXED_NOW,
        expires_at=FIXED_NOW.replace(hour=16),
        status=SignalStatus.CANDIDATE,
        validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
        lineage=SignalLineage(
            signal_lineage_id="slin_test",
            feature_ids=["feat_test"],
            feature_definition_ids=["fdef_test"],
            feature_value_ids=["fval_test"],
            research_artifact_ids=["hyp_test", "eass_test", "brief_test"],
            supporting_evidence_link_ids=["sel_test"],
            input_families=[FeatureFamily.TEXT_DERIVED],
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        assumptions=["Unit test signal assumption."],
        uncertainties=["Need more confirmation."],
        confidence=ConfidenceAssessment(confidence=0.55, uncertainty=0.45),
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _parsed_text() -> ParsedDocumentText:
    return ParsedDocumentText(
        parsed_document_text_id="pdtxt_test",
        document_id="doc_test",
        source_reference_id="src_test",
        company_id="co_test",
        document_kind=DocumentKind.DOCUMENT,
        canonical_text="Management maintained guidance and expects stable demand.",
        headline_text="Management maintained guidance",
        body_text="Stable demand remains expected.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _portfolio_proposal() -> PortfolioProposal:
    return PortfolioProposal(
        portfolio_proposal_id="proposal_test",
        name="Test proposal",
        as_of_time=FIXED_NOW,
        generated_at=FIXED_NOW,
        target_nav_usd=1_000_000.0,
        position_ideas=[_position_idea()],
        constraints=[],
        risk_checks=[_risk_check()],
        exposure_summary=PortfolioExposureSummary(
            portfolio_exposure_summary_id="pexpo_test",
            gross_exposure_bps=300,
            net_exposure_bps=300,
            long_exposure_bps=300,
            short_exposure_bps=0,
            cash_buffer_bps=9700,
            position_count=1,
            turnover_bps_assumption=300,
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        blocking_issues=[],
        review_decision_ids=[],
        review_required=True,
        status=PortfolioProposalStatus.PENDING_REVIEW,
        summary="Single long idea.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _position_idea() -> PositionIdea:
    return PositionIdea(
        position_idea_id="idea_test",
        company_id="co_test",
        signal_id="sig_test",
        symbol="TEST",
        instrument_type="equity",
        side=PositionSide.LONG,
        thesis_summary="Execution remains on plan.",
        selection_reason="Selected from candidate signal.",
        entry_conditions=[],
        exit_conditions=[],
        target_horizon="next_1_4_quarters",
        proposed_weight_bps=300,
        max_weight_bps=500,
        evidence_span_ids=["span_test"],
        supporting_evidence_link_ids=["sel_test"],
        research_artifact_ids=["hyp_test", "eass_test", "brief_test"],
        review_decision_ids=[],
        status=PositionIdeaStatus.PENDING_REVIEW,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _risk_check() -> RiskCheck:
    return RiskCheck(
        risk_check_id="risk_test",
        subject_type="portfolio_proposal",
        subject_id="proposal_test",
        portfolio_constraint_id=None,
        rule_name="single_name_limit",
        status=RiskCheckStatus.WARN,
        severity=Severity.MEDIUM,
        blocking=False,
        observed_value=None,
        limit_value=None,
        unit=None,
        message="Candidate signals remain review-bound.",
        checked_at=FIXED_NOW,
        reviewer_notes=[],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _paper_trade() -> PaperTrade:
    return PaperTrade(
        paper_trade_id="trade_test",
        portfolio_proposal_id="proposal_test",
        position_idea_id="idea_test",
        symbol="TEST",
        side=PositionSide.LONG,
        execution_mode="paper_only",
        quantity=10.0,
        notional_usd=1000.0,
        assumed_reference_price_usd=100.0,
        time_in_force="day",
        status=PaperTradeStatus.PROPOSED,
        submitted_at=FIXED_NOW,
        approved_at=None,
        simulated_fill_at=None,
        requested_by="unit_test",
        approved_by=None,
        review_decision_ids=[],
        execution_notes=[],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _experiment() -> Experiment:
    return Experiment(
        experiment_id="exp_test",
        name="test_experiment",
        objective="Unit test experiment.",
        created_by="unit_test",
        status=ExperimentStatus.COMPLETED,
        experiment_config_id="ecfg_test",
        run_context_id="rctx_test",
        dataset_reference_ids=["dref_test"],
        experiment_artifact_ids=["abres_test"],
        experiment_metric_ids=["metric_test"],
        started_at=FIXED_NOW,
        completed_at=FIXED_NOW.replace(hour=16),
        notes=[],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
