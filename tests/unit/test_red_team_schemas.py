from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    AdversarialInput,
    EvaluationStatus,
    FailureSeverity,
    GuardrailViolation,
    RecommendedMitigation,
    RedTeamCase,
    SafetyFinding,
    Severity,
)
from libraries.schemas.base import ProvenanceRecord

FIXED_NOW = datetime(2026, 3, 19, 14, 0, tzinfo=UTC)
FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "red_team"
    / "unsupported_claim_payload.json"
)


def test_failure_severity_reuses_shared_severity_scale() -> None:
    assert FailureSeverity.HIGH is Severity.HIGH


def test_red_team_schema_bundle_validates() -> None:
    adversarial_input = AdversarialInput(
        adversarial_input_id="ainput_test",
        input_kind="summary_override",
        description="Inject overstrong language into a cloned signal summary.",
        target_type="signal",
        target_id="sig_test",
        related_artifact_ids=["sig_test"],
        fixture_path=str(FIXTURE_PATH),
        payload_summary="must buy and guaranteed upside",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    mitigation = RecommendedMitigation(
        recommended_mitigation_id="mitig_test",
        summary="Remove unsupported language.",
        required_action="Require evidence-backed wording before promotion.",
        owner_hint="research_review",
        blocking=True,
        provenance=_provenance(),
    )
    violation = GuardrailViolation(
        guardrail_violation_id="gviol_test",
        red_team_case_id="rtcase_test",
        guardrail_name="claim_strength_matches_support",
        target_type="signal",
        target_id="sig_test",
        severity=FailureSeverity.HIGH,
        blocking=True,
        message="Overstrong language is not supported by the signal inputs.",
        related_artifact_ids=["sig_test"],
        recommended_mitigations=[mitigation],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    finding = SafetyFinding(
        safety_finding_id="sfind_test",
        red_team_case_id="rtcase_test",
        target_type="signal",
        target_id="sig_test",
        status=EvaluationStatus.FAIL,
        summary="Guardrails were triggered for the cloned signal.",
        guardrail_violation_ids=[violation.guardrail_violation_id],
        exposed_weaknesses=["unsupported_causal_claim"],
        related_artifact_ids=["sig_test", violation.guardrail_violation_id],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    red_team_case = RedTeamCase(
        red_team_case_id="rtcase_test",
        name="Unsupported signal claim",
        scenario_name="unsupported_causal_claim",
        target_type="signal",
        target_id="sig_test",
        adversarial_inputs=[adversarial_input],
        expected_guardrails=["claim_strength_matches_support"],
        outcome_status=EvaluationStatus.FAIL,
        guardrail_violation_ids=[violation.guardrail_violation_id],
        safety_finding_ids=[finding.safety_finding_id],
        executed_at=FIXED_NOW,
        notes=["Unit test case."],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert red_team_case.outcome_status is EvaluationStatus.FAIL
    assert violation.recommended_mitigations[0].blocking is True


def test_recommended_mitigation_requires_concrete_action() -> None:
    with pytest.raises(ValidationError):
        RecommendedMitigation(
            recommended_mitigation_id="mitig_test",
            summary="",
            required_action="",
            owner_hint="research_review",
            blocking=True,
            provenance=_provenance(),
        )


def test_red_team_case_requires_adversarial_inputs_and_guardrails() -> None:
    with pytest.raises(ValidationError):
        RedTeamCase(
            red_team_case_id="rtcase_test",
            name="Incomplete case",
            scenario_name="missing_provenance",
            target_type="signal",
            target_id="sig_test",
            adversarial_inputs=[],
            expected_guardrails=[],
            outcome_status=EvaluationStatus.FAIL,
            guardrail_violation_ids=["gviol_test"],
            safety_finding_ids=["sfinding_test"],
            executed_at=FIXED_NOW,
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
