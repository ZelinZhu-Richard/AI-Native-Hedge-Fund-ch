from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from libraries.schemas import (
    AblationConfig,
    AblationView,
    BacktestConfig,
    BenchmarkKind,
    EvaluationSlice,
    EvidenceAssessment,
    EvidenceGrade,
    ExecutionAssumption,
    Feature,
    PortfolioExposureSummary,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionIdea,
    PositionIdeaStatus,
    PositionSide,
    ProvenanceRecord,
    Signal,
    SignalStatus,
    StrategyFamily,
    StrategySpec,
    StrategyVariant,
)
from libraries.time import FrozenClock
from libraries.utils import make_canonical_id
from pipelines.backtesting import run_backtest_pipeline, run_strategy_ablation_pipeline
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.signal_generation import (
    FeatureSignalPipelineResponse,
    run_feature_signal_pipeline,
)
from services.backtesting import (
    RunBacktestWorkflowResponse,
    RunStrategyAblationWorkflowResponse,
)
from services.backtesting.ablation import build_default_strategy_variants, build_strategy_specs
from services.evaluation.checks import (
    AblationVariantRunEvaluationInput,
    evaluate_backtest_artifact_completeness,
    evaluate_feature_lineage_completeness,
    evaluate_hypothesis_support_quality,
    evaluate_provenance_completeness,
    evaluate_risk_review_coverage,
    evaluate_signal_generation_validity,
    robustness_invalid_strategy_config,
)
from services.research_orchestrator import RunResearchWorkflowResponse

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
PRICE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "backtesting"
    / "apex_synthetic_daily_prices.json"
)
FIXED_NOW = datetime(2026, 3, 18, 10, 0, tzinfo=UTC)


@dataclass
class BuiltOutputs:
    artifact_root: Path
    research_response: RunResearchWorkflowResponse
    feature_signal_response: FeatureSignalPipelineResponse
    backtest_response: RunBacktestWorkflowResponse
    strategy_specs: list[StrategySpec]
    strategy_variants: list[StrategyVariant]
    ablation_config: AblationConfig
    ablation_response: RunStrategyAblationWorkflowResponse


@pytest.fixture(scope="module")
def built_outputs(tmp_path_factory: pytest.TempPathFactory) -> BuiltOutputs:
    artifact_root = tmp_path_factory.mktemp("evaluation_day10")
    clock = FrozenClock(FIXED_NOW)

    run_fixture_ingestion_pipeline(
        fixtures_root=FIXTURE_ROOT,
        output_root=artifact_root / "ingestion",
        clock=clock,
    )
    run_evidence_extraction_pipeline(
        ingestion_root=artifact_root / "ingestion",
        output_root=artifact_root / "parsing",
        clock=clock,
    )
    research_response = run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=clock,
    )
    feature_signal_response = run_feature_signal_pipeline(
        research_root=artifact_root / "research",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "signal_generation",
        clock=clock,
    )
    backtest_response = run_backtest_pipeline(
        signal_root=artifact_root / "signal_generation",
        feature_root=artifact_root / "signal_generation",
        output_root=artifact_root / "backtesting",
        experiment_root=artifact_root / "experiments",
        price_fixture_path=PRICE_FIXTURE_PATH,
        backtest_config=_backtest_config(),
        clock=clock,
    )
    strategy_specs = build_strategy_specs(
        families=[
            StrategyFamily.NAIVE_BASELINE,
            StrategyFamily.PRICE_ONLY_BASELINE,
            StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
            StrategyFamily.COMBINED_BASELINE,
        ],
        clock=clock,
        workflow_run_id="evaluation_service_fixture",
    )
    strategy_variants = build_default_strategy_variants(
        strategy_specs=strategy_specs,
        clock=clock,
        workflow_run_id="evaluation_service_fixture",
    )
    ablation_config = _ablation_config(
        strategy_variants=strategy_variants,
        company_id=feature_signal_response.signal_generation.company_id,
    )
    ablation_response = run_strategy_ablation_pipeline(
        signal_root=artifact_root / "signal_generation",
        feature_root=artifact_root / "signal_generation",
        output_root=artifact_root / "ablation",
        experiment_root=artifact_root / "experiments_ablation",
        evaluation_root=artifact_root / "evaluation",
        price_fixture_path=PRICE_FIXTURE_PATH,
        ablation_config=ablation_config,
        clock=clock,
    )
    return BuiltOutputs(
        artifact_root=artifact_root,
        research_response=research_response,
        feature_signal_response=feature_signal_response,
        backtest_response=backtest_response,
        strategy_specs=strategy_specs,
        strategy_variants=strategy_variants,
        ablation_config=ablation_config,
        ablation_response=ablation_response,
    )


