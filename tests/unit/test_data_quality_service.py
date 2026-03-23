from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from libraries.schemas import (
    AblationView,
    Company,
    CounterHypothesis,
    CritiqueKind,
    DataLayer,
    DerivedArtifactValidationStatus,
    DocumentStatus,
    EvidenceAssessment,
    EvidenceGrade,
    EvidenceLinkRole,
    ExperimentConfig,
    ExperimentParameter,
    ExperimentParameterValueType,
    Feature,
    FeatureDefinition,
    FeatureFamily,
    FeatureLineage,
    FeatureStatus,
    FeatureValue,
    FeatureValueType,
    Filing,
    FilingForm,
    Hypothesis,
    HypothesisStatus,
    PortfolioExposureSummary,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionIdea,
    PositionIdeaStatus,
    PositionSide,
    ProvenanceRecord,
    QualityDecision,
    RefusalReason,
    ResearchBrief,
    ResearchReviewStatus,
    ResearchStance,
    ResearchValidationStatus,
    Signal,
    SignalLineage,
    SignalScore,
    SignalStatus,
    SourceReference,
    SourceType,
    SupportingEvidenceLink,
)
from libraries.time import FrozenClock
from services.data_quality import DataQualityService
from services.feature_store.loaders import LoadedFeatureMappingInputs
from services.paper_execution import PaperExecutionService, PaperTradeProposalRequest

FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


def test_normalized_document_gate_quarantines_missing_required_timestamp(
    tmp_path: Path,
) -> None:
    service = DataQualityService(clock=FrozenClock(FIXED_NOW))
    result = service.validate_ingestion_normalization(
        source_reference=_source_reference(with_timing=False),
        company=_company(),
        document=_filing(with_timing=False),
        workflow_run_id="ingest_test",
        requested_by="unit_test",
        output_root=tmp_path,
        raise_on_failure=False,
    )

    assert result.validation_gate.decision is QualityDecision.QUARANTINE
    assert result.validation_gate.refusal_reason is RefusalReason.MISSING_REQUIRED_TIMESTAMP
    assert result.validation_gate.quarantined is True
    assert any(
        violation.refusal_reason is RefusalReason.MISSING_REQUIRED_TIMESTAMP
        for violation in result.contract_violations
    )
    assert (tmp_path / "validation_gates" / f"{result.validation_gate.validation_gate_id}.json").exists()


def test_provenance_omission_records_blocking_contract_violation(tmp_path: Path) -> None:
    service = DataQualityService(clock=FrozenClock(FIXED_NOW))
    result = service.validate_ingestion_normalization(
        source_reference=_source_reference(provenance=_incomplete_provenance()),
        company=_company(provenance=_incomplete_provenance()),
        document=_filing(provenance=_incomplete_provenance()),
        workflow_run_id="ingest_test",
        requested_by="unit_test",
        output_root=tmp_path,
        raise_on_failure=False,
    )

    provenance_violations = [
        violation
        for violation in result.contract_violations
        if violation.refusal_reason is RefusalReason.MISSING_PROVENANCE
    ]
    assert provenance_violations
    assert all(violation.blocking for violation in provenance_violations)


def test_feature_mapping_input_gate_refuses_invalid_review_state(tmp_path: Path) -> None:
    service = DataQualityService(clock=FrozenClock(FIXED_NOW))
    result = service.validate_feature_mapping_inputs(
        inputs=LoadedFeatureMappingInputs(
            company_id="co_test",
            hypothesis=_hypothesis(review_status=ResearchReviewStatus.REJECTED),
            counter_hypothesis=_counter_hypothesis(),
            evidence_assessment=_evidence_assessment(),
            research_brief=_research_brief(),
            guidance_changes=[],
            risk_factors=[],
            tone_markers=[],
            document_availability_windows=[],
        ),
        workflow_run_id="fmap_test",
        requested_by="unit_test",
        output_root=tmp_path,
        raise_on_failure=False,
    )

    assert result.validation_gate.decision is QualityDecision.REFUSE
    assert result.validation_gate.refusal_reason is RefusalReason.INVALID_REVIEW_STATE
    assert any(
        violation.refusal_reason is RefusalReason.INVALID_REVIEW_STATE
        for violation in result.contract_violations
    )


