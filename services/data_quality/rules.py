from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from libraries.schemas import (
    DataQualityIssue,
    Document,
    DocumentKind,
    FailureCase,
    FailureCaseKind,
    ProvenanceRecord,
    QualityDecision,
    QualitySeverity,
    RefusalReason,
    Severity,
)


@dataclass(frozen=True)
class CompletenessField:
    """One required field or semantic requirement checked by a validation gate."""

    name: str
    present: bool


def provenance_failures(
    provenance: ProvenanceRecord,
    *,
    require_lineage_link: bool = True,
) -> list[str]:
    """Return missing minimum provenance elements for one artifact."""

    failures: list[str] = []
    if provenance.processing_time is None:
        failures.append("provenance.processing_time")
    if not provenance.transformation_name:
        failures.append("provenance.transformation_name")
    if (
        require_lineage_link
        and not provenance.source_reference_ids
        and not provenance.upstream_artifact_ids
    ):
        failures.append("provenance.source_reference_ids_or_upstream_artifact_ids")
    return failures


def has_usable_source_timing(document_or_source: object) -> bool:
    """Return whether one source-like or document-like artifact has a usable timing anchor."""

    publication_timing = getattr(document_or_source, "publication_timing", None)
    if publication_timing is not None and publication_timing.internal_available_at is not None:
        return True
    for field_name in ("published_at", "source_published_at", "effective_at"):
        if getattr(document_or_source, field_name, None) is not None:
            return True
    return False


def requires_company_link(document: Document) -> bool:
    """Return whether a normalized document should carry a company identifier."""

    return document.kind in {DocumentKind.FILING, DocumentKind.EARNINGS_CALL}


def review_state_invalid(*, review_status: object | None, validation_status: object | None) -> bool:
    """Return whether a review or validation state should block downstream promotion."""

    return getattr(review_status, "value", None) == "rejected" or getattr(
        validation_status, "value", None
    ) == "invalidated"


def highest_quality_severity(levels: Iterable[QualitySeverity]) -> QualitySeverity:
    """Return the highest quality severity in one iterable."""

    ordering = {
        QualitySeverity.LOW: 1,
        QualitySeverity.MEDIUM: 2,
        QualitySeverity.HIGH: 3,
        QualitySeverity.CRITICAL: 4,
    }
    highest = QualitySeverity.LOW
    for level in levels:
        if ordering[level] > ordering[highest]:
            highest = level
    return highest


def quality_severity_from_severity(severity: Severity) -> QualitySeverity:
    """Map a generic repository severity to the quality-layer severity scale."""

    mapping = {
        Severity.INFO: QualitySeverity.LOW,
        Severity.LOW: QualitySeverity.LOW,
        Severity.MEDIUM: QualitySeverity.MEDIUM,
        Severity.HIGH: QualitySeverity.HIGH,
        Severity.CRITICAL: QualitySeverity.CRITICAL,
    }
    return mapping[severity]


def refusal_reason_from_failure_case(failure_case: FailureCase) -> RefusalReason:
    """Map an evaluation failure case to a quality-layer refusal reason."""

    if failure_case.failure_kind is FailureCaseKind.MISSING_PROVENANCE:
        return RefusalReason.MISSING_PROVENANCE
    if failure_case.failure_kind is FailureCaseKind.BROKEN_LINEAGE:
        return RefusalReason.BROKEN_SIGNAL_LINEAGE
    if failure_case.failure_kind is FailureCaseKind.INCOMPLETE_CONFIG:
        return RefusalReason.MISSING_REQUIRED_ARTIFACT
    return RefusalReason.STRUCTURALLY_INVALID_OUTPUT


def quality_decision_for_findings(
    *,
    issues: list[DataQualityIssue],
    blocking_violation_count: int,
    quarantine_on_blocking: bool,
) -> QualityDecision:
    """Resolve one quality decision from the recorded findings."""

    if blocking_violation_count > 0:
        return QualityDecision.QUARANTINE if quarantine_on_blocking else QualityDecision.REFUSE
    if issues:
        return QualityDecision.WARN
    return QualityDecision.PASS


def completeness_ratio(fields: list[CompletenessField]) -> float:
    """Return the completeness ratio for one field set."""

    if not fields:
        return 1.0
    present_count = sum(1 for field in fields if field.present)
    return present_count / len(fields)


def completeness_lists(
    fields: list[CompletenessField],
) -> tuple[list[str], list[str], list[str], float]:
    """Return required, present, missing lists plus the completeness ratio."""

    required_fields = [field.name for field in fields]
    present_fields = [field.name for field in fields if field.present]
    missing_fields = [field.name for field in fields if not field.present]
    return required_fields, present_fields, missing_fields, completeness_ratio(fields)