def test_provenance_gaps_create_failures_and_zero_coverage(
    built_outputs: BuiltOutputs,
) -> None:
    feature_response = built_outputs.feature_signal_response
    feature = feature_response.feature_mapping.features[0]
    broken_feature = feature.model_copy(
        update={
            "provenance": feature.provenance.model_copy(
                update={
                    "processing_time": None,
                    "transformation_name": None,
                    "source_reference_ids": [],
                    "upstream_artifact_ids": [],
                    "data_snapshot_id": None,
                    "experiment_id": None,
                }
            )
        }
    )

    artifacts = evaluate_provenance_completeness(
        evaluation_report_id="evrep_provenance",
        target_type="feature_slice",
        target_id="feat_slice",
        artifacts=[broken_feature],
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="eval_provenance",
    )

    assert any(failure.failure_kind.value == "missing_provenance" for failure in artifacts.failure_cases)
    metric = next(metric for metric in artifacts.metrics if metric.metric_name == "provenance_complete_ratio")
    assert metric.metric_value.numeric_value == 0.0
    assert artifacts.coverage_summaries[0].coverage_ratio == 0.0


def test_hypothesis_support_quality_records_missing_and_weak_support(
    built_outputs: BuiltOutputs,
) -> None:
    research_response = built_outputs.research_response
    assert research_response.hypothesis is not None
    weak_hypothesis = research_response.hypothesis.model_copy(
        update={
            "supporting_evidence_links": [],
            "assumptions": [],
            "invalidation_conditions": [],
        }
    )
    weak_assessment: EvidenceAssessment = research_response.evidence_assessment.model_copy(
        update={"grade": EvidenceGrade.WEAK}
    )

    artifacts = evaluate_hypothesis_support_quality(
        evaluation_report_id="evrep_hypothesis",
        target_type="hypothesis_slice",
        target_id="hyp_slice",
        hypotheses=[weak_hypothesis],
        evidence_assessments=[weak_assessment],
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="eval_hypothesis",
    )

    failure_kinds = {failure.failure_kind.value for failure in artifacts.failure_cases}
    assert "missing_evidence" in failure_kinds
    assert "weak_support" in failure_kinds
    assert any(metric.metric_name.startswith("hypothesis_structure_present:") for metric in artifacts.metrics)


def test_feature_lineage_failures_are_recorded(
    built_outputs: BuiltOutputs,
) -> None:
    feature_response = built_outputs.feature_signal_response
    broken_feature: Feature = feature_response.feature_mapping.features[0].model_copy(
        update={
            "lineage": feature_response.feature_mapping.features[0].lineage.model_copy(
                update={
                    "supporting_evidence_link_ids": [],
                    "source_document_ids": [],
                }
            )
        }
    )

    artifacts = evaluate_feature_lineage_completeness(
        evaluation_report_id="evrep_feature",
        target_type="feature_slice",
        target_id="feat_slice",
        features=[broken_feature],
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="eval_feature",
    )

    assert any(failure.failure_kind.value == "broken_lineage" for failure in artifacts.failure_cases)
    metric = next(metric for metric in artifacts.metrics if metric.metric_name == "feature_lineage_complete_ratio")
    assert metric.metric_value.numeric_value == 0.0