def test_signal_gate_blocks_broken_lineage(tmp_path: Path) -> None:
    service = DataQualityService(clock=FrozenClock(FIXED_NOW))
    feature = _feature()
    score = _signal_score(source_feature_ids=["feat_missing"])
    signal = _signal(
        feature_ids=[feature.feature_id],
        lineage_feature_ids=["feat_other"],
        component_scores=[score],
    )

    result = service.validate_signal_generation(
        company_id="co_test",
        features=[feature],
        signals=[signal],
        signal_scores=[score],
        workflow_run_id="sgen_test",
        requested_by="unit_test",
        output_root=tmp_path,
        raise_on_failure=False,
    )

    assert result.validation_gate.decision is QualityDecision.QUARANTINE
    assert result.validation_gate.refusal_reason is RefusalReason.BROKEN_SIGNAL_LINEAGE
    assert any(
        violation.refusal_reason is RefusalReason.BROKEN_SIGNAL_LINEAGE
        for violation in result.contract_violations
    )


def test_paper_trade_gate_records_structured_refusal_on_unapproved_proposals(
    tmp_path: Path,
) -> None:
    service = PaperExecutionService(clock=FrozenClock(FIXED_NOW))
    response = service.propose_trades(
        PaperTradeProposalRequest(
            portfolio_proposal=_portfolio_proposal(status=PortfolioProposalStatus.PENDING_REVIEW),
            requested_by="unit_test",
        ),
        output_root=tmp_path,
    )

    assert response.proposed_trades == []
    assert response.validation_gate is not None
    assert response.quality_decision is QualityDecision.REFUSE
    assert response.refusal_reason is RefusalReason.INVALID_REVIEW_STATE
    assert "paper_trade_stop_kind=review_bound" in response.notes
    assert response.storage_locations


def test_experiment_metadata_gate_refuses_empty_dataset_references(tmp_path: Path) -> None:
    service = DataQualityService(clock=FrozenClock(FIXED_NOW))
    result = service.validate_experiment_metadata(
        experiment_name="exp_test",
        created_by="unit_test",
        experiment_config=_experiment_config(),
        dataset_references=[],
        workflow_run_id="exp_run_test",
        requested_by="unit_test",
        output_root=tmp_path,
        raise_on_failure=False,
    )

    assert result.validation_gate.decision is QualityDecision.REFUSE
    assert result.validation_gate.refusal_reason is RefusalReason.INCOMPLETE_EXPERIMENT_METADATA
    assert any(
        violation.refusal_reason is RefusalReason.INCOMPLETE_EXPERIMENT_METADATA
        for violation in result.contract_violations
    )


def _complete_provenance() -> ProvenanceRecord:
    return ProvenanceRecord(
        source_reference_ids=["src_test"],
        upstream_artifact_ids=["artifact_test"],
        transformation_name="unit_test",
        processing_time=FIXED_NOW,
    )


def _incomplete_provenance() -> ProvenanceRecord:
    return ProvenanceRecord(
        source_reference_ids=[],
        upstream_artifact_ids=[],
        transformation_name=None,
        processing_time=None,
    )


