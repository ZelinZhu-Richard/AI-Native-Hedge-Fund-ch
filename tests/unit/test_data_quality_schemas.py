from __future__ import annotations

from datetime import UTC, datetime

import pytest

from libraries.schemas import (
    ContractViolation,
    DataQualityIssue,
    InputCompletenessReport,
    ProvenanceRecord,
    QualityDecision,
    QualitySeverity,
    RefusalReason,
    ValidationGate,
)

FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(
        source_reference_ids=["src_test"],
        upstream_artifact_ids=["artifact_test"],
        transformation_name="unit_test",
        processing_time=FIXED_NOW,
    )


def test_validation_gate_requires_refusal_reason_for_blocking_decisions() -> None:
    with pytest.raises(ValueError, match="refusal_reason is required"):
        ValidationGate(
            validation_gate_id="vgate_test",
            gate_name="signal_generation_output",
            workflow_name="signal_generation",
            step_name="signal_output",
            target_type="signal_output",
            target_id="co_test",
            decision=QualityDecision.REFUSE,
            refusal_reason=None,
            quarantined=False,
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_validation_gate_requires_quarantine_flag_for_quarantine_decision() -> None:
    with pytest.raises(ValueError, match="quarantined must be true"):
        ValidationGate(
            validation_gate_id="vgate_test",
            gate_name="evidence_bundle",
            workflow_name="evidence_extraction",
            step_name="bundle_validation",
            target_type="document_evidence_bundle",
            target_id="doc_test",
            decision=QualityDecision.QUARANTINE,
            refusal_reason=RefusalReason.STRUCTURALLY_INVALID_OUTPUT,
            quarantined=False,
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_input_completeness_report_requires_consistent_field_sets() -> None:
    with pytest.raises(ValueError, match="present_fields must be a subset"):
        InputCompletenessReport(
            input_completeness_report_id="qreport_test",
            target_type="signal_output",
            target_id="co_test",
            required_fields=["signals"],
            present_fields=["signals", "signal_scores"],
            missing_fields=[],
            completeness_ratio=1.0,
            decision=QualityDecision.WARN,
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_issue_and_violation_require_target_and_message() -> None:
    with pytest.raises(ValueError, match="target_id must be non-empty"):
        DataQualityIssue(
            data_quality_issue_id="qissue_test",
            check_name="Signal output presence",
            check_code="signal_output_presence",
            target_type="signal_output",
            target_id="",
            severity=QualitySeverity.LOW,
            blocking=False,
            message="Missing output.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )

    with pytest.raises(ValueError, match="message must be non-empty"):
        ContractViolation(
            contract_violation_id="cviol_test",
            contract_name="signal_requires_lineage",
            target_type="signal",
            target_id="sig_test",
            severity=QualitySeverity.HIGH,
            blocking=True,
            refusal_reason=RefusalReason.BROKEN_SIGNAL_LINEAGE,
            message="",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )
