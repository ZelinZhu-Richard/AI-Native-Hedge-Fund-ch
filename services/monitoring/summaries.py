from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from urllib.parse import urlparse

from libraries.schemas import (
    AlertRecord,
    ArtifactStorageLocation,
    EvaluationReport,
    EvaluationStatus,
    FailureCase,
    HealthCheck,
    HealthCheckStatus,
    RobustnessCheck,
    RunSummary,
    WorkflowStatus,
)


def dedupe_preserve_order(values: Sequence[str | None]) -> list[str]:
    """Return unique non-empty values while preserving the original order."""

    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def artifact_ids_from_storage_locations(
    storage_locations: list[ArtifactStorageLocation],
) -> list[str]:
    """Return artifact identifiers referenced by storage locations."""

    return dedupe_preserve_order([location.artifact_id for location in storage_locations])


def artifact_counts_from_storage_locations(
    storage_locations: list[ArtifactStorageLocation],
) -> dict[str, int]:
    """Summarize artifact counts by the final persisted directory name."""

    counts: dict[str, int] = {}
    for location in storage_locations:
        parsed = urlparse(location.uri)
        category = Path(parsed.path).parent.name or "unknown"
        counts[category] = counts.get(category, 0) + 1
    return counts


def merged_artifact_counts(
    *,
    storage_locations: list[ArtifactStorageLocation],
    explicit_counts: dict[str, int] | None = None,
) -> dict[str, int]:
    """Merge explicit counts on top of counts derived from storage locations."""

    counts = artifact_counts_from_storage_locations(storage_locations)
    for category, count in (explicit_counts or {}).items():
        counts[category] = counts.get(category, 0) + count
    return counts


def derive_ablation_run_status(
    *,
    evaluation_report: EvaluationReport | None,
    failure_cases: list[FailureCase],
    robustness_checks: list[RobustnessCheck],
) -> WorkflowStatus:
    """Map ablation evaluation outcomes into a conservative monitoring status."""

    if evaluation_report is None:
        return WorkflowStatus.ATTENTION_REQUIRED
    if evaluation_report.overall_status is EvaluationStatus.FAIL:
        return WorkflowStatus.ATTENTION_REQUIRED
    if any(case.blocking for case in failure_cases):
        return WorkflowStatus.ATTENTION_REQUIRED
    if evaluation_report.overall_status in {EvaluationStatus.WARN, EvaluationStatus.FAIL}:
        return WorkflowStatus.ATTENTION_REQUIRED
    if any(check.status.value in {"warn", "fail"} for check in robustness_checks):
        return WorkflowStatus.ATTENTION_REQUIRED
    return WorkflowStatus.SUCCEEDED


def attention_reasons_from_ablation(
    *,
    evaluation_report: EvaluationReport | None,
    failure_cases: list[FailureCase],
    robustness_checks: list[RobustnessCheck],
) -> list[str]:
    """Extract concise operator-facing attention reasons from evaluation output."""

    reasons: list[str] = []
    if evaluation_report is not None and evaluation_report.overall_status in {
        EvaluationStatus.WARN,
        EvaluationStatus.FAIL,
    }:
        reasons.append(f"evaluation_overall_status={evaluation_report.overall_status.value}")
    reasons.extend(case.message for case in failure_cases[:3])
    reasons.extend(check.message for check in robustness_checks[:3])
    return dedupe_preserve_order(reasons)


def derive_service_status(
    *,
    recent_run_summaries: list[RunSummary],
    recent_health_checks: list[HealthCheck],
    open_alerts: list[AlertRecord],
) -> HealthCheckStatus:
    """Derive one conservative service status from recent runs, checks, and alerts."""

    if any(check.status is HealthCheckStatus.FAIL for check in recent_health_checks):
        return HealthCheckStatus.FAIL
    if any(summary.status is WorkflowStatus.FAILED for summary in recent_run_summaries):
        return HealthCheckStatus.FAIL
    if any(alert.severity.value in {"high", "critical"} for alert in open_alerts):
        return HealthCheckStatus.FAIL
    if any(check.status is HealthCheckStatus.WARN for check in recent_health_checks):
        return HealthCheckStatus.WARN
    if any(
        summary.status in {WorkflowStatus.PARTIAL, WorkflowStatus.ATTENTION_REQUIRED}
        for summary in recent_run_summaries
    ):
        return HealthCheckStatus.WARN
    if open_alerts:
        return HealthCheckStatus.WARN
    return HealthCheckStatus.PASS