def _source_reference(
    *,
    with_timing: bool = True,
    provenance: ProvenanceRecord | None = None,
) -> SourceReference:
    return SourceReference(
        source_reference_id="src_test",
        source_type=SourceType.SEC_EDGAR,
        uri="https://example.com/filing",
        published_at=FIXED_NOW if with_timing else None,
        effective_at=FIXED_NOW if with_timing else None,
        provenance=provenance or _complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _company(*, provenance: ProvenanceRecord | None = None) -> Company:
    return Company(
        company_id="co_test",
        legal_name="Test Company",
        ticker="TEST",
        provenance=provenance or _complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _filing(
    *,
    with_timing: bool = True,
    provenance: ProvenanceRecord | None = None,
) -> Filing:
    return Filing(
        document_id="doc_test",
        company_id="co_test",
        title="Test Filing",
        source_reference_id="src_test",
        data_layer=DataLayer.NORMALIZED,
        language="en",
        source_published_at=FIXED_NOW if with_timing else None,
        effective_at=FIXED_NOW if with_timing else None,
        ingested_at=FIXED_NOW,
        processed_at=FIXED_NOW,
        status=DocumentStatus.NORMALIZED,
        tags=["filing"],
        provenance=provenance or _complete_provenance(),
        form_type=FilingForm.FORM_10Q,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _supporting_link() -> SupportingEvidenceLink:
    return SupportingEvidenceLink(
        supporting_evidence_link_id="sel_test",
        source_reference_id="src_test",
        document_id="doc_test",
        evidence_span_id="esp_test",
        role=EvidenceLinkRole.SUPPORT,
        quote="Exact quoted evidence.",
        provenance=_complete_provenance(),
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
        support_summary="Support is adequate for candidate research work.",
        key_gaps=["Need fresh follow-up evidence."],
        contradiction_notes=[],
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        provenance=_complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _hypothesis(
    *,
    review_status: ResearchReviewStatus = ResearchReviewStatus.PENDING_HUMAN_REVIEW,
) -> Hypothesis:
    return Hypothesis(
        hypothesis_id="hyp_test",
        company_id="co_test",
        title="Test Hypothesis",
        thesis="The business is improving.",
        stance=ResearchStance.POSITIVE,
        status=HypothesisStatus.UNDER_REVIEW,
        review_status=review_status,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        time_horizon="next_2_4_quarters",
        supporting_evidence_links=[_supporting_link()],
        assumptions=["Margins continue to expand."],
        uncertainties=["Demand may weaken."],
        validation_steps=["Check the next earnings release."],
        evidence_assessment_id="eass_test",
        provenance=_complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _counter_hypothesis() -> CounterHypothesis:
    return CounterHypothesis(
        counter_hypothesis_id="counter_test",
        hypothesis_id="hyp_test",
        title="Test Counter",
        thesis="The apparent improvement may reverse.",
        critique_kinds=[CritiqueKind.CAUSAL_GAP],
        supporting_evidence_links=[_supporting_link()],
        challenged_assumptions=["Margins are not stable."],
        missing_evidence=[],
        causal_gaps=[],
        unresolved_questions=[],
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        provenance=_complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _research_brief() -> ResearchBrief:
    return ResearchBrief(
        research_brief_id="brief_test",
        company_id="co_test",
        title="Test Brief",
        context_summary="Context summary.",
        core_hypothesis="Core hypothesis.",
        counter_hypothesis_summary="Counter summary.",
        hypothesis_id="hyp_test",
        counter_hypothesis_id="counter_test",
        evidence_assessment_id="eass_test",
        supporting_evidence_links=[_supporting_link()],
        key_counterarguments=["Execution risk remains."],
        uncertainty_summary="Material uncertainty remains visible.",
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        next_validation_steps=["Review next filing."],
        provenance=_complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _feature() -> Feature:
    feature_definition = FeatureDefinition(
        feature_definition_id="fdef_test",
        name="support_grade_score",
        family=FeatureFamily.TEXT_DERIVED,
        value_type=FeatureValueType.NUMERIC,
        description="Support-grade feature.",
        ablation_views=[AblationView.TEXT_ONLY],
        status=FeatureStatus.PROVISIONAL,
        validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
        provenance=_complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    feature_value = FeatureValue(
        feature_value_id="fval_test",
        feature_definition_id="fdef_test",
        as_of_date=date(2026, 3, 22),
        available_at=FIXED_NOW,
        numeric_value=0.6,
        provenance=_complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    return Feature(
        feature_id="feat_test",
        entity_id="co_test",
        company_id="co_test",
        data_layer=DataLayer.DERIVED,
        feature_definition=feature_definition,
        feature_value=feature_value,
        status=FeatureStatus.PROVISIONAL,
        validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
        lineage=FeatureLineage(
            feature_lineage_id="flin_test",
            hypothesis_id="hyp_test",
            counter_hypothesis_id="counter_test",
            evidence_assessment_id="eass_test",
            research_brief_id="brief_test",
            supporting_evidence_link_ids=["sel_test"],
            source_document_ids=["doc_test"],
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        assumptions=["Candidate-only feature."],
        provenance=_complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _signal_score(*, source_feature_ids: list[str]) -> SignalScore:
    return SignalScore(
        signal_score_id="sscore_test",
        metric_name="support_grade_component",
        value=0.6,
        scale_min=0.0,
        scale_max=1.0,
        validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
        source_feature_ids=source_feature_ids,
        assumptions=["Rule-based placeholder."],
        provenance=_complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _signal(
    *,
    feature_ids: list[str],
    lineage_feature_ids: list[str],
    component_scores: list[SignalScore],
) -> Signal:
    return Signal(
        signal_id="sig_test",
        company_id="co_test",
        hypothesis_id="hyp_test",
        signal_family="text_only_candidate_signal",
        stance=ResearchStance.POSITIVE,
        ablation_view=AblationView.TEXT_ONLY,
        thesis_summary="Test signal.",
        feature_ids=feature_ids,
        component_scores=component_scores,
        primary_score=0.4,
        effective_at=FIXED_NOW,
        expires_at=None,
        status=SignalStatus.CANDIDATE,
        validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
        lineage=SignalLineage(
            signal_lineage_id="slin_test",
            feature_ids=lineage_feature_ids,
            feature_definition_ids=["fdef_test"],
            feature_value_ids=["fval_test"],
            research_artifact_ids=["hyp_test", "counter_test", "eass_test", "brief_test"],
            supporting_evidence_link_ids=["sel_test"],
            input_families=[FeatureFamily.TEXT_DERIVED],
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        assumptions=["Candidate-only signal."],
        uncertainties=["Still unvalidated."],
        provenance=_complete_provenance(),
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
        thesis_summary="Test position idea.",
        selection_reason="Selected from raw signal for unit testing.",
        entry_conditions=[],
        exit_conditions=[],
        target_horizon="next_quarter",
        proposed_weight_bps=300,
        max_weight_bps=500,
        evidence_span_ids=["esp_test"],
        supporting_evidence_link_ids=["sel_test"],
        research_artifact_ids=["hyp_test"],
        review_decision_ids=[],
        status=PositionIdeaStatus.PENDING_REVIEW,
        provenance=_complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _portfolio_proposal(*, status: PortfolioProposalStatus) -> PortfolioProposal:
    idea = _position_idea()
    return PortfolioProposal(
        portfolio_proposal_id="proposal_test",
        name="Test Proposal",
        as_of_time=FIXED_NOW,
        generated_at=FIXED_NOW,
        target_nav_usd=1_000_000.0,
        position_ideas=[idea],
        constraints=[],
        risk_checks=[],
        exposure_summary=PortfolioExposureSummary(
            portfolio_exposure_summary_id="pexpo_test",
            gross_exposure_bps=300,
            net_exposure_bps=300,
            long_exposure_bps=300,
            short_exposure_bps=0,
            cash_buffer_bps=9_700,
            position_count=1,
            turnover_bps_assumption=300,
            provenance=_complete_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        blocking_issues=[],
        review_decision_ids=[],
        review_required=True,
        status=status,
        summary="One-position unit-test proposal.",
        provenance=_complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _experiment_config() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_config_id="expcfg_test",
        workflow_name="backtest_workflow",
        workflow_version="v1",
        parameter_hash="hash_test",
        parameters=[
            ExperimentParameter(
                experiment_parameter_id="param_test",
                key="lookback_days",
                value_repr="20",
                value_type=ExperimentParameterValueType.INTEGER,
                provenance=_complete_provenance(),
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        ],
        provenance=_complete_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
