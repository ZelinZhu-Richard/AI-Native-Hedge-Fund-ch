from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import cast

from pydantic import Field

from libraries.core import build_provenance
from libraries.schemas import (
    AblationConfig,
    AblationResult,
    BacktestRun,
    BenchmarkReference,
    ComparisonSummary,
    CoverageSummary,
    DatasetReference,
    DataSnapshot,
    EvaluationDimension,
    EvaluationMetric,
    EvaluationReport,
    EvaluationStatus,
    EvidenceAssessment,
    EvidenceGrade,
    Experiment,
    FailureCase,
    FailureCaseKind,
    Feature,
    Hypothesis,
    MetricValue,
    PerformanceSummary,
    PortfolioProposal,
    ProvenanceRecord,
    RiskCheck,
    RobustnessCheck,
    RobustnessCheckKind,
    Severity,
    Signal,
    SignalStatus,
    StrategyFamily,
    StrategySpec,
    StrategyVariant,
    StrategyVariantSignal,
    StrictModel,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id


@dataclass
class EvaluationArtifacts:
    """Structured evaluation outputs accumulated across multiple checks."""

    metrics: list[EvaluationMetric] = field(default_factory=list)
    failure_cases: list[FailureCase] = field(default_factory=list)
    robustness_checks: list[RobustnessCheck] = field(default_factory=list)
    coverage_summaries: list[CoverageSummary] = field(default_factory=list)
    comparison_summary: ComparisonSummary | None = None
    notes: list[str] = field(default_factory=list)

    def extend(self, other: EvaluationArtifacts) -> None:
        """Merge another artifact bundle into this bundle."""

        self.metrics.extend(other.metrics)
        self.failure_cases.extend(other.failure_cases)
        self.robustness_checks.extend(other.robustness_checks)
        self.coverage_summaries.extend(other.coverage_summaries)
        if other.comparison_summary is not None:
            self.comparison_summary = other.comparison_summary
        self.notes.extend(other.notes)


def evaluate_provenance_completeness(
    *,
    evaluation_report_id: str,
    target_type: str,
    target_id: str,
    artifacts: list[StrictModel],
    clock: Clock,
    workflow_run_id: str,
) -> EvaluationArtifacts:
    """Evaluate whether artifacts carry minimum usable provenance."""

    output = EvaluationArtifacts()
    total_count = len(artifacts)
    covered_count = 0
    if total_count == 0:
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type=target_type,
                target_id=target_id,
                failure_kind=FailureCaseKind.EMPTY_OUTPUT,
                severity=Severity.HIGH,
                blocking=True,
                message="No artifacts were supplied for provenance evaluation.",
                related_artifact_ids=[],
                suspected_cause="missing_inputs",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    else:
        for artifact in artifacts:
            artifact_id = _artifact_id(artifact)
            completeness_failures = _provenance_failures(artifact)
            if not completeness_failures:
                covered_count += 1
                continue
            output.failure_cases.append(
                _failure_case(
                    evaluation_report_id=evaluation_report_id,
                    target_type=_artifact_type_name(artifact),
                    target_id=artifact_id,
                    failure_kind=FailureCaseKind.MISSING_PROVENANCE,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="; ".join(completeness_failures),
                    related_artifact_ids=[artifact_id],
                    suspected_cause="incomplete_provenance_record",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )

    coverage_ratio = 0.0 if total_count == 0 else covered_count / total_count
    status = _ratio_status(covered_count=covered_count, total_count=total_count)
    output.metrics.append(
        _metric(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.PROVENANCE_COMPLETENESS,
            metric_name="provenance_complete_ratio",
            target_type=target_type,
            target_id=target_id,
            status=status,
            metric_value=_numeric_metric_value(
                evaluation_report_id=evaluation_report_id,
                metric_name="provenance_complete_ratio",
                target_id=target_id,
                numeric_value=coverage_ratio,
                unit="ratio",
                clock=clock,
            ),
            threshold=1.0,
            notes=["Minimum provenance requires processing_time, transformation_name, and source or upstream linkage."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    output.coverage_summaries.append(
        _coverage_summary(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.PROVENANCE_COMPLETENESS,
            target_type=target_type,
            target_id=target_id,
            covered_count=covered_count,
            missing_count=total_count - covered_count,
            notes=["Coverage reflects artifacts with structurally usable provenance."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return output


def evaluate_hypothesis_support_quality(
    *,
    evaluation_report_id: str,
    target_type: str,
    target_id: str,
    hypotheses: list[Hypothesis],
    evidence_assessments: list[EvidenceAssessment],
    clock: Clock,
    workflow_run_id: str,
) -> EvaluationArtifacts:
    """Evaluate whether hypotheses are meaningfully supported and reviewable."""

    output = EvaluationArtifacts()
    assessment_by_hypothesis_id = {
        assessment.hypothesis_id: assessment
        for assessment in evidence_assessments
        if assessment.hypothesis_id is not None
    }
    total_count = len(hypotheses)
    covered_count = 0

    for hypothesis in hypotheses:
        hypothesis_failures = 0
        assessment = assessment_by_hypothesis_id.get(hypothesis.hypothesis_id)
        if not hypothesis.supporting_evidence_links:
            hypothesis_failures += 1
            output.failure_cases.append(
                _failure_case(
                    evaluation_report_id=evaluation_report_id,
                    target_type="hypothesis",
                    target_id=hypothesis.hypothesis_id,
                    failure_kind=FailureCaseKind.MISSING_EVIDENCE,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="Hypothesis does not link any supporting evidence.",
                    related_artifact_ids=[hypothesis.hypothesis_id],
                    suspected_cause="missing_support_links",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if assessment is None:
            hypothesis_failures += 1
            output.failure_cases.append(
                _failure_case(
                    evaluation_report_id=evaluation_report_id,
                    target_type="hypothesis",
                    target_id=hypothesis.hypothesis_id,
                    failure_kind=FailureCaseKind.INCOMPLETE_CONFIG,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="Hypothesis is missing an evidence assessment.",
                    related_artifact_ids=[hypothesis.hypothesis_id],
                    suspected_cause="missing_evidence_assessment",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        else:
            assessment_status = EvaluationStatus.PASS
            if assessment.grade is EvidenceGrade.MODERATE:
                assessment_status = EvaluationStatus.WARN
            elif assessment.grade is EvidenceGrade.WEAK:
                assessment_status = EvaluationStatus.WARN
                output.failure_cases.append(
                    _failure_case(
                        evaluation_report_id=evaluation_report_id,
                        target_type="hypothesis",
                        target_id=hypothesis.hypothesis_id,
                        failure_kind=FailureCaseKind.WEAK_SUPPORT,
                        severity=Severity.MEDIUM,
                        blocking=False,
                        message="Hypothesis support is weak and should not be treated as trustworthy.",
                        related_artifact_ids=[
                            hypothesis.hypothesis_id,
                            assessment.evidence_assessment_id,
                        ],
                        suspected_cause="thin_support",
                        clock=clock,
                        workflow_run_id=workflow_run_id,
                    )
                )
            elif assessment.grade is EvidenceGrade.INSUFFICIENT:
                assessment_status = EvaluationStatus.FAIL
                hypothesis_failures += 1
                output.failure_cases.append(
                    _failure_case(
                        evaluation_report_id=evaluation_report_id,
                        target_type="hypothesis",
                        target_id=hypothesis.hypothesis_id,
                        failure_kind=FailureCaseKind.WEAK_SUPPORT,
                        severity=Severity.HIGH,
                        blocking=True,
                        message="Hypothesis support is insufficient.",
                        related_artifact_ids=[
                            hypothesis.hypothesis_id,
                            assessment.evidence_assessment_id,
                        ],
                        suspected_cause="insufficient_support",
                        clock=clock,
                        workflow_run_id=workflow_run_id,
                    )
                )
            output.metrics.append(
                _metric(
                    evaluation_report_id=evaluation_report_id,
                    dimension=EvaluationDimension.HYPOTHESIS_SUPPORT_QUALITY,
                    metric_name=f"support_grade:{hypothesis.hypothesis_id}",
                    target_type="hypothesis",
                    target_id=hypothesis.hypothesis_id,
                    status=assessment_status,
                    metric_value=_text_metric_value(
                        evaluation_report_id=evaluation_report_id,
                        metric_name=f"support_grade:{hypothesis.hypothesis_id}",
                        target_id=hypothesis.hypothesis_id,
                        text_value=assessment.grade.value,
                        clock=clock,
                    ),
                    threshold=None,
                    notes=[assessment.support_summary],
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if not hypothesis.assumptions or not hypothesis.invalidation_conditions:
            output.metrics.append(
                _metric(
                    evaluation_report_id=evaluation_report_id,
                    dimension=EvaluationDimension.HYPOTHESIS_SUPPORT_QUALITY,
                    metric_name=f"hypothesis_structure_present:{hypothesis.hypothesis_id}",
                    target_type="hypothesis",
                    target_id=hypothesis.hypothesis_id,
                    status=EvaluationStatus.WARN,
                    metric_value=_boolean_metric_value(
                        evaluation_report_id=evaluation_report_id,
                        metric_name=f"hypothesis_structure_present:{hypothesis.hypothesis_id}",
                        target_id=hypothesis.hypothesis_id,
                        boolean_value=False,
                        clock=clock,
                    ),
                    threshold=None,
                    notes=["Hypothesis assumptions or invalidation conditions are too thin."],
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if hypothesis_failures == 0:
            covered_count += 1

    output.metrics.append(
        _metric(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.HYPOTHESIS_SUPPORT_QUALITY,
            metric_name="hypothesis_support_coverage_ratio",
            target_type=target_type,
            target_id=target_id,
            status=_ratio_status(covered_count=covered_count, total_count=total_count),
            metric_value=_numeric_metric_value(
                evaluation_report_id=evaluation_report_id,
                metric_name="hypothesis_support_coverage_ratio",
                target_id=target_id,
                numeric_value=0.0 if total_count == 0 else covered_count / total_count,
                unit="ratio",
                clock=clock,
            ),
            threshold=1.0,
            notes=["Coverage counts hypotheses with support links and evidence assessments."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    output.coverage_summaries.append(
        _coverage_summary(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.HYPOTHESIS_SUPPORT_QUALITY,
            target_type=target_type,
            target_id=target_id,
            covered_count=covered_count,
            missing_count=max(total_count - covered_count, 0),
            notes=["Coverage reflects hypotheses with structurally acceptable support."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return output


def evaluate_feature_lineage_completeness(
    *,
    evaluation_report_id: str,
    target_type: str,
    target_id: str,
    features: list[Feature],
    clock: Clock,
    workflow_run_id: str,
) -> EvaluationArtifacts:
    """Evaluate whether Day 5 features preserve required upstream lineage."""

    output = EvaluationArtifacts()
    total_count = len(features)
    covered_count = 0

    for feature in features:
        failures = 0
        if feature.feature_definition.feature_definition_id != feature.feature_value.feature_definition_id:
            failures += 1
            output.failure_cases.append(
                _failure_case(
                    evaluation_report_id=evaluation_report_id,
                    target_type="feature",
                    target_id=feature.feature_id,
                    failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="Feature definition ID does not match feature value definition ID.",
                    related_artifact_ids=[
                        feature.feature_id,
                        feature.feature_definition.feature_definition_id,
                        feature.feature_value.feature_value_id,
                    ],
                    suspected_cause="definition_value_mismatch",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if not feature.lineage.supporting_evidence_link_ids or not feature.lineage.source_document_ids:
            failures += 1
            output.failure_cases.append(
                _failure_case(
                    evaluation_report_id=evaluation_report_id,
                    target_type="feature",
                    target_id=feature.feature_id,
                    failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="Feature lineage is missing evidence-link IDs or source-document IDs.",
                    related_artifact_ids=[feature.feature_id, feature.lineage.feature_lineage_id],
                    suspected_cause="missing_feature_lineage",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if not feature.assumptions:
            output.metrics.append(
                _metric(
                    evaluation_report_id=evaluation_report_id,
                    dimension=EvaluationDimension.FEATURE_LINEAGE_COMPLETENESS,
                    metric_name=f"feature_assumptions_present:{feature.feature_id}",
                    target_type="feature",
                    target_id=feature.feature_id,
                    status=EvaluationStatus.WARN,
                    metric_value=_boolean_metric_value(
                        evaluation_report_id=evaluation_report_id,
                        metric_name=f"feature_assumptions_present:{feature.feature_id}",
                        target_id=feature.feature_id,
                        boolean_value=False,
                        clock=clock,
                    ),
                    threshold=None,
                    notes=["Feature has no explicit assumptions attached."],
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if failures == 0:
            covered_count += 1

    output.metrics.append(
        _metric(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.FEATURE_LINEAGE_COMPLETENESS,
            metric_name="feature_lineage_complete_ratio",
            target_type=target_type,
            target_id=target_id,
            status=_ratio_status(covered_count=covered_count, total_count=total_count),
            metric_value=_numeric_metric_value(
                evaluation_report_id=evaluation_report_id,
                metric_name="feature_lineage_complete_ratio",
                target_id=target_id,
                numeric_value=0.0 if total_count == 0 else covered_count / total_count,
                unit="ratio",
                clock=clock,
            ),
            threshold=1.0,
            notes=["Coverage reflects features with aligned definition/value IDs and required lineage."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    output.coverage_summaries.append(
        _coverage_summary(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.FEATURE_LINEAGE_COMPLETENESS,
            target_type=target_type,
            target_id=target_id,
            covered_count=covered_count,
            missing_count=max(total_count - covered_count, 0),
            notes=["Coverage reflects structurally complete feature lineage."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return output


def evaluate_signal_generation_validity(
    *,
    evaluation_report_id: str,
    target_type: str,
    target_id: str,
    signals: Sequence[Signal | StrategyVariantSignal],
    features_by_id: dict[str, Feature],
    known_signal_ids: set[str],
    snapshots_by_id: dict[str, DataSnapshot],
    clock: Clock,
    workflow_run_id: str,
) -> EvaluationArtifacts:
    """Evaluate research and variant signals for structural validity."""

    output = EvaluationArtifacts()
    total_count = len(signals)
    covered_count = 0

    for signal in signals:
        failures = 0
        signal_id = signal.signal_id
        if signal.expires_at is not None and signal.expires_at < signal.effective_at:
            failures += 1
            output.failure_cases.append(
                _failure_case(
                    evaluation_report_id=evaluation_report_id,
                    target_type=_signal_target_type(signal),
                    target_id=signal_id,
                    failure_kind=FailureCaseKind.INVALID_TIMESTAMP,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="Signal expiry precedes signal effective time.",
                    related_artifact_ids=[signal_id],
                    suspected_cause="invalid_signal_window",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if isinstance(signal, Signal):
            failures += _evaluate_research_signal_lineage(
                output=output,
                evaluation_report_id=evaluation_report_id,
                signal=signal,
                features_by_id=features_by_id,
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        else:
            failures += _evaluate_variant_signal_lineage(
                output=output,
                evaluation_report_id=evaluation_report_id,
                signal=signal,
                known_signal_ids=known_signal_ids,
                snapshots_by_id=snapshots_by_id,
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        if signal.status is SignalStatus.CANDIDATE and not signal.uncertainties:
            output.metrics.append(
                _metric(
                    evaluation_report_id=evaluation_report_id,
                    dimension=EvaluationDimension.SIGNAL_GENERATION_VALIDITY,
                    metric_name=f"candidate_uncertainty_visible:{signal_id}",
                    target_type=_signal_target_type(signal),
                    target_id=signal_id,
                    status=EvaluationStatus.WARN,
                    metric_value=_boolean_metric_value(
                        evaluation_report_id=evaluation_report_id,
                        metric_name=f"candidate_uncertainty_visible:{signal_id}",
                        target_id=signal_id,
                        boolean_value=False,
                        clock=clock,
                    ),
                    threshold=None,
                    notes=["Candidate signals should expose visible uncertainty."],
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if failures == 0:
            covered_count += 1

    output.metrics.append(
        _metric(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.SIGNAL_GENERATION_VALIDITY,
            metric_name="signal_validity_ratio",
            target_type=target_type,
            target_id=target_id,
            status=_ratio_status(covered_count=covered_count, total_count=total_count),
            metric_value=_numeric_metric_value(
                evaluation_report_id=evaluation_report_id,
                metric_name="signal_validity_ratio",
                target_id=target_id,
                numeric_value=0.0 if total_count == 0 else covered_count / total_count,
                unit="ratio",
                clock=clock,
            ),
            threshold=1.0,
            notes=["Coverage reflects signals without invalid windows or broken lineage."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    output.coverage_summaries.append(
        _coverage_summary(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.SIGNAL_GENERATION_VALIDITY,
            target_type=target_type,
            target_id=target_id,
            covered_count=covered_count,
            missing_count=max(total_count - covered_count, 0),
            notes=["Coverage reflects structurally valid signals."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return output


def evaluate_backtest_artifact_completeness(
    *,
    evaluation_report_id: str,
    target_type: str,
    target_id: str,
    variant_runs: list[AblationVariantRunEvaluationInput],
    record_experiment_expected: bool,
    clock: Clock,
    workflow_run_id: str,
) -> EvaluationArtifacts:
    """Evaluate whether child backtest outputs are complete and reproducible."""

    output = EvaluationArtifacts()
    total_count = len(variant_runs)
    covered_count = 0
    experiment_linked_count = 0

    for variant_run in variant_runs:
        run = variant_run.backtest_run
        failures = 0
        has_valid_experiment_linkage = False
        if not run.signal_snapshot_id or not run.price_snapshot_id:
            failures += 1
            output.failure_cases.append(
                _failure_case(
                    evaluation_report_id=evaluation_report_id,
                    target_type="backtest_run",
                    target_id=run.backtest_run_id,
                    failure_kind=FailureCaseKind.INCOMPLETE_CONFIG,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="Backtest run is missing one or more snapshot identifiers.",
                    related_artifact_ids=[run.backtest_run_id],
                    suspected_cause="missing_snapshot_linkage",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if run.performance_summary_id != variant_run.performance_summary.performance_summary_id:
            failures += 1
            output.failure_cases.append(
                _failure_case(
                    evaluation_report_id=evaluation_report_id,
                    target_type="backtest_run",
                    target_id=run.backtest_run_id,
                    failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="Backtest run does not point to the supplied performance summary.",
                    related_artifact_ids=[
                        run.backtest_run_id,
                        variant_run.performance_summary.performance_summary_id,
                    ],
                    suspected_cause="backtest_summary_mismatch",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if not variant_run.benchmark_references:
            failures += 1
            output.failure_cases.append(
                _failure_case(
                    evaluation_report_id=evaluation_report_id,
                    target_type="backtest_run",
                    target_id=run.backtest_run_id,
                    failure_kind=FailureCaseKind.EMPTY_OUTPUT,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="Backtest run is missing benchmark references.",
                    related_artifact_ids=[run.backtest_run_id],
                    suspected_cause="missing_benchmark_output",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if record_experiment_expected:
            linked_snapshot_ids = {
                dataset_reference.data_snapshot_id
                for dataset_reference in variant_run.dataset_references
            }
            has_valid_experiment_linkage = (
                variant_run.experiment is not None
                and run.experiment_id == variant_run.experiment.experiment_id
                and bool(variant_run.dataset_references)
                and {run.signal_snapshot_id, run.price_snapshot_id}.issubset(linked_snapshot_ids)
            )
            if variant_run.experiment is None or run.experiment_id != variant_run.experiment.experiment_id:
                failures += 1
                output.failure_cases.append(
                    _failure_case(
                        evaluation_report_id=evaluation_report_id,
                        target_type="backtest_run",
                        target_id=run.backtest_run_id,
                        failure_kind=FailureCaseKind.INCOMPLETE_CONFIG,
                        severity=Severity.HIGH,
                        blocking=True,
                        message="Experiment linkage is missing or inconsistent for the backtest run.",
                        related_artifact_ids=[run.backtest_run_id, *( [run.experiment_id] if run.experiment_id else [] )],
                        suspected_cause="missing_experiment_linkage",
                        clock=clock,
                        workflow_run_id=workflow_run_id,
                    )
                )
            if not variant_run.dataset_references:
                failures += 1
                output.failure_cases.append(
                    _failure_case(
                        evaluation_report_id=evaluation_report_id,
                        target_type="backtest_run",
                        target_id=run.backtest_run_id,
                        failure_kind=FailureCaseKind.INCOMPLETE_CONFIG,
                        severity=Severity.HIGH,
                        blocking=True,
                        message="Experiment-recorded backtest run is missing dataset references.",
                        related_artifact_ids=[run.backtest_run_id],
                        suspected_cause="missing_dataset_references",
                        clock=clock,
                        workflow_run_id=workflow_run_id,
                    )
                )
            elif not {run.signal_snapshot_id, run.price_snapshot_id}.issubset(linked_snapshot_ids):
                failures += 1
                output.failure_cases.append(
                    _failure_case(
                        evaluation_report_id=evaluation_report_id,
                        target_type="backtest_run",
                        target_id=run.backtest_run_id,
                        failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                        severity=Severity.HIGH,
                        blocking=True,
                        message="Dataset references do not resolve back to the run snapshots.",
                        related_artifact_ids=[
                            run.backtest_run_id,
                            run.signal_snapshot_id,
                            run.price_snapshot_id,
                            *[dataset_reference.dataset_reference_id for dataset_reference in variant_run.dataset_references],
                        ],
                        suspected_cause="snapshot_reference_mismatch",
                        clock=clock,
                        workflow_run_id=workflow_run_id,
                    )
                )
        else:
            has_valid_experiment_linkage = True
        suspicious_leakage = [
            check
            for check in run.leakage_checks
            if any(
                token in check
                for token in (
                    "failed",
                    "rejected",
                    "missing_lineage",
                    "requested_window_outside_available_price_bars",
                )
            )
        ]
        if suspicious_leakage:
            output.metrics.append(
                _metric(
                    evaluation_report_id=evaluation_report_id,
                    dimension=EvaluationDimension.BACKTEST_ARTIFACT_COMPLETENESS,
                    metric_name=f"leakage_checks_clean:{run.backtest_run_id}",
                    target_type="backtest_run",
                    target_id=run.backtest_run_id,
                    status=EvaluationStatus.WARN,
                    metric_value=_boolean_metric_value(
                        evaluation_report_id=evaluation_report_id,
                        metric_name=f"leakage_checks_clean:{run.backtest_run_id}",
                        target_id=run.backtest_run_id,
                        boolean_value=False,
                        clock=clock,
                    ),
                    threshold=None,
                    notes=suspicious_leakage,
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if not run.notes:
            output.metrics.append(
                _metric(
                    evaluation_report_id=evaluation_report_id,
                    dimension=EvaluationDimension.BACKTEST_ARTIFACT_COMPLETENESS,
                    metric_name=f"backtest_notes_present:{run.backtest_run_id}",
                    target_type="backtest_run",
                    target_id=run.backtest_run_id,
                    status=EvaluationStatus.WARN,
                    metric_value=_boolean_metric_value(
                        evaluation_report_id=evaluation_report_id,
                        metric_name=f"backtest_notes_present:{run.backtest_run_id}",
                        target_id=run.backtest_run_id,
                        boolean_value=False,
                        clock=clock,
                    ),
                    threshold=None,
                    notes=["Backtest run has no explanatory notes."],
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                )
            )
        if failures == 0:
            covered_count += 1
        if has_valid_experiment_linkage:
            experiment_linked_count += 1

    output.metrics.append(
        _metric(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.BACKTEST_ARTIFACT_COMPLETENESS,
            metric_name="backtest_artifact_complete_ratio",
            target_type=target_type,
            target_id=target_id,
            status=_ratio_status(covered_count=covered_count, total_count=total_count),
            metric_value=_numeric_metric_value(
                evaluation_report_id=evaluation_report_id,
                metric_name="backtest_artifact_complete_ratio",
                target_id=target_id,
                numeric_value=0.0 if total_count == 0 else covered_count / total_count,
                unit="ratio",
                clock=clock,
            ),
            threshold=1.0,
            notes=["Coverage reflects child backtests with snapshots, benchmarks, summaries, and expected experiment linkage."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    if record_experiment_expected:
        output.metrics.append(
            _metric(
                evaluation_report_id=evaluation_report_id,
                dimension=EvaluationDimension.BACKTEST_ARTIFACT_COMPLETENESS,
                metric_name="experiment_linkage_ratio",
                target_type=target_type,
                target_id=target_id,
                status=_ratio_status(
                    covered_count=experiment_linked_count,
                    total_count=total_count,
                ),
                metric_value=_numeric_metric_value(
                    evaluation_report_id=evaluation_report_id,
                    metric_name="experiment_linkage_ratio",
                    target_id=target_id,
                    numeric_value=(
                        0.0 if total_count == 0 else experiment_linked_count / total_count
                    ),
                    unit="ratio",
                    clock=clock,
                ),
                threshold=1.0,
                notes=[
                    "Coverage reflects child backtests with consistent experiment and dataset linkage."
                ],
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    output.coverage_summaries.append(
        _coverage_summary(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.BACKTEST_ARTIFACT_COMPLETENESS,
            target_type=target_type,
            target_id=target_id,
            covered_count=covered_count,
            missing_count=max(total_count - covered_count, 0),
            notes=["Coverage reflects structurally complete child backtest outputs."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return output


def evaluate_strategy_comparison_output(
    *,
    evaluation_report_id: str,
    ablation_config: AblationConfig,
    ablation_result: AblationResult,
    strategy_specs: list[StrategySpec],
    strategy_variants: list[StrategyVariant],
    variant_runs: list[AblationVariantRunEvaluationInput],
    clock: Clock,
    workflow_run_id: str,
) -> EvaluationArtifacts:
    """Evaluate multi-variant comparison structure and family coverage."""

    output = EvaluationArtifacts()
    expected_families = [variant.family for variant in strategy_variants]
    observed_families = [result.family for result in ablation_result.variant_results]
    expected_family_count = len(set(expected_families))
    observed_family_count = len(set(observed_families))
    variant_run_ids = {variant_run.backtest_run.backtest_run_id for variant_run in variant_runs}

    if not ablation_result.variant_results:
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="ablation_result",
                target_id=ablation_result.ablation_result_id,
                failure_kind=FailureCaseKind.EMPTY_OUTPUT,
                severity=Severity.HIGH,
                blocking=True,
                message="Ablation result has no comparison rows.",
                related_artifact_ids=[ablation_result.ablation_result_id],
                suspected_cause="missing_variant_results",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    duplicate_observed = _duplicates([family.value for family in observed_families])
    missing_families = sorted({family.value for family in expected_families} - {family.value for family in observed_families})
    unexpected_families = sorted({family.value for family in observed_families} - {family.value for family in expected_families})
    if duplicate_observed or missing_families or unexpected_families:
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="ablation_result",
                target_id=ablation_result.ablation_result_id,
                failure_kind=FailureCaseKind.INCOMPLETE_CONFIG,
                severity=Severity.HIGH,
                blocking=True,
                message=(
                    "Strategy family coverage is inconsistent."
                    f" duplicates={duplicate_observed or 'none'}"
                    f" missing={missing_families or 'none'}"
                    f" unexpected={unexpected_families or 'none'}"
                ),
                related_artifact_ids=[ablation_result.ablation_result_id],
                suspected_cause="family_coverage_mismatch",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    if ablation_result.comparison_metric_name != ablation_config.comparison_metric_name:
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="ablation_result",
                target_id=ablation_result.ablation_result_id,
                failure_kind=FailureCaseKind.INCOMPLETE_CONFIG,
                severity=Severity.HIGH,
                blocking=True,
                message="Ablation result comparison metric does not match the ablation config.",
                related_artifact_ids=[
                    ablation_result.ablation_result_id,
                    ablation_config.ablation_config_id,
                ],
                suspected_cause="comparison_metric_mismatch",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    if ablation_config.record_experiment and any(result.experiment_id is None for result in ablation_result.variant_results):
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="ablation_result",
                target_id=ablation_result.ablation_result_id,
                failure_kind=FailureCaseKind.INCOMPLETE_CONFIG,
                severity=Severity.HIGH,
                blocking=True,
                message="One or more ablation rows are missing child experiment IDs.",
                related_artifact_ids=[
                    ablation_result.ablation_result_id,
                    *[
                        result.strategy_variant_id
                        for result in ablation_result.variant_results
                        if result.experiment_id is None
                    ],
                ],
                suspected_cause="missing_child_experiments",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    dangling_backtest_ids = [
        result.backtest_run_id
        for result in ablation_result.variant_results
        if result.backtest_run_id not in variant_run_ids
    ]
    if dangling_backtest_ids:
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="ablation_result",
                target_id=ablation_result.ablation_result_id,
                failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                severity=Severity.HIGH,
                blocking=True,
                message="Ablation result references backtest runs that were not supplied for evaluation.",
                related_artifact_ids=[ablation_result.ablation_result_id, *dangling_backtest_ids],
                suspected_cause="missing_child_backtests",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )

    family_coverage_ratio = 0.0 if expected_family_count == 0 else observed_family_count / expected_family_count
    output.metrics.append(
        _metric(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.STRATEGY_COMPARISON_OUTPUT,
            metric_name="strategy_family_coverage_ratio",
            target_type="ablation_result",
            target_id=ablation_result.ablation_result_id,
            status=_ratio_status(
                covered_count=observed_family_count,
                total_count=expected_family_count,
            ),
            metric_value=_numeric_metric_value(
                evaluation_report_id=evaluation_report_id,
                metric_name="strategy_family_coverage_ratio",
                target_id=ablation_result.ablation_result_id,
                numeric_value=family_coverage_ratio,
                unit="ratio",
                clock=clock,
            ),
            threshold=1.0,
            notes=["Coverage compares observed strategy families to the configured family set."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    output.coverage_summaries.append(
        _coverage_summary(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.STRATEGY_COMPARISON_OUTPUT,
            target_type="ablation_result",
            target_id=ablation_result.ablation_result_id,
            covered_count=observed_family_count,
            missing_count=max(expected_family_count - observed_family_count, 0),
            notes=["Coverage reflects observed strategy families in the ablation result."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    output.comparison_summary = ComparisonSummary(
        comparison_summary_id=make_canonical_id(
            "cmpsum",
            evaluation_report_id,
            ablation_result.ablation_result_id,
        ),
        evaluation_report_id=evaluation_report_id,
        target_id=ablation_result.ablation_result_id,
        comparison_metric_name=ablation_result.comparison_metric_name,
        expected_family_count=expected_family_count,
        observed_family_count=observed_family_count,
        ordered_strategy_variant_ids=[
            result.strategy_variant_id for result in ablation_result.variant_results
        ],
        mechanical_order_only=True,
        notes=[
            "Rows remain mechanically ordered by the declared comparison metric only.",
            "Ordering does not imply validation, promotion, or proven edge.",
            f"strategy_spec_count={len(strategy_specs)}",
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day10_comparison_summary",
            upstream_artifact_ids=[
                ablation_config.ablation_config_id,
                ablation_result.ablation_result_id,
                *[result.strategy_variant_id for result in ablation_result.variant_results],
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    return output


def evaluate_risk_review_coverage(
    *,
    evaluation_report_id: str,
    portfolio_proposal: PortfolioProposal,
    risk_checks: list[RiskCheck],
    clock: Clock,
    workflow_run_id: str,
) -> EvaluationArtifacts:
    """Evaluate whether risk review coverage is explicit and aligned."""

    output = EvaluationArtifacts()
    if not risk_checks:
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="portfolio_proposal",
                target_id=portfolio_proposal.portfolio_proposal_id,
                failure_kind=FailureCaseKind.INCOMPLETE_CONFIG,
                severity=Severity.HIGH,
                blocking=True,
                message="Portfolio proposal has no attached risk checks.",
                related_artifact_ids=[portfolio_proposal.portfolio_proposal_id],
                suspected_cause="missing_risk_review",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    if any(check.blocking for check in risk_checks) and not portfolio_proposal.blocking_issues:
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="portfolio_proposal",
                target_id=portfolio_proposal.portfolio_proposal_id,
                failure_kind=FailureCaseKind.INCOMPLETE_CONFIG,
                severity=Severity.HIGH,
                blocking=True,
                message="Blocking risk checks exist but proposal blocking_issues is empty.",
                related_artifact_ids=[
                    portfolio_proposal.portfolio_proposal_id,
                    *[check.risk_check_id for check in risk_checks if check.blocking],
                ],
                suspected_cause="proposal_risk_alignment_gap",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    subject_types = {check.subject_type for check in risk_checks}
    if risk_checks and subject_types == {"portfolio_proposal"}:
        output.metrics.append(
            _metric(
                evaluation_report_id=evaluation_report_id,
                dimension=EvaluationDimension.RISK_REVIEW_COVERAGE,
                metric_name="position_level_risk_coverage_present",
                target_type="portfolio_proposal",
                target_id=portfolio_proposal.portfolio_proposal_id,
                status=EvaluationStatus.WARN,
                metric_value=_boolean_metric_value(
                    evaluation_report_id=evaluation_report_id,
                    metric_name="position_level_risk_coverage_present",
                    target_id=portfolio_proposal.portfolio_proposal_id,
                    boolean_value=False,
                    clock=clock,
                ),
                threshold=None,
                notes=["Risk review is present but only at the portfolio-proposal level."],
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    covered_count = 1 if risk_checks else 0
    output.metrics.append(
        _metric(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.RISK_REVIEW_COVERAGE,
            metric_name="risk_review_present",
            target_type="portfolio_proposal",
            target_id=portfolio_proposal.portfolio_proposal_id,
            status=EvaluationStatus.PASS if risk_checks else EvaluationStatus.FAIL,
            metric_value=_boolean_metric_value(
                evaluation_report_id=evaluation_report_id,
                metric_name="risk_review_present",
                target_id=portfolio_proposal.portfolio_proposal_id,
                boolean_value=bool(risk_checks),
                clock=clock,
            ),
            threshold=None,
            notes=["Presence-only risk review coverage check."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    output.coverage_summaries.append(
        _coverage_summary(
            evaluation_report_id=evaluation_report_id,
            dimension=EvaluationDimension.RISK_REVIEW_COVERAGE,
            target_type="portfolio_proposal",
            target_id=portfolio_proposal.portfolio_proposal_id,
            covered_count=covered_count,
            missing_count=1 - covered_count,
            notes=["Coverage reflects whether the proposal has explicit risk review artifacts."],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return output


def robustness_missing_data_sensitivity(
    *,
    evaluation_report_id: str,
    target_id: str,
    variant_runs: list[AblationVariantRunEvaluationInput],
    clock: Clock,
    workflow_run_id: str,
) -> RobustnessCheck:
    """Warn when variant output coverage is too thin to compare honestly."""

    empty_variants = [
        variant_run.strategy_variant.variant_name
        for variant_run in variant_runs
        if not variant_run.variant_signals
    ]
    if empty_variants:
        return _robustness_check(
            evaluation_report_id=evaluation_report_id,
            check_kind=RobustnessCheckKind.MISSING_DATA_SENSITIVITY,
            target_type="ablation_result",
            target_id=target_id,
            status=EvaluationStatus.WARN,
            severity=Severity.MEDIUM,
            message=(
                "One or more strategy variants emitted no comparable signals: "
                + ", ".join(empty_variants)
            ),
            related_artifact_ids=[
                variant_run.strategy_variant.strategy_variant_id
                for variant_run in variant_runs
                if not variant_run.variant_signals
            ],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    return _robustness_check(
        evaluation_report_id=evaluation_report_id,
        check_kind=RobustnessCheckKind.MISSING_DATA_SENSITIVITY,
        target_type="ablation_result",
        target_id=target_id,
        status=EvaluationStatus.PASS,
        severity=Severity.LOW,
        message="All configured strategy variants emitted at least one comparable signal.",
        related_artifact_ids=[variant_run.strategy_variant.strategy_variant_id for variant_run in variant_runs],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def robustness_timestamp_anomaly(
    *,
    evaluation_report_id: str,
    target_id: str,
    evaluation_slice_start: datetime,
    evaluation_slice_end: datetime,
    source_snapshots: list[DataSnapshot],
    text_signals: list[Signal],
    variant_runs: list[AblationVariantRunEvaluationInput],
    clock: Clock,
    workflow_run_id: str,
) -> RobustnessCheck:
    """Check for cross-artifact timestamp anomalies."""

    anomalies: list[str] = []
    snapshots_by_id = {snapshot.data_snapshot_id: snapshot for snapshot in source_snapshots}
    for snapshot in source_snapshots:
        if (
            snapshot.information_cutoff_time is not None
            and snapshot.snapshot_time < snapshot.information_cutoff_time
        ):
            anomalies.append(f"snapshot_time_before_information_cutoff:{snapshot.data_snapshot_id}")
    research_snapshot = next(
        (snapshot for snapshot in source_snapshots if snapshot.dataset_name == "candidate_signals"),
        None,
    )
    price_snapshot = next(
        (snapshot for snapshot in source_snapshots if snapshot.dataset_name == "synthetic_daily_prices"),
        None,
    )
    if research_snapshot is not None and research_snapshot.information_cutoff_time is not None:
        for signal in text_signals:
            if signal.effective_at > research_snapshot.information_cutoff_time:
                anomalies.append(f"text_signal_after_snapshot_cutoff:{signal.signal_id}")
    for variant_run in variant_runs:
        if (
            price_snapshot is not None
            and variant_run.backtest_run.decision_cutoff_time > price_snapshot.snapshot_time
        ):
            anomalies.append(
                "decision_cutoff_after_price_snapshot:"
                f"{variant_run.backtest_run.backtest_run_id}"
            )
        for variant_signal in variant_run.variant_signals:
            if (
                variant_signal.effective_at < evaluation_slice_start
                or variant_signal.effective_at > evaluation_slice_end
            ):
                anomalies.append(
                    "signal_outside_evaluation_slice:"
                    f"{variant_signal.strategy_variant_signal_id}"
                )
            for snapshot_id in variant_signal.source_snapshot_ids:
                source_snapshot = snapshots_by_id.get(snapshot_id)
                if source_snapshot is None:
                    anomalies.append(
                        "unknown_source_snapshot:"
                        f"{variant_signal.strategy_variant_signal_id}:{snapshot_id}"
                    )
                    continue
                if (
                    source_snapshot.information_cutoff_time is not None
                    and variant_signal.effective_at > source_snapshot.information_cutoff_time
                ):
                    anomalies.append(
                        "signal_after_source_cutoff:"
                        f"{variant_signal.strategy_variant_signal_id}"
                    )
    if anomalies:
        return _robustness_check(
            evaluation_report_id=evaluation_report_id,
            check_kind=RobustnessCheckKind.TIMESTAMP_ANOMALY,
            target_type="ablation_result",
            target_id=target_id,
            status=EvaluationStatus.FAIL,
            severity=Severity.HIGH,
            message="Timestamp anomalies were detected across snapshots, signals, or decision cutoffs.",
            related_artifact_ids=anomalies,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    return _robustness_check(
        evaluation_report_id=evaluation_report_id,
        check_kind=RobustnessCheckKind.TIMESTAMP_ANOMALY,
        target_type="ablation_result",
        target_id=target_id,
        status=EvaluationStatus.PASS,
        severity=Severity.LOW,
        message="No cross-artifact timestamp anomalies were detected.",
        related_artifact_ids=[snapshot.data_snapshot_id for snapshot in source_snapshots],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def robustness_source_inconsistency(
    *,
    evaluation_report_id: str,
    target_id: str,
    expected_company_id: str,
    source_snapshots: list[DataSnapshot],
    text_signals: list[Signal],
    features: list[Feature],
    variant_runs: list[AblationVariantRunEvaluationInput],
    clock: Clock,
    workflow_run_id: str,
) -> RobustnessCheck:
    """Check for inconsistent company identity or snapshot partitioning."""

    observed_company_ids: set[str] = {expected_company_id}
    observed_company_ids.update(signal.company_id for signal in text_signals)
    observed_company_ids.update(
        feature.company_id for feature in features if feature.company_id is not None
    )
    observed_company_ids.update(
        signal.company_id
        for variant_run in variant_runs
        for signal in variant_run.variant_signals
    )
    observed_company_ids.update(
        variant_run.backtest_run.company_id for variant_run in variant_runs
    )
    anomalies: list[str] = []
    if observed_company_ids != {expected_company_id}:
        anomalies.append(
            "company_id_mismatch:" + ",".join(sorted(observed_company_ids))
        )
    for snapshot in source_snapshots:
        if snapshot.partition_key is not None and snapshot.partition_key != expected_company_id:
            anomalies.append(f"snapshot_partition_mismatch:{snapshot.data_snapshot_id}")
    if anomalies:
        return _robustness_check(
            evaluation_report_id=evaluation_report_id,
            check_kind=RobustnessCheckKind.SOURCE_INCONSISTENCY,
            target_type="ablation_result",
            target_id=target_id,
            status=EvaluationStatus.FAIL,
            severity=Severity.HIGH,
            message="Company or source-snapshot identity is inconsistent across the evaluation slice.",
            related_artifact_ids=anomalies,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    return _robustness_check(
        evaluation_report_id=evaluation_report_id,
        check_kind=RobustnessCheckKind.SOURCE_INCONSISTENCY,
        target_type="ablation_result",
        target_id=target_id,
        status=EvaluationStatus.PASS,
        severity=Severity.LOW,
        message="Company and snapshot identity remained consistent across the evaluation slice.",
        related_artifact_ids=[expected_company_id],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def robustness_incomplete_extraction_artifact(
    *,
    evaluation_report_id: str,
    target_id: str,
    text_signals: list[Signal],
    features: list[Feature],
    clock: Clock,
    workflow_run_id: str,
) -> RobustnessCheck:
    """Check whether upstream research evidence linkage is materially incomplete."""

    incomplete_artifact_ids = [
        signal.signal_id
        for signal in text_signals
        if not signal.lineage.supporting_evidence_link_ids
    ]
    incomplete_artifact_ids.extend(
        feature.feature_id
        for feature in features
        if not feature.lineage.supporting_evidence_link_ids or not feature.lineage.source_document_ids
    )
    if incomplete_artifact_ids:
        return _robustness_check(
            evaluation_report_id=evaluation_report_id,
            check_kind=RobustnessCheckKind.INCOMPLETE_EXTRACTION_ARTIFACT,
            target_type="ablation_result",
            target_id=target_id,
            status=EvaluationStatus.FAIL,
            severity=Severity.HIGH,
            message="Upstream research lineage is incomplete for one or more text artifacts.",
            related_artifact_ids=incomplete_artifact_ids,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    return _robustness_check(
        evaluation_report_id=evaluation_report_id,
        check_kind=RobustnessCheckKind.INCOMPLETE_EXTRACTION_ARTIFACT,
        target_type="ablation_result",
        target_id=target_id,
        status=EvaluationStatus.PASS,
        severity=Severity.LOW,
        message="Upstream research artifacts retained evidence linkage required for the ablation slice.",
        related_artifact_ids=[signal.signal_id for signal in text_signals],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def robustness_invalid_strategy_config(
    *,
    evaluation_report_id: str,
    ablation_config: AblationConfig,
    strategy_specs: list[StrategySpec],
    clock: Clock,
    workflow_run_id: str,
) -> RobustnessCheck:
    """Check for invalid or suspicious ablation configuration combinations."""

    issues: list[str] = []
    spec_by_id = {spec.strategy_spec_id: spec for spec in strategy_specs}
    duplicate_families = _duplicates([variant.family.value for variant in ablation_config.strategy_variants])
    if duplicate_families:
        issues.append("duplicate_families:" + ",".join(duplicate_families))
    for variant in ablation_config.strategy_variants:
        spec = spec_by_id.get(variant.strategy_spec_id)
        if spec is None:
            issues.append(f"unknown_strategy_spec:{variant.strategy_variant_id}")
            continue
        if spec.family is not variant.family:
            issues.append(f"family_spec_mismatch:{variant.strategy_variant_id}")
    if ablation_config.shared_backtest_config.test_start != ablation_config.evaluation_slice.test_start:
        issues.append("shared_backtest_start_mismatch")
    if ablation_config.shared_backtest_config.test_end != ablation_config.evaluation_slice.test_end:
        issues.append("shared_backtest_end_mismatch")
    if ablation_config.shared_backtest_config.decision_frequency != ablation_config.evaluation_slice.decision_frequency:
        issues.append("decision_frequency_mismatch")
    if issues:
        return _robustness_check(
            evaluation_report_id=evaluation_report_id,
            check_kind=RobustnessCheckKind.INVALID_STRATEGY_CONFIG,
            target_type="ablation_config",
            target_id=ablation_config.ablation_config_id,
            status=EvaluationStatus.FAIL,
            severity=Severity.HIGH,
            message="Strategy ablation configuration is internally inconsistent.",
            related_artifact_ids=[ablation_config.ablation_config_id, *issues],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    return _robustness_check(
        evaluation_report_id=evaluation_report_id,
        check_kind=RobustnessCheckKind.INVALID_STRATEGY_CONFIG,
        target_type="ablation_config",
        target_id=ablation_config.ablation_config_id,
        status=EvaluationStatus.PASS,
        severity=Severity.LOW,
        message="Strategy ablation configuration is internally consistent.",
        related_artifact_ids=[ablation_config.ablation_config_id],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def derive_overall_status(*, artifacts: EvaluationArtifacts) -> EvaluationStatus:
    """Collapse structured evaluation outputs into one report-level status."""

    if any(
        failure.blocking or failure.severity in {Severity.HIGH, Severity.CRITICAL}
        for failure in artifacts.failure_cases
    ):
        return EvaluationStatus.FAIL
    if any(
        check.status is EvaluationStatus.FAIL for check in artifacts.robustness_checks
    ) or any(metric.status is EvaluationStatus.FAIL for metric in artifacts.metrics):
        return EvaluationStatus.FAIL
    if artifacts.failure_cases or any(
        check.status is EvaluationStatus.WARN for check in artifacts.robustness_checks
    ) or any(metric.status is EvaluationStatus.WARN for metric in artifacts.metrics):
        return EvaluationStatus.WARN
    if (
        artifacts.metrics
        or artifacts.failure_cases
        or artifacts.robustness_checks
        or artifacts.comparison_summary is not None
        or artifacts.coverage_summaries
    ):
        return EvaluationStatus.PASS
    return EvaluationStatus.NOT_EVALUATED


class AblationVariantRunEvaluationInput(StrictModel):
    """Local evaluation bundle for one ablation child run."""

    strategy_variant: StrategyVariant = Field(description="Variant represented by the child run.")
    strategy_spec: StrategySpec = Field(description="Spec represented by the child run.")
    variant_signals: list[StrategyVariantSignal] = Field(
        default_factory=list,
        description="Comparable signals emitted for the variant.",
    )
    backtest_run: BacktestRun = Field(description="Backtest run produced for the variant.")
    performance_summary: PerformanceSummary = Field(
        description="Performance summary emitted by the child run."
    )
    benchmark_references: list[BenchmarkReference] = Field(
        default_factory=list,
        description="Benchmark references emitted by the child run.",
    )
    dataset_references: list[DatasetReference] = Field(
        default_factory=list,
        description="Dataset references used by the child run.",
    )
    experiment: Experiment | None = Field(
        default=None,
        description="Optional experiment recorded for the child run.",
    )


def _evaluate_research_signal_lineage(
    *,
    output: EvaluationArtifacts,
    evaluation_report_id: str,
    signal: Signal,
    features_by_id: dict[str, Feature],
    clock: Clock,
    workflow_run_id: str,
) -> int:
    failures = 0
    signal_id = signal.signal_id
    if not signal.feature_ids:
        failures += 1
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="signal",
                target_id=signal_id,
                failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                severity=Severity.HIGH,
                blocking=True,
                message="Research signal does not reference any features.",
                related_artifact_ids=[signal_id],
                suspected_cause="missing_feature_ids",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    missing_features = [feature_id for feature_id in signal.feature_ids if feature_id not in features_by_id]
    if missing_features:
        failures += 1
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="signal",
                target_id=signal_id,
                failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                severity=Severity.HIGH,
                blocking=True,
                message="Research signal references features that were not supplied for evaluation.",
                related_artifact_ids=[signal_id, *missing_features],
                suspected_cause="missing_feature_artifacts",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    if set(signal.lineage.feature_ids) != set(signal.feature_ids):
        failures += 1
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="signal",
                target_id=signal_id,
                failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                severity=Severity.HIGH,
                blocking=True,
                message="Signal lineage feature IDs do not match the signal feature IDs.",
                related_artifact_ids=[signal_id, signal.lineage.signal_lineage_id],
                suspected_cause="lineage_feature_mismatch",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    invalid_component_scores = [
        score.signal_score_id
        for score in signal.component_scores
        if not score.source_feature_ids
        or not set(score.source_feature_ids).issubset(set(signal.feature_ids))
    ]
    if invalid_component_scores:
        failures += 1
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="signal",
                target_id=signal_id,
                failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                severity=Severity.HIGH,
                blocking=True,
                message="Signal component scores are missing valid source_feature_ids.",
                related_artifact_ids=[signal_id, *invalid_component_scores],
                suspected_cause="component_score_lineage_gap",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    return failures


def _evaluate_variant_signal_lineage(
    *,
    output: EvaluationArtifacts,
    evaluation_report_id: str,
    signal: StrategyVariantSignal,
    known_signal_ids: set[str],
    snapshots_by_id: dict[str, DataSnapshot],
    clock: Clock,
    workflow_run_id: str,
) -> int:
    failures = 0
    signal_id = signal.signal_id
    if not signal.source_snapshot_ids:
        failures += 1
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="strategy_variant_signal",
                target_id=signal_id,
                failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                severity=Severity.HIGH,
                blocking=True,
                message="Variant signal does not reference any source snapshots.",
                related_artifact_ids=[signal_id],
                suspected_cause="missing_source_snapshots",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    missing_snapshots = [
        snapshot_id for snapshot_id in signal.source_snapshot_ids if snapshot_id not in snapshots_by_id
    ]
    if missing_snapshots:
        failures += 1
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="strategy_variant_signal",
                target_id=signal_id,
                failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                severity=Severity.HIGH,
                blocking=True,
                message="Variant signal references unknown source snapshots.",
                related_artifact_ids=[signal_id, *missing_snapshots],
                suspected_cause="unknown_source_snapshot",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    if signal.family in {
        StrategyFamily.TEXT_ONLY_CANDIDATE_BASELINE,
        StrategyFamily.COMBINED_BASELINE,
    } and not signal.source_signal_ids:
        failures += 1
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="strategy_variant_signal",
                target_id=signal_id,
                failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                severity=Severity.HIGH,
                blocking=True,
                message="Text-linked variant signal is missing source research-signal IDs.",
                related_artifact_ids=[signal_id],
                suspected_cause="missing_source_signal_ids",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    unknown_sources = [signal_id_ref for signal_id_ref in signal.source_signal_ids if signal_id_ref not in known_signal_ids]
    if unknown_sources:
        failures += 1
        output.failure_cases.append(
            _failure_case(
                evaluation_report_id=evaluation_report_id,
                target_type="strategy_variant_signal",
                target_id=signal_id,
                failure_kind=FailureCaseKind.BROKEN_LINEAGE,
                severity=Severity.HIGH,
                blocking=True,
                message="Variant signal references source signals that were not supplied for evaluation.",
                related_artifact_ids=[signal_id, *unknown_sources],
                suspected_cause="unknown_source_signal",
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        )
    return failures


def _provenance_failures(artifact: StrictModel) -> list[str]:
    provenance = cast(ProvenanceRecord | None, getattr(artifact, "provenance", None))
    if provenance is None:
        return ["Artifact does not carry a provenance record."]
    failures: list[str] = []
    if provenance.processing_time is None:
        failures.append("Provenance is missing processing_time.")
    if not provenance.transformation_name:
        failures.append("Provenance is missing transformation_name.")
    if not (
        provenance.source_reference_ids
        or provenance.upstream_artifact_ids
        or provenance.data_snapshot_id is not None
        or provenance.experiment_id is not None
    ):
        failures.append("Provenance is missing source or upstream linkage.")
    return failures


def _signal_target_type(signal: Signal | StrategyVariantSignal) -> str:
    return "signal" if isinstance(signal, Signal) else "strategy_variant_signal"


def _metric(
    *,
    evaluation_report_id: str,
    dimension: EvaluationDimension,
    metric_name: str,
    target_type: str,
    target_id: str,
    status: EvaluationStatus,
    metric_value: MetricValue,
    threshold: float | None,
    notes: list[str],
    clock: Clock,
    workflow_run_id: str,
) -> EvaluationMetric:
    return EvaluationMetric(
        evaluation_metric_id=make_canonical_id("evalm", evaluation_report_id, target_id, metric_name),
        evaluation_report_id=evaluation_report_id,
        dimension=dimension,
        metric_name=metric_name,
        target_type=target_type,
        target_id=target_id,
        status=status,
        metric_value=metric_value,
        threshold=threshold,
        notes=notes,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day10_evaluation_metric",
            upstream_artifact_ids=[target_id, metric_value.metric_value_id],
            workflow_run_id=workflow_run_id,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _failure_case(
    *,
    evaluation_report_id: str,
    target_type: str,
    target_id: str,
    failure_kind: FailureCaseKind,
    severity: Severity,
    blocking: bool,
    message: str,
    related_artifact_ids: list[str],
    suspected_cause: str | None,
    clock: Clock,
    workflow_run_id: str,
) -> FailureCase:
    return FailureCase(
        failure_case_id=make_canonical_id(
            "fcase",
            evaluation_report_id,
            target_id,
            failure_kind.value,
        ),
        evaluation_report_id=evaluation_report_id,
        target_type=target_type,
        target_id=target_id,
        failure_kind=failure_kind,
        severity=severity,
        blocking=blocking,
        message=message,
        related_artifact_ids=related_artifact_ids,
        suspected_cause=suspected_cause,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day10_failure_case",
            upstream_artifact_ids=[target_id, *related_artifact_ids],
            workflow_run_id=workflow_run_id,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _robustness_check(
    *,
    evaluation_report_id: str,
    check_kind: RobustnessCheckKind,
    target_type: str,
    target_id: str,
    status: EvaluationStatus,
    severity: Severity,
    message: str,
    related_artifact_ids: list[str],
    clock: Clock,
    workflow_run_id: str,
) -> RobustnessCheck:
    return RobustnessCheck(
        robustness_check_id=make_canonical_id(
            "rbst",
            evaluation_report_id,
            target_id,
            check_kind.value,
        ),
        evaluation_report_id=evaluation_report_id,
        check_kind=check_kind,
        target_type=target_type,
        target_id=target_id,
        status=status,
        severity=severity,
        message=message,
        related_artifact_ids=related_artifact_ids,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day10_robustness_check",
            upstream_artifact_ids=[target_id, *related_artifact_ids],
            workflow_run_id=workflow_run_id,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _coverage_summary(
    *,
    evaluation_report_id: str,
    dimension: EvaluationDimension,
    target_type: str,
    target_id: str,
    covered_count: int,
    missing_count: int,
    notes: list[str],
    clock: Clock,
    workflow_run_id: str,
) -> CoverageSummary:
    total_count = covered_count + missing_count
    ratio = 0.0 if total_count == 0 else covered_count / total_count
    return CoverageSummary(
        coverage_summary_id=make_canonical_id(
            "covsum",
            evaluation_report_id,
            target_id,
            dimension.value,
        ),
        evaluation_report_id=evaluation_report_id,
        dimension=dimension,
        target_type=target_type,
        target_id=target_id,
        covered_count=covered_count,
        missing_count=missing_count,
        total_count=total_count,
        coverage_ratio=ratio,
        notes=notes,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day10_coverage_summary",
            upstream_artifact_ids=[target_id],
            workflow_run_id=workflow_run_id,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _numeric_metric_value(
    *,
    evaluation_report_id: str,
    metric_name: str,
    target_id: str,
    numeric_value: float,
    unit: str | None,
    clock: Clock,
) -> MetricValue:
    return MetricValue(
        metric_value_id=make_canonical_id("mval", evaluation_report_id, target_id, metric_name),
        numeric_value=numeric_value,
        boolean_value=None,
        text_value=None,
        unit=unit,
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _boolean_metric_value(
    *,
    evaluation_report_id: str,
    metric_name: str,
    target_id: str,
    boolean_value: bool,
    clock: Clock,
) -> MetricValue:
    return MetricValue(
        metric_value_id=make_canonical_id("mval", evaluation_report_id, target_id, metric_name),
        numeric_value=None,
        boolean_value=boolean_value,
        text_value=None,
        unit=None,
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _text_metric_value(
    *,
    evaluation_report_id: str,
    metric_name: str,
    target_id: str,
    text_value: str,
    clock: Clock,
) -> MetricValue:
    return MetricValue(
        metric_value_id=make_canonical_id("mval", evaluation_report_id, target_id, metric_name),
        numeric_value=None,
        boolean_value=None,
        text_value=text_value,
        unit=None,
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def build_evaluation_report(
    *,
    evaluation_report_id: str,
    target_type: str,
    target_id: str,
    artifacts: EvaluationArtifacts,
    clock: Clock,
    workflow_run_id: str,
) -> EvaluationReport:
    """Build the primary evaluation report from accumulated outputs."""

    return EvaluationReport(
        evaluation_report_id=evaluation_report_id,
        target_type=target_type,
        target_id=target_id,
        generated_at=clock.now(),
        overall_status=derive_overall_status(artifacts=artifacts),
        metric_ids=[metric.evaluation_metric_id for metric in artifacts.metrics],
        failure_case_ids=[failure.failure_case_id for failure in artifacts.failure_cases],
        robustness_check_ids=[
            robustness_check.robustness_check_id
            for robustness_check in artifacts.robustness_checks
        ],
        comparison_summary_id=(
            artifacts.comparison_summary.comparison_summary_id
            if artifacts.comparison_summary is not None
            else None
        ),
        coverage_summary_ids=[
            coverage_summary.coverage_summary_id
            for coverage_summary in artifacts.coverage_summaries
        ],
        notes=artifacts.notes,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day10_evaluation_report",
            upstream_artifact_ids=[
                target_id,
                *[metric.evaluation_metric_id for metric in artifacts.metrics],
                *[failure.failure_case_id for failure in artifacts.failure_cases],
                *[
                    robustness_check.robustness_check_id
                    for robustness_check in artifacts.robustness_checks
                ],
                *[
                    coverage_summary.coverage_summary_id
                    for coverage_summary in artifacts.coverage_summaries
                ],
                *(
                    [artifacts.comparison_summary.comparison_summary_id]
                    if artifacts.comparison_summary is not None
                    else []
                ),
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _artifact_id(artifact: StrictModel) -> str:
    for field_name in (
        "ablation_config_id",
        "ablation_result_id",
        "evaluation_slice_id",
        "hypothesis_id",
        "counter_hypothesis_id",
        "research_brief_id",
        "evidence_assessment_id",
        "feature_id",
        "signal_score_id",
        "signal_id",
        "strategy_variant_signal_id",
        "strategy_variant_id",
        "strategy_spec_id",
        "backtest_run_id",
        "performance_summary_id",
        "benchmark_reference_id",
        "data_snapshot_id",
        "dataset_reference_id",
        "experiment_id",
        "portfolio_proposal_id",
        "position_idea_id",
        "paper_trade_id",
        "review_decision_id",
        "risk_check_id",
    ):
        value = getattr(artifact, field_name, None)
        if value:
            return cast(str, value)
    for field_name in getattr(type(artifact), "model_fields", {}):
        if not field_name.endswith("_id"):
            continue
        value = getattr(artifact, field_name, None)
        if value:
            return cast(str, value)
    raise ValueError(f"Unable to resolve canonical artifact ID for {type(artifact).__name__}.")


def _artifact_type_name(artifact: StrictModel) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", type(artifact).__name__).lower()


def _ratio_status(*, covered_count: int, total_count: int) -> EvaluationStatus:
    if total_count == 0 or covered_count == 0:
        return EvaluationStatus.FAIL
    if covered_count < total_count:
        return EvaluationStatus.WARN
    return EvaluationStatus.PASS


def _duplicates(values: list[str]) -> list[str]:
    return sorted([value for value, count in Counter(values).items() if count > 1])