def test_signal_generation_failures_are_recorded(
    built_outputs: BuiltOutputs,
) -> None:
    feature_response = built_outputs.feature_signal_response
    signal: Signal = feature_response.signal_generation.signals[0]
    broken_signal = signal.model_copy(
        update={
            "expires_at": signal.effective_at.replace(year=signal.effective_at.year - 1),
            "component_scores": [
                component_score.model_copy(update={"source_feature_ids": []})
                for component_score in signal.component_scores
            ],
            "uncertainties": [],
        }
    )
    features_by_id = {
        feature.feature_id: feature for feature in feature_response.feature_mapping.features
    }

    artifacts = evaluate_signal_generation_validity(
        evaluation_report_id="evrep_signal",
        target_type="signal_slice",
        target_id="sig_slice",
        signals=[broken_signal],
        features_by_id=features_by_id,
        known_signal_ids={signal.signal_id},
        snapshots_by_id={},
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="eval_signal",
    )

    failure_kinds = {failure.failure_kind.value for failure in artifacts.failure_cases}
    assert "invalid_timestamp" in failure_kinds
    assert "broken_lineage" in failure_kinds
    assert any(metric.metric_name.startswith("candidate_uncertainty_visible:") for metric in artifacts.metrics)


def test_backtest_completeness_and_experiment_linkage_failures_are_recorded(
    built_outputs: BuiltOutputs,
) -> None:
    backtest_response = built_outputs.backtest_response
    strategy_spec = _strategy_spec()
    strategy_variant = _strategy_variant(strategy_spec)
    variant_input = AblationVariantRunEvaluationInput(
        strategy_variant=strategy_variant,
        strategy_spec=strategy_spec,
        variant_signals=[],
        backtest_run=backtest_response.backtest_run.model_copy(
            update={"performance_summary_id": "psum_wrong"}
        ),
        performance_summary=backtest_response.performance_summary,
        benchmark_references=[],
        dataset_references=[],
        experiment=None,
    )

    artifacts = evaluate_backtest_artifact_completeness(
        evaluation_report_id="evrep_backtest",
        target_type="backtest_slice",
        target_id="btrun_slice",
        variant_runs=[variant_input],
        record_experiment_expected=True,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="eval_backtest",
    )

    failure_kinds = {failure.failure_kind.value for failure in artifacts.failure_cases}
    assert "empty_output" in failure_kinds
    assert "incomplete_config" in failure_kinds
    assert "broken_lineage" in failure_kinds
    experiment_metric = next(metric for metric in artifacts.metrics if metric.metric_name == "experiment_linkage_ratio")
    assert experiment_metric.metric_value.numeric_value == 0.0


def test_invalid_strategy_config_and_missing_risk_review_are_recorded(
    built_outputs: BuiltOutputs,
) -> None:
    strategy_variants = built_outputs.strategy_variants
    invalid_config = _ablation_config(
        strategy_variants=[strategy_variants[0], strategy_variants[0]],
        company_id="co_apex",
    ).model_copy(
        update={
            "shared_backtest_config": _backtest_config(test_end=date(2026, 3, 29)),
        }
    )
    invalid_strategy_check = robustness_invalid_strategy_config(
        evaluation_report_id="evrep_robustness",
        ablation_config=invalid_config,
        strategy_specs=built_outputs.strategy_specs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="eval_robustness",
    )
    proposal = _portfolio_proposal()
    risk_artifacts = evaluate_risk_review_coverage(
        evaluation_report_id="evrep_risk",
        portfolio_proposal=proposal,
        risk_checks=[],
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="eval_risk",
    )

    assert invalid_strategy_check.status.value == "fail"
    assert invalid_strategy_check.check_kind.value == "invalid_strategy_config"
    assert any(failure.failure_kind.value == "incomplete_config" for failure in risk_artifacts.failure_cases)


def _backtest_config(*, test_end: date = date(2026, 3, 30)) -> BacktestConfig:
    return BacktestConfig(
        backtest_config_id=make_canonical_id("btcfg", "day10_eval"),
        strategy_name="day10_eval_backtest",
        signal_family="text_only_candidate_signal_family",
        ablation_view=AblationView.TEXT_ONLY,
        test_start=date(2026, 3, 17),
        test_end=test_end,
        signal_status_allowlist=[SignalStatus.CANDIDATE],
        execution_assumption=ExecutionAssumption(
            execution_assumption_id=make_canonical_id("exec", "day10_eval"),
            transaction_cost_bps=5.0,
            slippage_bps=2.0,
            execution_lag_bars=1,
            decision_price_field="close",
            execution_price_field="open",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        benchmark_kinds=[BenchmarkKind.FLAT_BASELINE, BenchmarkKind.BUY_AND_HOLD],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _ablation_config(
    *, strategy_variants: list[StrategyVariant], company_id: str
) -> AblationConfig:
    return AblationConfig(
        ablation_config_id=make_canonical_id("abcfg", "day10_eval"),
        name="day10_eval_ablation",
        strategy_variants=strategy_variants,
        evaluation_slice=EvaluationSlice(
            evaluation_slice_id=make_canonical_id("eslice", "day10_eval"),
            company_id=company_id,
            test_start=date(2026, 3, 17),
            test_end=date(2026, 3, 30),
            decision_frequency="daily",
            price_fixture_path=str(PRICE_FIXTURE_PATH),
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        ),
        shared_backtest_config=_backtest_config(),
        comparison_metric_name="net_pnl",
        requested_by="unit_test",
        notes=["Day 10 evaluation fixture."],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _strategy_spec() -> StrategySpec:
    return StrategySpec(
        strategy_spec_id="sspec_eval",
        name="text_only_candidate_baseline",
        family=StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
        description="Synthetic spec for evaluation coverage.",
        signal_family="text_only_candidate_signal_family",
        required_inputs=["candidate_signals"],
        decision_rule_name="adapt_candidate_signals",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _strategy_variant(strategy_spec: StrategySpec) -> StrategyVariant:
    return StrategyVariant(
        strategy_variant_id="svar_eval",
        strategy_spec_id=strategy_spec.strategy_spec_id,
        variant_name="text_only_candidate_baseline",
        family=strategy_spec.family,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _portfolio_proposal() -> PortfolioProposal:
    return PortfolioProposal(
        portfolio_proposal_id="proposal_eval",
        name="Evaluation Proposal",
        as_of_time=FIXED_NOW,
        generated_at=FIXED_NOW,
        position_ideas=[_position_idea()],
        constraints=[],
        risk_checks=[],
        exposure_summary=PortfolioExposureSummary(
            portfolio_exposure_summary_id="pexpo_eval",
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
        review_required=True,
        status=PortfolioProposalStatus.PENDING_REVIEW,
        summary="Single reviewable candidate position.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _position_idea() -> PositionIdea:
    return PositionIdea(
        position_idea_id="idea_eval",
        company_id="co_apex",
        signal_id="sig_eval",
        symbol="APEX",
        instrument_type="equity",
        side=PositionSide.LONG,
        thesis_summary="Evaluation position idea.",
        selection_reason="Used to exercise Day 10 risk review coverage.",
        entry_conditions=[],
        exit_conditions=[],
        target_horizon="next_1_4_quarters",
        proposed_weight_bps=300,
        max_weight_bps=500,
        evidence_span_ids=["esp_eval"],
        supporting_evidence_link_ids=["sel_eval"],
        research_artifact_ids=["hyp_eval", "eass_eval"],
        review_decision_ids=[],
        status=PositionIdeaStatus.PENDING_REVIEW,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
