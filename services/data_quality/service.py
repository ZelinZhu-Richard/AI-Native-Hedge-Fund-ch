from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pydantic import Field

from libraries.config import get_settings
from libraries.core import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    Company,
    ContractViolation,
    DataQualityCheck,
    DataQualityIssue,
    DatasetReference,
    Document,
    DocumentEvidenceBundle,
    ExperimentConfig,
    Feature,
    InputCompletenessReport,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionIdea,
    ProvenanceRecord,
    QualityDecision,
    QualitySeverity,
    RefusalReason,
    Signal,
    SignalScore,
    SourceReference,
    StrictModel,
    ValidationGate,
)
from libraries.utils import make_canonical_id, make_prefixed_id
from services.data_quality.rules import (
    CompletenessField,
    completeness_lists,
    has_usable_source_timing,
    highest_quality_severity,
    provenance_failures,
    quality_decision_for_findings,
    quality_severity_from_severity,
    refusal_reason_from_failure_case,
    requires_company_link,
    review_state_invalid,
)
from services.data_quality.storage import LocalDataQualityArtifactStore
from services.evaluation.checks import (
    evaluate_feature_lineage_completeness,
    evaluate_provenance_completeness,
    evaluate_signal_generation_validity,
)

if TYPE_CHECKING:
    from services.feature_store.loaders import LoadedFeatureMappingInputs


class _ProvenancedArtifact(Protocol):
    """Minimal contract for internal checks that require provenance access."""

    provenance: ProvenanceRecord


class ValidationGateResult(StrictModel):
    """Structured output of one executed data-quality gate."""

    validation_gate: ValidationGate = Field(description="Persisted validation gate artifact.")
    data_quality_checks: list[DataQualityCheck] = Field(
        default_factory=list,
        description="Executed quality checks for the gate.",
    )
    data_quality_issues: list[DataQualityIssue] = Field(
        default_factory=list,
        description="Recorded data-quality issues for the gate.",
    )
    contract_violations: list[ContractViolation] = Field(
        default_factory=list,
        description="Recorded contract violations for the gate.",
    )
    input_completeness_report: InputCompletenessReport | None = Field(
        default=None,
        description="Optional completeness report for the gate.",
    )
    storage_locations: list[ArtifactStorageLocation] = Field(
        default_factory=list,
        description="Persisted storage locations for all gate artifacts.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes attached to the gate execution.",
    )


class DataQualityRefusalError(ValueError):
    """Typed refusal raised when a validation gate blocks downstream progression."""

    def __init__(self, result: ValidationGateResult) -> None:
        self.result = result
        gate = result.validation_gate
        reason = gate.refusal_reason.value if gate.refusal_reason is not None else "unspecified"
        super().__init__(
            f"{gate.gate_name} blocked `{gate.target_type}` `{gate.target_id}` with "
            f"`{gate.decision.value}` ({reason})."
        )

    @property
    def storage_locations(self) -> list[ArtifactStorageLocation]:
        """Expose persisted quality-artifact storage locations."""

        return self.result.storage_locations


class DataQualityService(BaseService):
    """Validate core artifacts before downstream admission and persist refusal decisions."""

    capability_name = "data_quality"
    capability_description = "Validates core artifacts, records contract violations, and blocks unsafe downstream use."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=[
                "normalized artifacts",
                "evidence bundles",
                "features",
                "signals",
                "portfolio proposals",
                "paper-trade requests",
                "experiment metadata",
            ],
            produces=[
                "ValidationGate",
                "DataQualityCheck",
                "DataQualityIssue",
                "ContractViolation",
                "InputCompletenessReport",
            ],
            api_routes=[],
        )

    def validate_ingestion_normalization(
        self,
        *,
        source_reference: SourceReference,
        company: Company | None,
        document: Document | None,
        workflow_run_id: str,
        requested_by: str,
        output_root: Path | None = None,
        raise_on_failure: bool = True,
    ) -> ValidationGateResult:
        """Validate normalized ingestion outputs before normal downstream persistence."""

        target_type = "document" if document is not None else "source_reference"
        target_id = document.document_id if document is not None else source_reference.source_reference_id
        gate_id = self._gate_id("ingestion_normalization", target_id)
        source_reference_ids = [source_reference.source_reference_id]
        now = self.clock.now()
        notes = [f"requested_by={requested_by}"]

        completeness_fields = [
            CompletenessField(
                "source_reference.timing_anchor",
                has_usable_source_timing(source_reference),
            ),
            CompletenessField(
                "source_reference.provenance.processing_time",
                source_reference.provenance.processing_time is not None,
            ),
            CompletenessField(
                "source_reference.provenance.transformation_name",
                bool(source_reference.provenance.transformation_name),
            ),
        ]
        if document is not None:
            completeness_fields.extend(
                [
                    CompletenessField(
                        "document.timing_anchor",
                        has_usable_source_timing(document),
                    ),
                    CompletenessField(
                        "document.provenance.processing_time",
                        document.provenance.processing_time is not None,
                    ),
                    CompletenessField(
                        "document.provenance.transformation_name",
                        bool(document.provenance.transformation_name),
                    ),
                ]
            )
            if requires_company_link(document):
                completeness_fields.append(
                    CompletenessField(
                        "document.company_id",
                        bool(document.company_id),
                    )
                )
        if company is not None:
            completeness_fields.extend(
                [
                    CompletenessField("company.company_id", bool(company.company_id)),
                    CompletenessField(
                        "company.provenance.processing_time",
                        company.provenance.processing_time is not None,
                    ),
                    CompletenessField(
                        "company.provenance.transformation_name",
                        bool(company.provenance.transformation_name),
                    ),
                ]
            )

        report = self._completeness_report(
            report_id=self._report_id("ingestion_normalization", target_id),
            target_type=target_type,
            target_id=target_id,
            fields=completeness_fields,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            decision=(
                QualityDecision.PASS
                if all(field.present for field in completeness_fields)
                else QualityDecision.WARN
            ),
            notes=[],
            now=now,
        )

        issues: list[DataQualityIssue] = []
        violations: list[ContractViolation] = []

        if source_reference.published_at is None and source_reference.effective_at is not None:
            issues.append(
                self._issue(
                    issue_id=self._issue_id("source_publication_timestamp_missing", source_reference.source_reference_id),
                    check_name="Source timing visibility",
                    check_code="source_timing_visibility",
                    target_type="source_reference",
                    target_id=source_reference.source_reference_id,
                    message="Source publication timestamp is missing, so source timing relies on the effective timestamp fallback.",
                    severity=QualitySeverity.MEDIUM,
                    blocking=False,
                    field_paths=["published_at", "effective_at"],
                    related_artifact_ids=[source_reference.source_reference_id],
                    workflow_name="fixture_ingestion",
                    step_name="fixture_refresh_and_normalization",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )

        if not has_usable_source_timing(source_reference):
            violations.append(
                self._violation(
                    violation_id=self._violation_id("source_required_timing_missing", source_reference.source_reference_id),
                    contract_name="normalized_source_reference_requires_timing_anchor",
                    target_type="source_reference",
                    target_id=source_reference.source_reference_id,
                    refusal_reason=RefusalReason.MISSING_REQUIRED_TIMESTAMP,
                    message="Normalized source reference is missing both publication and effective timing anchors.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=["published_at", "effective_at", "publication_timing.internal_available_at"],
                    related_artifact_ids=[source_reference.source_reference_id],
                    workflow_name="fixture_ingestion",
                    step_name="fixture_refresh_and_normalization",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )

        source_provenance_failures = provenance_failures(
            source_reference.provenance,
            require_lineage_link=False,
        )
        if source_provenance_failures:
            violations.append(
                self._violation(
                    violation_id=self._violation_id("source_provenance_missing", source_reference.source_reference_id),
                    contract_name="normalized_source_reference_requires_minimum_provenance",
                    target_type="source_reference",
                    target_id=source_reference.source_reference_id,
                    refusal_reason=RefusalReason.MISSING_PROVENANCE,
                    message="Normalized source reference is missing minimum provenance fields.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=source_provenance_failures,
                    related_artifact_ids=[source_reference.source_reference_id],
                    workflow_name="fixture_ingestion",
                    step_name="fixture_refresh_and_normalization",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )

        if document is not None:
            if not has_usable_source_timing(document):
                violations.append(
                    self._violation(
                        violation_id=self._violation_id("document_required_timing_missing", document.document_id),
                        contract_name="normalized_document_requires_timing_anchor",
                        target_type="document",
                        target_id=document.document_id,
                        refusal_reason=RefusalReason.MISSING_REQUIRED_TIMESTAMP,
                        message="Normalized document is missing both publication and effective timing anchors.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=[
                            "source_published_at",
                            "effective_at",
                            "publication_timing.internal_available_at",
                        ],
                        related_artifact_ids=[document.document_id],
                        workflow_name="fixture_ingestion",
                        step_name="fixture_refresh_and_normalization",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )
            document_provenance_failures = provenance_failures(document.provenance)
            if document_provenance_failures:
                violations.append(
                    self._violation(
                        violation_id=self._violation_id("document_provenance_missing", document.document_id),
                        contract_name="normalized_document_requires_minimum_provenance",
                        target_type="document",
                        target_id=document.document_id,
                        refusal_reason=RefusalReason.MISSING_PROVENANCE,
                        message="Normalized document is missing minimum provenance fields.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=document_provenance_failures,
                        related_artifact_ids=[document.document_id],
                        workflow_name="fixture_ingestion",
                        step_name="fixture_refresh_and_normalization",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )
            if requires_company_link(document) and (company is None or not document.company_id):
                violations.append(
                    self._violation(
                        violation_id=self._violation_id("document_company_link_missing", document.document_id),
                        contract_name="company_specific_document_requires_entity_linkage",
                        target_type="document",
                        target_id=document.document_id,
                        refusal_reason=RefusalReason.MISSING_ENTITY_LINKAGE,
                        message="Company-specific normalized document is missing a company linkage.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=["company_id"],
                        related_artifact_ids=[document.document_id],
                        workflow_name="fixture_ingestion",
                        step_name="fixture_refresh_and_normalization",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )
            if company is not None and document.company_id and document.company_id != company.company_id:
                violations.append(
                    self._violation(
                        violation_id=self._violation_id("document_company_link_mismatch", document.document_id),
                        contract_name="normalized_document_company_link_must_match_company_record",
                        target_type="document",
                        target_id=document.document_id,
                        refusal_reason=RefusalReason.MISSING_ENTITY_LINKAGE,
                        message="Normalized document company_id does not match the normalized company record.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=["company_id"],
                        related_artifact_ids=[document.document_id, company.company_id],
                        workflow_name="fixture_ingestion",
                        step_name="fixture_refresh_and_normalization",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )

        if company is not None:
            company_provenance_failures = provenance_failures(company.provenance)
            if company_provenance_failures:
                violations.append(
                    self._violation(
                        violation_id=self._violation_id("company_provenance_missing", company.company_id),
                        contract_name="normalized_company_requires_minimum_provenance",
                        target_type="company",
                        target_id=company.company_id,
                        refusal_reason=RefusalReason.MISSING_PROVENANCE,
                        message="Normalized company is missing minimum provenance fields.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=company_provenance_failures,
                        related_artifact_ids=[company.company_id],
                        workflow_name="fixture_ingestion",
                        step_name="fixture_refresh_and_normalization",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )

        checks = self._build_checks(
            gate_id=gate_id,
            target_type=target_type,
            target_id=target_id,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            now=now,
            specs=[
                ("source_timing_visibility", "Source timing visibility", issues, []),
                (
                    "normalized_ingestion_provenance",
                    "Normalized ingestion provenance",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is RefusalReason.MISSING_PROVENANCE
                    ],
                ),
                (
                    "normalized_ingestion_entity_linkage",
                    "Normalized ingestion entity linkage",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is RefusalReason.MISSING_ENTITY_LINKAGE
                    ],
                ),
            ],
            quarantine_on_blocking=True,
        )

        return self._finalize_gate_result(
            gate_id=gate_id,
            gate_name="ingestion_normalization",
            workflow_name="fixture_ingestion",
            step_name="fixture_refresh_and_normalization",
            target_type=target_type,
            target_id=target_id,
            issues=issues,
            violations=violations,
            checks=checks,
            completeness_report=report,
            output_root=output_root,
            source_reference_ids=source_reference_ids,
            workflow_run_id=workflow_run_id,
            notes=notes,
            quarantine_on_blocking=True,
            raise_on_failure=raise_on_failure,
            now=now,
        )

    def validate_parsing_inputs(
        self,
        *,
        document: Document,
        source_reference: SourceReference,
        workflow_run_id: str,
        requested_by: str,
        output_root: Path | None = None,
        raise_on_failure: bool = True,
    ) -> ValidationGateResult:
        """Validate explicit parsing inputs before extraction begins."""

        gate_id = self._gate_id("parsing_inputs", document.document_id)
        now = self.clock.now()
        source_reference_ids = [source_reference.source_reference_id]
        notes = [f"requested_by={requested_by}"]
        completeness_fields = [
            CompletenessField("document.source_reference_id", bool(document.source_reference_id)),
            CompletenessField("source_reference.source_reference_id", bool(source_reference.source_reference_id)),
            CompletenessField("document.timing_anchor", has_usable_source_timing(document)),
            CompletenessField("source_reference.timing_anchor", has_usable_source_timing(source_reference)),
        ]
        if requires_company_link(document):
            completeness_fields.append(
                CompletenessField("document.company_id", bool(document.company_id))
            )
        report = self._completeness_report(
            report_id=self._report_id("parsing_inputs", document.document_id),
            target_type="document",
            target_id=document.document_id,
            fields=completeness_fields,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            decision=(
                QualityDecision.PASS
                if all(field.present for field in completeness_fields)
                else QualityDecision.WARN
            ),
            notes=[],
            now=now,
        )

        issues: list[DataQualityIssue] = []
        violations: list[ContractViolation] = []
        if document.source_reference_id != source_reference.source_reference_id:
            violations.append(
                self._violation(
                    violation_id=self._violation_id("parsing_input_source_reference_mismatch", document.document_id),
                    contract_name="parsing_inputs_source_reference_must_match_document",
                    target_type="document",
                    target_id=document.document_id,
                    refusal_reason=RefusalReason.MISSING_REQUIRED_ARTIFACT,
                    message="Parsing input source reference does not match the normalized document linkage.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=["document.source_reference_id", "source_reference.source_reference_id"],
                    related_artifact_ids=[document.document_id, source_reference.source_reference_id],
                    workflow_name="evidence_extraction",
                    step_name="parsing_inputs",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        for artifact, artifact_type, artifact_id, require_lineage_link in (
            (document, "document", document.document_id, True),
            (source_reference, "source_reference", source_reference.source_reference_id, False),
        ):
            missing = provenance_failures(
                artifact.provenance,
                require_lineage_link=require_lineage_link,
            )
            if missing:
                violations.append(
                    self._violation(
                        violation_id=self._violation_id(f"{artifact_type}_parsing_provenance_missing", artifact_id),
                        contract_name=f"{artifact_type}_requires_minimum_provenance_for_parsing",
                        target_type=artifact_type,
                        target_id=artifact_id,
                        refusal_reason=RefusalReason.MISSING_PROVENANCE,
                        message=f"{artifact_type.replace('_', ' ').title()} is missing minimum provenance required for parsing.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=missing,
                        related_artifact_ids=[artifact_id],
                        workflow_name="evidence_extraction",
                        step_name="parsing_inputs",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )
        if not has_usable_source_timing(document):
            violations.append(
                self._violation(
                    violation_id=self._violation_id("parsing_document_timing_missing", document.document_id),
                    contract_name="parseable_document_requires_timing_anchor",
                    target_type="document",
                    target_id=document.document_id,
                    refusal_reason=RefusalReason.MISSING_REQUIRED_TIMESTAMP,
                    message="Parseable normalized document is missing a usable timing anchor.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=["source_published_at", "effective_at", "publication_timing.internal_available_at"],
                    related_artifact_ids=[document.document_id],
                    workflow_name="evidence_extraction",
                    step_name="parsing_inputs",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        if requires_company_link(document) and not document.company_id:
            violations.append(
                self._violation(
                    violation_id=self._violation_id("parsing_document_company_missing", document.document_id),
                    contract_name="company_specific_parseable_document_requires_company_link",
                    target_type="document",
                    target_id=document.document_id,
                    refusal_reason=RefusalReason.MISSING_ENTITY_LINKAGE,
                    message="Company-specific parseable document is missing a company linkage.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=["company_id"],
                    related_artifact_ids=[document.document_id],
                    workflow_name="evidence_extraction",
                    step_name="parsing_inputs",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )

        checks = self._build_checks(
            gate_id=gate_id,
            target_type="document",
            target_id=document.document_id,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            now=now,
            specs=[
                (
                    "parsing_input_completeness",
                    "Parsing input completeness",
                    issues,
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason
                        in {
                            RefusalReason.MISSING_REQUIRED_TIMESTAMP,
                            RefusalReason.MISSING_REQUIRED_ARTIFACT,
                            RefusalReason.MISSING_ENTITY_LINKAGE,
                        }
                    ],
                ),
                (
                    "parsing_input_provenance",
                    "Parsing input provenance",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is RefusalReason.MISSING_PROVENANCE
                    ],
                ),
            ],
            quarantine_on_blocking=False,
        )

        return self._finalize_gate_result(
            gate_id=gate_id,
            gate_name="parsing_inputs",
            workflow_name="evidence_extraction",
            step_name="parsing_inputs",
            target_type="document",
            target_id=document.document_id,
            issues=issues,
            violations=violations,
            checks=checks,
            completeness_report=report,
            output_root=output_root,
            source_reference_ids=source_reference_ids,
            workflow_run_id=workflow_run_id,
            notes=notes,
            quarantine_on_blocking=False,
            raise_on_failure=raise_on_failure,
            now=now,
        )

    def validate_evidence_bundle(
        self,
        *,
        bundle: DocumentEvidenceBundle,
        workflow_run_id: str,
        requested_by: str,
        output_root: Path | None = None,
        raise_on_failure: bool = True,
    ) -> ValidationGateResult:
        """Validate a document evidence bundle before downstream persistence and reuse."""

        gate_id = self._gate_id("evidence_bundle", bundle.document_id)
        now = self.clock.now()
        source_reference_ids = [bundle.source_reference_id]
        notes = [f"requested_by={requested_by}", *bundle.evaluation.notes]
        completeness_fields = [
            CompletenessField(
                "parsed_document_text.canonical_text",
                bool(bundle.parsed_document_text.canonical_text),
            ),
            CompletenessField("segments", bool(bundle.segments)),
            CompletenessField("evidence_spans", bool(bundle.evidence_spans)),
            CompletenessField("evaluation.passed", bundle.evaluation.passed),
        ]
        if bundle.document_kind.value in {"filing", "earnings_call"}:
            completeness_fields.append(
                CompletenessField("company_id", bool(bundle.company_id))
            )
        report = self._completeness_report(
            report_id=self._report_id("evidence_bundle", bundle.document_id),
            target_type="document_evidence_bundle",
            target_id=bundle.document_id,
            fields=completeness_fields,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            decision=(
                QualityDecision.PASS
                if all(field.present for field in completeness_fields)
                else QualityDecision.WARN
            ),
            notes=bundle.evaluation.notes,
            now=now,
        )

        issues: list[DataQualityIssue] = []
        violations: list[ContractViolation] = []
        if not bundle.evaluation.passed:
            violations.append(
                self._violation(
                    violation_id=self._violation_id("evidence_bundle_evaluation_failed", bundle.document_id),
                    contract_name="document_evidence_bundle_requires_passing_integrity_evaluation",
                    target_type="document_evidence_bundle",
                    target_id=bundle.document_id,
                    refusal_reason=RefusalReason.STRUCTURALLY_INVALID_OUTPUT,
                    message="Document evidence bundle failed its integrity evaluation.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=[
                        "evaluation.reference_integrity_ok",
                        "evaluation.span_text_alignment_ok",
                        "evaluation.provenance_complete",
                    ],
                    related_artifact_ids=[bundle.document_id, bundle.parsed_document_text.parsed_document_text_id],
                    workflow_name="evidence_extraction",
                    step_name="bundle_validation",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        if not bundle.segments or not bundle.evidence_spans:
            violations.append(
                self._violation(
                    violation_id=self._violation_id("evidence_bundle_empty_core_outputs", bundle.document_id),
                    contract_name="document_evidence_bundle_requires_segments_and_spans",
                    target_type="document_evidence_bundle",
                    target_id=bundle.document_id,
                    refusal_reason=RefusalReason.STRUCTURALLY_INVALID_OUTPUT,
                    message="Document evidence bundle is missing segments or evidence spans.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=["segments", "evidence_spans"],
                    related_artifact_ids=[bundle.document_id],
                    workflow_name="evidence_extraction",
                    step_name="bundle_validation",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        if bundle.document_kind.value in {"filing", "earnings_call"} and not bundle.company_id:
            violations.append(
                self._violation(
                    violation_id=self._violation_id("evidence_bundle_company_missing", bundle.document_id),
                    contract_name="company_specific_evidence_bundle_requires_entity_linkage",
                    target_type="document_evidence_bundle",
                    target_id=bundle.document_id,
                    refusal_reason=RefusalReason.MISSING_ENTITY_LINKAGE,
                    message="Evidence bundle for a company-specific document is missing company linkage.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=["company_id"],
                    related_artifact_ids=[bundle.document_id],
                    workflow_name="evidence_extraction",
                    step_name="bundle_validation",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )

        provenance_artifacts: list[StrictModel] = [
            bundle.parsed_document_text,
            *bundle.segments,
            *bundle.evidence_spans,
            *bundle.claims,
            *bundle.risk_factors,
            *bundle.guidance_changes,
            *bundle.tone_markers,
        ]
        provenance_eval = evaluate_provenance_completeness(
            evaluation_report_id=self._evaluation_id("evidence_bundle_provenance", bundle.document_id),
            target_type="document_evidence_bundle",
            target_id=bundle.document_id,
            artifacts=provenance_artifacts,
            clock=self.clock,
            workflow_run_id=workflow_run_id,
        )
        violations.extend(
            self._violations_from_failure_cases(
                failure_cases=provenance_eval.failure_cases,
                workflow_name="evidence_extraction",
                step_name="bundle_validation",
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
                now=now,
            )
        )

        checks = self._build_checks(
            gate_id=gate_id,
            target_type="document_evidence_bundle",
            target_id=bundle.document_id,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            now=now,
            specs=[
                (
                    "document_evidence_integrity",
                    "Document evidence integrity",
                    issues,
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason
                        in {
                            RefusalReason.STRUCTURALLY_INVALID_OUTPUT,
                            RefusalReason.MISSING_ENTITY_LINKAGE,
                        }
                    ],
                ),
                (
                    "document_evidence_provenance",
                    "Document evidence provenance",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is RefusalReason.MISSING_PROVENANCE
                    ],
                ),
            ],
            quarantine_on_blocking=True,
        )

        return self._finalize_gate_result(
            gate_id=gate_id,
            gate_name="evidence_bundle",
            workflow_name="evidence_extraction",
            step_name="bundle_validation",
            target_type="document_evidence_bundle",
            target_id=bundle.document_id,
            issues=issues,
            violations=violations,
            checks=checks,
            completeness_report=report,
            output_root=output_root,
            source_reference_ids=source_reference_ids,
            workflow_run_id=workflow_run_id,
            notes=notes,
            quarantine_on_blocking=True,
            raise_on_failure=raise_on_failure,
            now=now,
        )

    def validate_feature_mapping_inputs(
        self,
        *,
        inputs: LoadedFeatureMappingInputs,
        workflow_run_id: str,
        requested_by: str,
        output_root: Path | None = None,
        raise_on_failure: bool = True,
    ) -> ValidationGateResult:
        """Validate research artifacts before they are admitted into feature mapping."""

        gate_id = self._gate_id("feature_mapping_inputs", inputs.company_id)
        now = self.clock.now()
        source_reference_ids = self._source_reference_ids(
            [artifact for artifact in (
                inputs.hypothesis,
                inputs.counter_hypothesis,
                inputs.evidence_assessment,
                inputs.research_brief,
                *inputs.guidance_changes,
                *inputs.risk_factors,
                *inputs.tone_markers,
            ) if artifact is not None]
        )
        notes = [f"requested_by={requested_by}"]
        completeness_fields = [
            CompletenessField("evidence_assessment", inputs.evidence_assessment is not None),
            CompletenessField("hypothesis", inputs.hypothesis is not None),
            CompletenessField("counter_hypothesis", inputs.counter_hypothesis is not None),
            CompletenessField("research_brief", inputs.research_brief is not None),
        ]
        report = self._completeness_report(
            report_id=self._report_id("feature_mapping_inputs", inputs.company_id),
            target_type="feature_mapping_inputs",
            target_id=inputs.company_id,
            fields=completeness_fields,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            decision=(
                QualityDecision.PASS
                if all(field.present for field in completeness_fields)
                else QualityDecision.WARN
            ),
            notes=[],
            now=now,
        )

        issues: list[DataQualityIssue] = []
        violations: list[ContractViolation] = []
        if inputs.hypothesis is None or inputs.counter_hypothesis is None or inputs.research_brief is None:
            violations.append(
                self._violation(
                    violation_id=self._violation_id("feature_mapping_required_research_missing", inputs.company_id),
                    contract_name="feature_mapping_requires_completed_research_slice",
                    target_type="feature_mapping_inputs",
                    target_id=inputs.company_id,
                    refusal_reason=RefusalReason.MISSING_REQUIRED_ARTIFACT,
                    message="Feature mapping requires hypothesis, counter-hypothesis, and research brief artifacts.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=["hypothesis", "counter_hypothesis", "research_brief"],
                    related_artifact_ids=[inputs.company_id],
                    workflow_name="feature_mapping",
                    step_name="feature_mapping_inputs",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )

        company_scoped_artifacts: list[
            tuple[_ProvenancedArtifact, str, str, str, object | None, object | None]
        ] = [
            (
                inputs.evidence_assessment,
                "evidence_assessment",
                inputs.evidence_assessment.evidence_assessment_id,
                inputs.evidence_assessment.company_id,
                inputs.evidence_assessment.review_status,
                inputs.evidence_assessment.validation_status,
            )
        ]
        if inputs.hypothesis is not None:
            company_scoped_artifacts.append(
                (
                    inputs.hypothesis,
                    "hypothesis",
                    inputs.hypothesis.hypothesis_id,
                    inputs.hypothesis.company_id,
                    inputs.hypothesis.review_status,
                    inputs.hypothesis.validation_status,
                )
            )
        if inputs.research_brief is not None:
            company_scoped_artifacts.append(
                (
                    inputs.research_brief,
                    "research_brief",
                    inputs.research_brief.research_brief_id,
                    inputs.research_brief.company_id,
                    inputs.research_brief.review_status,
                    inputs.research_brief.validation_status,
                )
            )

        for artifact, artifact_type, artifact_id, artifact_company_id, review_status, validation_status in company_scoped_artifacts:
            missing = provenance_failures(artifact.provenance)
            if missing:
                violations.append(
                    self._violation(
                        violation_id=self._violation_id(f"{artifact_type}_feature_provenance_missing", artifact_id),
                        contract_name=f"{artifact_type}_requires_minimum_provenance_for_feature_mapping",
                        target_type=artifact_type,
                        target_id=artifact_id,
                        refusal_reason=RefusalReason.MISSING_PROVENANCE,
                        message=f"{artifact_type.replace('_', ' ').title()} is missing minimum provenance required for feature mapping.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=missing,
                        related_artifact_ids=[artifact_id],
                        workflow_name="feature_mapping",
                        step_name="feature_mapping_inputs",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )
            if artifact_company_id != inputs.company_id:
                violations.append(
                    self._violation(
                        violation_id=self._violation_id(f"{artifact_type}_feature_company_mismatch", artifact_id),
                        contract_name=f"{artifact_type}_company_id_must_match_feature_mapping_company",
                        target_type=artifact_type,
                        target_id=artifact_id,
                        refusal_reason=RefusalReason.MISSING_ENTITY_LINKAGE,
                        message=f"{artifact_type.replace('_', ' ').title()} company_id does not match the feature-mapping company boundary.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=["company_id"],
                        related_artifact_ids=[artifact_id, inputs.company_id],
                        workflow_name="feature_mapping",
                        step_name="feature_mapping_inputs",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )
            if review_state_invalid(
                review_status=review_status,
                validation_status=validation_status,
            ):
                violations.append(
                    self._violation(
                        violation_id=self._violation_id(f"{artifact_type}_feature_review_invalid", artifact_id),
                        contract_name=f"{artifact_type}_must_not_be_rejected_or_invalidated_for_feature_mapping",
                        target_type=artifact_type,
                        target_id=artifact_id,
                        refusal_reason=RefusalReason.INVALID_REVIEW_STATE,
                        message=f"{artifact_type.replace('_', ' ').title()} is rejected or invalidated and cannot enter feature mapping.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=["review_status", "validation_status"],
                        related_artifact_ids=[artifact_id],
                        workflow_name="feature_mapping",
                        step_name="feature_mapping_inputs",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )

        if inputs.counter_hypothesis is not None:
            counter_hypothesis = inputs.counter_hypothesis
            missing = provenance_failures(counter_hypothesis.provenance)
            if missing:
                violations.append(
                    self._violation(
                        violation_id=self._violation_id(
                            "counter_hypothesis_feature_provenance_missing",
                            counter_hypothesis.counter_hypothesis_id,
                        ),
                        contract_name="counter_hypothesis_requires_minimum_provenance_for_feature_mapping",
                        target_type="counter_hypothesis",
                        target_id=counter_hypothesis.counter_hypothesis_id,
                        refusal_reason=RefusalReason.MISSING_PROVENANCE,
                        message="Counter hypothesis is missing minimum provenance required for feature mapping.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=missing,
                        related_artifact_ids=[counter_hypothesis.counter_hypothesis_id],
                        workflow_name="feature_mapping",
                        step_name="feature_mapping_inputs",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )
            if (
                inputs.hypothesis is not None
                and counter_hypothesis.hypothesis_id != inputs.hypothesis.hypothesis_id
            ):
                violations.append(
                    self._violation(
                        violation_id=self._violation_id(
                            "counter_hypothesis_feature_hypothesis_mismatch",
                            counter_hypothesis.counter_hypothesis_id,
                        ),
                        contract_name="counter_hypothesis_hypothesis_id_must_match_feature_mapping_hypothesis",
                        target_type="counter_hypothesis",
                        target_id=counter_hypothesis.counter_hypothesis_id,
                        refusal_reason=RefusalReason.MISSING_ENTITY_LINKAGE,
                        message=(
                            "Counter hypothesis does not match the primary hypothesis used for "
                            "feature mapping."
                        ),
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=["hypothesis_id"],
                        related_artifact_ids=[
                            counter_hypothesis.counter_hypothesis_id,
                            inputs.hypothesis.hypothesis_id,
                        ],
                        workflow_name="feature_mapping",
                        step_name="feature_mapping_inputs",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )
            if review_state_invalid(
                review_status=counter_hypothesis.review_status,
                validation_status=counter_hypothesis.validation_status,
            ):
                violations.append(
                    self._violation(
                        violation_id=self._violation_id(
                            "counter_hypothesis_feature_review_invalid",
                            counter_hypothesis.counter_hypothesis_id,
                        ),
                        contract_name="counter_hypothesis_must_not_be_rejected_or_invalidated_for_feature_mapping",
                        target_type="counter_hypothesis",
                        target_id=counter_hypothesis.counter_hypothesis_id,
                        refusal_reason=RefusalReason.INVALID_REVIEW_STATE,
                        message="Counter hypothesis is rejected or invalidated and cannot enter feature mapping.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=["review_status", "validation_status"],
                        related_artifact_ids=[counter_hypothesis.counter_hypothesis_id],
                        workflow_name="feature_mapping",
                        step_name="feature_mapping_inputs",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )

        checks = self._build_checks(
            gate_id=gate_id,
            target_type="feature_mapping_inputs",
            target_id=inputs.company_id,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            now=now,
            specs=[
                (
                    "feature_mapping_input_completeness",
                    "Feature-mapping input completeness",
                    issues,
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is RefusalReason.MISSING_REQUIRED_ARTIFACT
                    ],
                ),
                (
                    "feature_mapping_input_provenance",
                    "Feature-mapping input provenance",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is RefusalReason.MISSING_PROVENANCE
                    ],
                ),
                (
                    "feature_mapping_input_review_state",
                    "Feature-mapping input review state",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason in {RefusalReason.INVALID_REVIEW_STATE, RefusalReason.MISSING_ENTITY_LINKAGE}
                    ],
                ),
            ],
            quarantine_on_blocking=False,
        )

        return self._finalize_gate_result(
            gate_id=gate_id,
            gate_name="feature_mapping_inputs",
            workflow_name="feature_mapping",
            step_name="feature_mapping_inputs",
            target_type="feature_mapping_inputs",
            target_id=inputs.company_id,
            issues=issues,
            violations=violations,
            checks=checks,
            completeness_report=report,
            output_root=output_root,
            source_reference_ids=source_reference_ids,
            workflow_run_id=workflow_run_id,
            notes=notes,
            quarantine_on_blocking=False,
            raise_on_failure=raise_on_failure,
            now=now,
        )

    def validate_feature_output(
        self,
        *,
        company_id: str,
        features: list[Feature],
        workflow_run_id: str,
        requested_by: str,
        output_root: Path | None = None,
        raise_on_failure: bool = True,
    ) -> ValidationGateResult:
        """Validate emitted feature artifacts before persistence."""

        gate_id = self._gate_id("feature_output", company_id)
        now = self.clock.now()
        source_reference_ids = self._source_reference_ids(features)
        notes = [f"requested_by={requested_by}"]
        report = self._completeness_report(
            report_id=self._report_id("feature_output", company_id),
            target_type="feature_output",
            target_id=company_id,
            fields=[CompletenessField("features", bool(features))],
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            decision=QualityDecision.PASS if features else QualityDecision.WARN,
            notes=["No feature artifacts were emitted." ] if not features else [],
            now=now,
        )
        issues: list[DataQualityIssue] = []
        violations: list[ContractViolation] = []
        if not features:
            issues.append(
                self._issue(
                    issue_id=self._issue_id("feature_output_empty", company_id),
                    check_name="Feature output presence",
                    check_code="feature_output_presence",
                    target_type="feature_output",
                    target_id=company_id,
                    message="No feature artifacts were emitted, so feature output validation recorded no structural output checks.",
                    severity=QualitySeverity.LOW,
                    blocking=False,
                    field_paths=["features"],
                    related_artifact_ids=[company_id],
                    workflow_name="feature_mapping",
                    step_name="feature_output",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        else:
            feature_eval = evaluate_feature_lineage_completeness(
                evaluation_report_id=self._evaluation_id("feature_output_lineage", company_id),
                target_type="feature",
                target_id=company_id,
                features=features,
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
            violations.extend(
                self._violations_from_failure_cases(
                    failure_cases=feature_eval.failure_cases,
                    workflow_name="feature_mapping",
                    step_name="feature_output",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                    default_reason=RefusalReason.STRUCTURALLY_INVALID_OUTPUT,
                )
            )
            provenance_eval = evaluate_provenance_completeness(
                evaluation_report_id=self._evaluation_id("feature_output_provenance", company_id),
                target_type="feature_output",
                target_id=company_id,
                artifacts=[
                    nested
                    for feature in features
                    for nested in [feature.feature_definition, feature.feature_value, feature]
                ],
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
            violations.extend(
                self._violations_from_failure_cases(
                    failure_cases=provenance_eval.failure_cases,
                    workflow_name="feature_mapping",
                    step_name="feature_output",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )

        checks = self._build_checks(
            gate_id=gate_id,
            target_type="feature_output",
            target_id=company_id,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            now=now,
            specs=[
                ("feature_output_presence", "Feature output presence", issues, []),
                (
                    "feature_output_lineage",
                    "Feature output lineage",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is not RefusalReason.MISSING_PROVENANCE
                    ],
                ),
                (
                    "feature_output_provenance",
                    "Feature output provenance",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is RefusalReason.MISSING_PROVENANCE
                    ],
                ),
            ],
            quarantine_on_blocking=True,
        )

        return self._finalize_gate_result(
            gate_id=gate_id,
            gate_name="feature_output",
            workflow_name="feature_mapping",
            step_name="feature_output",
            target_type="feature_output",
            target_id=company_id,
            issues=issues,
            violations=violations,
            checks=checks,
            completeness_report=report,
            output_root=output_root,
            source_reference_ids=source_reference_ids,
            workflow_run_id=workflow_run_id,
            notes=notes,
            quarantine_on_blocking=True,
            raise_on_failure=raise_on_failure,
            now=now,
        )

    def validate_signal_generation(
        self,
        *,
        company_id: str,
        features: list[Feature],
        signals: list[Signal],
        signal_scores: list[SignalScore],
        workflow_run_id: str,
        requested_by: str,
        output_root: Path | None = None,
        raise_on_failure: bool = True,
    ) -> ValidationGateResult:
        """Validate emitted signals before persistence and downstream use."""

        gate_id = self._gate_id("signal_generation_output", company_id)
        now = self.clock.now()
        source_reference_ids = self._source_reference_ids([*features, *signals, *signal_scores])
        notes = [f"requested_by={requested_by}"]
        report = self._completeness_report(
            report_id=self._report_id("signal_generation_output", company_id),
            target_type="signal_output",
            target_id=company_id,
            fields=[
                CompletenessField("signals", bool(signals)),
                CompletenessField("signal_scores", bool(signal_scores) if signals else True),
            ],
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            decision=QualityDecision.PASS if signals else QualityDecision.WARN,
            notes=[],
            now=now,
        )
        issues: list[DataQualityIssue] = []
        violations: list[ContractViolation] = []
        if not signals:
            issues.append(
                self._issue(
                    issue_id=self._issue_id("signal_output_empty", company_id),
                    check_name="Signal output presence",
                    check_code="signal_output_presence",
                    target_type="signal_output",
                    target_id=company_id,
                    message="No signal artifacts were emitted, so signal-output validation recorded no structural signal checks.",
                    severity=QualitySeverity.LOW,
                    blocking=False,
                    field_paths=["signals"],
                    related_artifact_ids=[company_id],
                    workflow_name="signal_generation",
                    step_name="signal_output",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        else:
            signal_eval = evaluate_signal_generation_validity(
                evaluation_report_id=self._evaluation_id("signal_output_validity", company_id),
                target_type="signal",
                target_id=company_id,
                signals=signals,
                features_by_id={feature.feature_id: feature for feature in features},
                known_signal_ids=set(),
                snapshots_by_id={},
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
            violations.extend(
                self._violations_from_failure_cases(
                    failure_cases=signal_eval.failure_cases,
                    workflow_name="signal_generation",
                    step_name="signal_output",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
            provenance_eval = evaluate_provenance_completeness(
                evaluation_report_id=self._evaluation_id("signal_output_provenance", company_id),
                target_type="signal_output",
                target_id=company_id,
                artifacts=[*signals, *signal_scores],
                clock=self.clock,
                workflow_run_id=workflow_run_id,
            )
            violations.extend(
                self._violations_from_failure_cases(
                    failure_cases=provenance_eval.failure_cases,
                    workflow_name="signal_generation",
                    step_name="signal_output",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )

        checks = self._build_checks(
            gate_id=gate_id,
            target_type="signal_output",
            target_id=company_id,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            now=now,
            specs=[
                ("signal_output_presence", "Signal output presence", issues, []),
                (
                    "signal_output_validity",
                    "Signal output validity",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is not RefusalReason.MISSING_PROVENANCE
                    ],
                ),
                (
                    "signal_output_provenance",
                    "Signal output provenance",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is RefusalReason.MISSING_PROVENANCE
                    ],
                ),
            ],
            quarantine_on_blocking=True,
        )
        return self._finalize_gate_result(
            gate_id=gate_id,
            gate_name="signal_generation_output",
            workflow_name="signal_generation",
            step_name="signal_output",
            target_type="signal_output",
            target_id=company_id,
            issues=issues,
            violations=violations,
            checks=checks,
            completeness_report=report,
            output_root=output_root,
            source_reference_ids=source_reference_ids,
            workflow_run_id=workflow_run_id,
            notes=notes,
            quarantine_on_blocking=True,
            raise_on_failure=raise_on_failure,
            now=now,
        )

    def validate_portfolio_proposal(
        self,
        *,
        company_id: str,
        signals_by_id: dict[str, Signal],
        position_ideas: list[PositionIdea],
        portfolio_proposal: PortfolioProposal,
        workflow_run_id: str,
        requested_by: str,
        output_root: Path | None = None,
        raise_on_failure: bool = True,
    ) -> ValidationGateResult:
        """Validate loaded signals plus the generated portfolio proposal before persistence."""

        gate_id = self._gate_id("portfolio_proposal", portfolio_proposal.portfolio_proposal_id)
        now = self.clock.now()
        source_reference_ids = self._source_reference_ids([*signals_by_id.values(), *position_ideas, portfolio_proposal])
        notes = [f"requested_by={requested_by}"]
        report = self._completeness_report(
            report_id=self._report_id("portfolio_proposal", portfolio_proposal.portfolio_proposal_id),
            target_type="portfolio_proposal",
            target_id=portfolio_proposal.portfolio_proposal_id,
            fields=[
                CompletenessField("signals", bool(signals_by_id)),
                CompletenessField("position_ideas", True),
                CompletenessField("portfolio_proposal.provenance.processing_time", portfolio_proposal.provenance.processing_time is not None),
            ],
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            decision=QualityDecision.PASS if signals_by_id else QualityDecision.WARN,
            notes=[],
            now=now,
        )
        issues: list[DataQualityIssue] = []
        violations: list[ContractViolation] = []

        for signal in signals_by_id.values():
            missing = provenance_failures(signal.provenance)
            if missing:
                violations.append(
                    self._violation(
                        violation_id=self._violation_id("portfolio_signal_provenance_missing", signal.signal_id),
                        contract_name="portfolio_input_signal_requires_minimum_provenance",
                        target_type="signal",
                        target_id=signal.signal_id,
                        refusal_reason=RefusalReason.MISSING_PROVENANCE,
                        message="Portfolio input signal is missing minimum provenance.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=missing,
                        related_artifact_ids=[signal.signal_id],
                        workflow_name="portfolio_workflow",
                        step_name="portfolio_inputs",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )
            if not signal.feature_ids or set(signal.lineage.feature_ids) != set(signal.feature_ids):
                violations.append(
                    self._violation(
                        violation_id=self._violation_id("portfolio_signal_lineage_broken", signal.signal_id),
                        contract_name="portfolio_input_signal_requires_coherent_lineage",
                        target_type="signal",
                        target_id=signal.signal_id,
                        refusal_reason=RefusalReason.BROKEN_SIGNAL_LINEAGE,
                        message="Portfolio input signal has broken or incomplete lineage.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=["feature_ids", "lineage.feature_ids", "lineage.supporting_evidence_link_ids"],
                        related_artifact_ids=[signal.signal_id, signal.lineage.signal_lineage_id],
                        workflow_name="portfolio_workflow",
                        step_name="portfolio_inputs",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )
            invalid_component_scores = [
                score.signal_score_id
                for score in signal.component_scores
                if not score.source_feature_ids or not set(score.source_feature_ids).issubset(set(signal.feature_ids))
            ]
            if invalid_component_scores:
                violations.append(
                    self._violation(
                        violation_id=self._violation_id("portfolio_signal_component_lineage_broken", signal.signal_id),
                        contract_name="portfolio_input_signal_component_scores_require_feature_links",
                        target_type="signal",
                        target_id=signal.signal_id,
                        refusal_reason=RefusalReason.BROKEN_SIGNAL_LINEAGE,
                        message="Portfolio input signal has component scores without valid feature lineage.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=["component_scores.source_feature_ids"],
                        related_artifact_ids=[signal.signal_id, *invalid_component_scores],
                        workflow_name="portfolio_workflow",
                        step_name="portfolio_inputs",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )

        for idea in position_ideas:
            if idea.signal_id not in signals_by_id:
                violations.append(
                    self._violation(
                        violation_id=self._violation_id("position_idea_signal_missing", idea.position_idea_id),
                        contract_name="position_idea_requires_loaded_signal",
                        target_type="position_idea",
                        target_id=idea.position_idea_id,
                        refusal_reason=RefusalReason.MISSING_REQUIRED_ARTIFACT,
                        message="Position idea references a signal that is not available in the portfolio input slice.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=["signal_id"],
                        related_artifact_ids=[idea.position_idea_id, idea.signal_id],
                        workflow_name="portfolio_workflow",
                        step_name="portfolio_output",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )
            missing = provenance_failures(idea.provenance)
            if missing:
                violations.append(
                    self._violation(
                        violation_id=self._violation_id("position_idea_provenance_missing", idea.position_idea_id),
                        contract_name="position_idea_requires_minimum_provenance",
                        target_type="position_idea",
                        target_id=idea.position_idea_id,
                        refusal_reason=RefusalReason.MISSING_PROVENANCE,
                        message="Position idea is missing minimum provenance.",
                        severity=QualitySeverity.HIGH,
                        blocking=True,
                        offending_field_paths=missing,
                        related_artifact_ids=[idea.position_idea_id],
                        workflow_name="portfolio_workflow",
                        step_name="portfolio_output",
                        workflow_run_id=workflow_run_id,
                        source_reference_ids=source_reference_ids,
                        now=now,
                    )
                )

        proposal_missing = provenance_failures(portfolio_proposal.provenance)
        if proposal_missing:
            violations.append(
                self._violation(
                    violation_id=self._violation_id("portfolio_proposal_provenance_missing", portfolio_proposal.portfolio_proposal_id),
                    contract_name="portfolio_proposal_requires_minimum_provenance",
                    target_type="portfolio_proposal",
                    target_id=portfolio_proposal.portfolio_proposal_id,
                    refusal_reason=RefusalReason.MISSING_PROVENANCE,
                    message="Portfolio proposal is missing minimum provenance.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=proposal_missing,
                    related_artifact_ids=[portfolio_proposal.portfolio_proposal_id],
                    workflow_name="portfolio_workflow",
                    step_name="portfolio_output",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )

        checks = self._build_checks(
            gate_id=gate_id,
            target_type="portfolio_proposal",
            target_id=portfolio_proposal.portfolio_proposal_id,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            now=now,
            specs=[
                (
                    "portfolio_input_signal_contracts",
                    "Portfolio input signal contracts",
                    issues,
                    [
                        violation
                        for violation in violations
                        if violation.target_type == "signal"
                    ],
                ),
                (
                    "portfolio_output_position_contracts",
                    "Portfolio output position contracts",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.target_type == "position_idea"
                    ],
                ),
                (
                    "portfolio_output_proposal_contracts",
                    "Portfolio output proposal contracts",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.target_type == "portfolio_proposal"
                    ],
                ),
            ],
            quarantine_on_blocking=False,
        )

        return self._finalize_gate_result(
            gate_id=gate_id,
            gate_name="portfolio_proposal",
            workflow_name="portfolio_workflow",
            step_name="portfolio_output",
            target_type="portfolio_proposal",
            target_id=portfolio_proposal.portfolio_proposal_id,
            issues=issues,
            violations=violations,
            checks=checks,
            completeness_report=report,
            output_root=output_root,
            source_reference_ids=source_reference_ids,
            workflow_run_id=workflow_run_id,
            notes=notes,
            quarantine_on_blocking=False,
            raise_on_failure=raise_on_failure,
            now=now,
        )

    def validate_paper_trade_request(
        self,
        *,
        portfolio_proposal: PortfolioProposal,
        proposed_trades: Sequence[_ProvenancedArtifact] | None,
        workflow_run_id: str,
        requested_by: str,
        output_root: Path | None = None,
        raise_on_failure: bool = False,
    ) -> ValidationGateResult:
        """Validate paper-trade admission conditions and generated trade candidates."""

        target_id = portfolio_proposal.portfolio_proposal_id
        gate_name = "paper_trade_request" if proposed_trades is None else "paper_trade_output"
        step_name = "paper_trade_request" if proposed_trades is None else "paper_trade_output"
        gate_id = self._gate_id(gate_name, target_id)
        now = self.clock.now()
        source_reference_ids = self._source_reference_ids([portfolio_proposal, *([] if proposed_trades is None else proposed_trades)])
        notes = [f"requested_by={requested_by}"]
        completeness_fields = [
            CompletenessField(
                "portfolio_proposal.status_approved",
                portfolio_proposal.status is PortfolioProposalStatus.APPROVED,
            ),
            CompletenessField(
                "portfolio_proposal.blocking_issues_clear",
                not portfolio_proposal.blocking_issues and not any(
                    check.blocking for check in portfolio_proposal.risk_checks
                ),
            ),
        ]
        if proposed_trades is not None:
            completeness_fields.append(
                CompletenessField("proposed_trades", bool(proposed_trades))
            )
        report = self._completeness_report(
            report_id=self._report_id(gate_name, target_id),
            target_type="portfolio_proposal",
            target_id=target_id,
            fields=completeness_fields,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            decision=QualityDecision.PASS if all(field.present for field in completeness_fields) else QualityDecision.WARN,
            notes=[],
            now=now,
        )
        issues: list[DataQualityIssue] = []
        violations: list[ContractViolation] = []

        if portfolio_proposal.status.value != "approved":
            violations.append(
                self._violation(
                    violation_id=self._violation_id("paper_trade_proposal_not_approved", target_id),
                    contract_name="paper_trade_candidates_require_approved_portfolio_proposal",
                    target_type="portfolio_proposal",
                    target_id=target_id,
                    refusal_reason=RefusalReason.INVALID_REVIEW_STATE,
                    message="Portfolio proposal is not approved, so paper-trade candidates cannot be created.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=["status"],
                    related_artifact_ids=[target_id],
                    workflow_name="paper_trade_creation",
                    step_name=step_name,
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        if portfolio_proposal.blocking_issues or any(check.blocking for check in portfolio_proposal.risk_checks):
            violations.append(
                self._violation(
                    violation_id=self._violation_id("paper_trade_blocking_risk_checks_present", target_id),
                    contract_name="paper_trade_candidates_require_no_blocking_risk_checks",
                    target_type="portfolio_proposal",
                    target_id=target_id,
                    refusal_reason=RefusalReason.INVALID_REVIEW_STATE,
                    message="Portfolio proposal still has blocking risk checks or blocking issues.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=["blocking_issues", "risk_checks"],
                    related_artifact_ids=[target_id, *[check.risk_check_id for check in portfolio_proposal.risk_checks if check.blocking]],
                    workflow_name="paper_trade_creation",
                    step_name=step_name,
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        if proposed_trades is not None:
            known_position_ids = {idea.position_idea_id for idea in portfolio_proposal.position_ideas}
            for trade in proposed_trades:
                trade_id = self._artifact_id(trade)
                if getattr(trade, "portfolio_proposal_id", None) != target_id:
                    violations.append(
                        self._violation(
                            violation_id=self._violation_id("paper_trade_proposal_link_broken", trade_id),
                            contract_name="paper_trade_requires_matching_portfolio_proposal_link",
                            target_type="paper_trade",
                            target_id=trade_id,
                            refusal_reason=RefusalReason.STRUCTURALLY_INVALID_OUTPUT,
                            message="Generated paper trade does not point back to the supplied portfolio proposal.",
                            severity=QualitySeverity.HIGH,
                            blocking=True,
                            offending_field_paths=["portfolio_proposal_id"],
                            related_artifact_ids=[trade_id, target_id],
                            workflow_name="paper_trade_creation",
                            step_name=step_name,
                            workflow_run_id=workflow_run_id,
                            source_reference_ids=source_reference_ids,
                            now=now,
                        )
                    )
                if getattr(trade, "position_idea_id", None) not in known_position_ids:
                    violations.append(
                        self._violation(
                            violation_id=self._violation_id("paper_trade_position_link_missing", trade_id),
                            contract_name="paper_trade_requires_known_position_idea_link",
                            target_type="paper_trade",
                            target_id=trade_id,
                            refusal_reason=RefusalReason.MISSING_REQUIRED_ARTIFACT,
                            message="Generated paper trade references a position idea that is not in the proposal.",
                            severity=QualitySeverity.HIGH,
                            blocking=True,
                            offending_field_paths=["position_idea_id"],
                            related_artifact_ids=[trade_id, getattr(trade, "position_idea_id", "unknown")],
                            workflow_name="paper_trade_creation",
                            step_name=step_name,
                            workflow_run_id=workflow_run_id,
                            source_reference_ids=source_reference_ids,
                            now=now,
                        )
                    )
                missing = provenance_failures(trade.provenance)
                if missing:
                    violations.append(
                        self._violation(
                            violation_id=self._violation_id("paper_trade_provenance_missing", trade_id),
                            contract_name="paper_trade_requires_minimum_provenance",
                            target_type="paper_trade",
                            target_id=trade_id,
                            refusal_reason=RefusalReason.MISSING_PROVENANCE,
                            message="Generated paper trade is missing minimum provenance.",
                            severity=QualitySeverity.HIGH,
                            blocking=True,
                            offending_field_paths=missing,
                            related_artifact_ids=[trade_id],
                            workflow_name="paper_trade_creation",
                            step_name=step_name,
                            workflow_run_id=workflow_run_id,
                            source_reference_ids=source_reference_ids,
                            now=now,
                        )
                    )

        quarantine_on_blocking = proposed_trades is not None
        checks = self._build_checks(
            gate_id=gate_id,
            target_type="portfolio_proposal",
            target_id=target_id,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            now=now,
            specs=[
                (
                    "paper_trade_request_contracts",
                    "Paper-trade request contracts",
                    issues,
                    [violation for violation in violations if violation.target_type == "portfolio_proposal"],
                ),
                (
                    "paper_trade_output_contracts",
                    "Paper-trade output contracts",
                    [],
                    [violation for violation in violations if violation.target_type == "paper_trade"],
                ),
            ],
            quarantine_on_blocking=quarantine_on_blocking,
        )
        return self._finalize_gate_result(
            gate_id=gate_id,
            gate_name=gate_name,
            workflow_name="paper_trade_creation",
            step_name=step_name,
            target_type="portfolio_proposal",
            target_id=target_id,
            issues=issues,
            violations=violations,
            checks=checks,
            completeness_report=report,
            output_root=output_root,
            source_reference_ids=source_reference_ids,
            workflow_run_id=workflow_run_id,
            notes=notes,
            quarantine_on_blocking=quarantine_on_blocking,
            raise_on_failure=raise_on_failure,
            now=now,
        )

    def validate_experiment_metadata(
        self,
        *,
        experiment_name: str,
        created_by: str,
        experiment_config: ExperimentConfig,
        dataset_references: list[DatasetReference],
        workflow_run_id: str,
        requested_by: str,
        output_root: Path | None = None,
        raise_on_failure: bool = True,
    ) -> ValidationGateResult:
        """Validate minimum experiment reproducibility metadata before experiment creation."""

        gate_id = self._gate_id("experiment_metadata", experiment_name)
        now = self.clock.now()
        dataset_reference_ids = [
            dataset_reference.dataset_reference_id for dataset_reference in dataset_references
        ]
        source_reference_ids = sorted(
            {
                *experiment_config.provenance.source_reference_ids,
                *[
                    source_reference_id
                    for dataset_reference in dataset_references
                    for source_reference_id in dataset_reference.provenance.source_reference_ids
                ],
            }
        )
        notes = [f"requested_by={requested_by}"]
        report = self._completeness_report(
            report_id=self._report_id("experiment_metadata", experiment_name),
            target_type="experiment",
            target_id=experiment_name,
            fields=[
                CompletenessField("dataset_reference_ids", bool(dataset_reference_ids)),
                CompletenessField(
                    "experiment_config.parameters",
                    bool(experiment_config.parameters),
                ),
                CompletenessField("created_by", bool(created_by)),
            ],
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            decision=QualityDecision.PASS if dataset_reference_ids else QualityDecision.WARN,
            notes=[],
            now=now,
        )
        issues: list[DataQualityIssue] = []
        violations: list[ContractViolation] = []
        if not dataset_reference_ids:
            violations.append(
                self._violation(
                    violation_id=self._violation_id("experiment_dataset_references_missing", experiment_name),
                    contract_name="experiment_requires_dataset_references",
                    target_type="experiment",
                    target_id=experiment_name,
                    refusal_reason=RefusalReason.INCOMPLETE_EXPERIMENT_METADATA,
                    message="Experiment creation requires at least one dataset reference.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=["dataset_reference_ids"],
                    related_artifact_ids=[experiment_name],
                    workflow_name="experiment_registry",
                    step_name="begin_experiment",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        config_missing = provenance_failures(experiment_config.provenance)
        if config_missing:
            violations.append(
                self._violation(
                    violation_id=self._violation_id("experiment_config_provenance_missing", experiment_config.experiment_config_id),
                    contract_name="experiment_config_requires_minimum_provenance",
                    target_type="experiment_config",
                    target_id=experiment_config.experiment_config_id,
                    refusal_reason=RefusalReason.MISSING_PROVENANCE,
                    message="Experiment config is missing minimum provenance.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=config_missing,
                    related_artifact_ids=[experiment_config.experiment_config_id],
                    workflow_name="experiment_registry",
                    step_name="begin_experiment",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        for dataset_reference in dataset_references:
            metadata_missing: list[str] = []
            if not dataset_reference.data_snapshot_id:
                metadata_missing.append("data_snapshot_id")
            if not dataset_reference.storage_uri:
                metadata_missing.append("storage_uri")
            if not dataset_reference.dataset_manifest_id:
                metadata_missing.append("dataset_manifest_id")
            provenance_missing = provenance_failures(dataset_reference.provenance)
            metadata_missing.extend(provenance_missing)
            if not metadata_missing:
                continue
            violations.append(
                self._violation(
                    violation_id=self._violation_id(
                        "dataset_reference_metadata_incomplete",
                        dataset_reference.dataset_reference_id,
                    ),
                    contract_name="dataset_reference_requires_replayable_metadata",
                    target_type="dataset_reference",
                    target_id=dataset_reference.dataset_reference_id,
                    refusal_reason=RefusalReason.INCOMPLETE_EXPERIMENT_METADATA,
                    message="Dataset reference is missing replayable metadata required for experiment registration.",
                    severity=QualitySeverity.HIGH,
                    blocking=True,
                    offending_field_paths=metadata_missing,
                    related_artifact_ids=[dataset_reference.dataset_reference_id],
                    workflow_name="experiment_registry",
                    step_name="begin_experiment",
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        checks = self._build_checks(
            gate_id=gate_id,
            target_type="experiment",
            target_id=experiment_name,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
            now=now,
            specs=[
                (
                    "experiment_metadata_completeness",
                    "Experiment metadata completeness",
                    issues,
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is RefusalReason.INCOMPLETE_EXPERIMENT_METADATA
                    ],
                ),
                (
                    "experiment_metadata_provenance",
                    "Experiment metadata provenance",
                    [],
                    [
                        violation
                        for violation in violations
                        if violation.refusal_reason is RefusalReason.MISSING_PROVENANCE
                    ],
                ),
            ],
            quarantine_on_blocking=False,
        )
        return self._finalize_gate_result(
            gate_id=gate_id,
            gate_name="experiment_metadata",
            workflow_name="experiment_registry",
            step_name="begin_experiment",
            target_type="experiment",
            target_id=experiment_name,
            issues=issues,
            violations=violations,
            checks=checks,
            completeness_report=report,
            output_root=output_root,
            source_reference_ids=source_reference_ids,
            workflow_run_id=workflow_run_id,
            notes=notes,
            quarantine_on_blocking=False,
            raise_on_failure=raise_on_failure,
            now=now,
        )

    def _finalize_gate_result(
        self,
        *,
        gate_id: str,
        gate_name: str,
        workflow_name: str,
        step_name: str,
        target_type: str,
        target_id: str,
        issues: list[DataQualityIssue],
        violations: list[ContractViolation],
        checks: list[DataQualityCheck],
        completeness_report: InputCompletenessReport | None,
        output_root: Path | None,
        source_reference_ids: list[str],
        workflow_run_id: str,
        notes: list[str],
        quarantine_on_blocking: bool,
        raise_on_failure: bool,
        now: datetime,
    ) -> ValidationGateResult:
        """Persist one full gate result and optionally raise on refusal."""

        blocking_violation_count = sum(1 for violation in violations if violation.blocking)
        decision = quality_decision_for_findings(
            issues=issues,
            blocking_violation_count=blocking_violation_count,
            quarantine_on_blocking=quarantine_on_blocking,
        )
        refusal_reason = next((violation.refusal_reason for violation in violations if violation.blocking), None)
        gate = ValidationGate(
            validation_gate_id=gate_id,
            gate_name=gate_name,
            workflow_name=workflow_name,
            step_name=step_name,
            target_type=target_type,
            target_id=target_id,
            decision=decision,
            refusal_reason=refusal_reason,
            quarantined=decision is QualityDecision.QUARANTINE,
            data_quality_check_ids=[check.data_quality_check_id for check in checks],
            data_quality_issue_ids=[issue.data_quality_issue_id for issue in issues],
            contract_violation_ids=[violation.contract_violation_id for violation in violations],
            input_completeness_report_id=(
                completeness_report.input_completeness_report_id
                if completeness_report is not None
                else None
            ),
            notes=notes,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="data_quality_validation_gate",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=[
                    target_id,
                    *[issue.data_quality_issue_id for issue in issues],
                    *[violation.contract_violation_id for violation in violations],
                ],
                workflow_run_id=workflow_run_id,
            ),
            created_at=now,
            updated_at=now,
        )
        store = LocalDataQualityArtifactStore(
            root=output_root or (get_settings().resolved_artifact_root / "data_quality"),
            clock=self.clock,
        )
        storage_locations: list[ArtifactStorageLocation] = []
        if completeness_report is not None:
            storage_locations.append(
                store.persist_model(
                    artifact_id=completeness_report.input_completeness_report_id,
                    category="input_completeness_reports",
                    model=completeness_report,
                    source_reference_ids=source_reference_ids,
                )
            )
        for issue in issues:
            storage_locations.append(
                store.persist_model(
                    artifact_id=issue.data_quality_issue_id,
                    category="data_quality_issues",
                    model=issue,
                    source_reference_ids=source_reference_ids,
                )
            )
        for violation in violations:
            storage_locations.append(
                store.persist_model(
                    artifact_id=violation.contract_violation_id,
                    category="contract_violations",
                    model=violation,
                    source_reference_ids=source_reference_ids,
                )
            )
        for check in checks:
            storage_locations.append(
                store.persist_model(
                    artifact_id=check.data_quality_check_id,
                    category="data_quality_checks",
                    model=check,
                    source_reference_ids=source_reference_ids,
                )
            )
        storage_locations.append(
            store.persist_model(
                artifact_id=gate.validation_gate_id,
                category="validation_gates",
                model=gate,
                source_reference_ids=source_reference_ids,
            )
        )
        result = ValidationGateResult(
            validation_gate=gate,
            data_quality_checks=checks,
            data_quality_issues=issues,
            contract_violations=violations,
            input_completeness_report=completeness_report,
            storage_locations=storage_locations,
            notes=notes,
        )
        if decision in {QualityDecision.REFUSE, QualityDecision.QUARANTINE} and raise_on_failure:
            raise DataQualityRefusalError(result)
        return result

    def _build_checks(
        self,
        *,
        gate_id: str,
        target_type: str,
        target_id: str,
        workflow_run_id: str,
        source_reference_ids: list[str],
        now: datetime,
        specs: list[tuple[str, str, list[DataQualityIssue], list[ContractViolation]]],
        quarantine_on_blocking: bool,
    ) -> list[DataQualityCheck]:
        """Build gate child checks from grouped issue and violation lists."""

        checks: list[DataQualityCheck] = []
        for check_code, check_name, issues, violations in specs:
            levels = [issue.severity for issue in issues] + [violation.severity for violation in violations]
            severity = highest_quality_severity(levels) if levels else QualitySeverity.LOW
            blocking = any(violation.blocking for violation in violations)
            decision = (
                QualityDecision.QUARANTINE
                if blocking and quarantine_on_blocking
                else QualityDecision.REFUSE
                if blocking
                else QualityDecision.WARN
                if issues or violations
                else QualityDecision.PASS
            )
            checks.append(
                DataQualityCheck(
                    data_quality_check_id=self._check_id(check_code, target_id),
                    validation_gate_id=gate_id,
                    target_type=target_type,
                    target_id=target_id,
                    check_name=check_name,
                    check_code=check_code,
                    decision=decision,
                    severity=severity,
                    data_quality_issue_ids=[issue.data_quality_issue_id for issue in issues],
                    contract_violation_ids=[violation.contract_violation_id for violation in violations],
                    notes=[],
                    provenance=build_provenance(
                        clock=self.clock,
                        transformation_name="data_quality_check",
                        source_reference_ids=source_reference_ids,
                        upstream_artifact_ids=[
                            target_id,
                            *[issue.data_quality_issue_id for issue in issues],
                            *[violation.contract_violation_id for violation in violations],
                        ],
                        workflow_run_id=workflow_run_id,
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
        return checks

    def _violations_from_failure_cases(
        self,
        *,
        failure_cases: list,
        workflow_name: str,
        step_name: str,
        workflow_run_id: str,
        source_reference_ids: list[str],
        now: datetime,
        default_reason: RefusalReason | None = None,
    ) -> list[ContractViolation]:
        """Convert evaluation failure cases into contract violations."""

        violations: list[ContractViolation] = []
        for failure_case in failure_cases:
            reason = default_reason or refusal_reason_from_failure_case(failure_case)
            violations.append(
                self._violation(
                    violation_id=self._violation_id(failure_case.failure_kind.value, failure_case.target_id),
                    contract_name=f"evaluation_{failure_case.failure_kind.value}",
                    target_type=failure_case.target_type,
                    target_id=failure_case.target_id,
                    refusal_reason=reason,
                    message=failure_case.message,
                    severity=quality_severity_from_severity(failure_case.severity),
                    blocking=failure_case.blocking,
                    offending_field_paths=[],
                    related_artifact_ids=failure_case.related_artifact_ids,
                    workflow_name=workflow_name,
                    step_name=step_name,
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                    now=now,
                )
            )
        return violations

    def _completeness_report(
        self,
        *,
        report_id: str,
        target_type: str,
        target_id: str,
        fields: list[CompletenessField],
        workflow_run_id: str,
        source_reference_ids: list[str],
        decision: QualityDecision,
        notes: list[str],
        now: datetime,
    ) -> InputCompletenessReport:
        required_fields, present_fields, missing_fields, ratio = completeness_lists(fields)
        return InputCompletenessReport(
            input_completeness_report_id=report_id,
            target_type=target_type,
            target_id=target_id,
            required_fields=required_fields,
            present_fields=present_fields,
            missing_fields=missing_fields,
            completeness_ratio=ratio,
            decision=decision,
            notes=notes,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="data_quality_input_completeness",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=[target_id],
                workflow_run_id=workflow_run_id,
            ),
            created_at=now,
            updated_at=now,
        )

    def _issue(
        self,
        *,
        issue_id: str,
        check_name: str,
        check_code: str,
        target_type: str,
        target_id: str,
        message: str,
        severity: QualitySeverity,
        blocking: bool,
        field_paths: list[str],
        related_artifact_ids: list[str],
        workflow_name: str,
        step_name: str,
        workflow_run_id: str,
        source_reference_ids: list[str],
        now: datetime,
    ) -> DataQualityIssue:
        return DataQualityIssue(
            data_quality_issue_id=issue_id,
            check_name=check_name,
            check_code=check_code,
            target_type=target_type,
            target_id=target_id,
            workflow_name=workflow_name,
            step_name=step_name,
            field_paths=field_paths,
            severity=severity,
            blocking=blocking,
            message=message,
            related_artifact_ids=related_artifact_ids,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="data_quality_issue",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=[target_id, *related_artifact_ids],
                workflow_run_id=workflow_run_id,
            ),
            created_at=now,
            updated_at=now,
        )

    def _violation(
        self,
        *,
        violation_id: str,
        contract_name: str,
        target_type: str,
        target_id: str,
        refusal_reason: RefusalReason,
        message: str,
        severity: QualitySeverity,
        blocking: bool,
        offending_field_paths: list[str],
        related_artifact_ids: list[str],
        workflow_name: str,
        step_name: str,
        workflow_run_id: str,
        source_reference_ids: list[str],
        now: datetime,
    ) -> ContractViolation:
        return ContractViolation(
            contract_violation_id=violation_id,
            contract_name=contract_name,
            target_type=target_type,
            target_id=target_id,
            workflow_name=workflow_name,
            step_name=step_name,
            offending_field_paths=offending_field_paths,
            severity=severity,
            blocking=blocking,
            refusal_reason=refusal_reason,
            message=message,
            related_artifact_ids=related_artifact_ids,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="data_quality_contract_violation",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=[target_id, *related_artifact_ids],
                workflow_run_id=workflow_run_id,
            ),
            created_at=now,
            updated_at=now,
        )

    def _source_reference_ids(self, artifacts: Sequence[object]) -> list[str]:
        """Collect stable source-reference IDs from a heterogeneous artifact list."""

        source_reference_ids: set[str] = set()
        for artifact in artifacts:
            provenance = getattr(artifact, "provenance", None)
            if provenance is not None:
                source_reference_ids.update(getattr(provenance, "source_reference_ids", []))
            direct_source_reference_id = getattr(artifact, "source_reference_id", None)
            if isinstance(direct_source_reference_id, str):
                source_reference_ids.add(direct_source_reference_id)
        return sorted(source_reference_ids)

    def _artifact_id(self, model: object) -> str:
        """Resolve the canonical identifier field from a strict model-like object."""

        for field_name in getattr(type(model), "model_fields", {}):
            if field_name.endswith("_id"):
                value = getattr(model, field_name, None)
                if isinstance(value, str):
                    return value
        return make_prefixed_id("artifact")

    def _gate_id(self, gate_name: str, target_id: str) -> str:
        return make_canonical_id("vgate", gate_name, target_id)

    def _report_id(self, report_name: str, target_id: str) -> str:
        return make_canonical_id("qreport", report_name, target_id)

    def _issue_id(self, issue_name: str, target_id: str) -> str:
        return make_canonical_id("qissue", issue_name, target_id)

    def _violation_id(self, violation_name: str, target_id: str) -> str:
        return make_canonical_id("cviol", violation_name, target_id)

    def _check_id(self, check_name: str, target_id: str) -> str:
        return make_canonical_id("qcheck", check_name, target_id)

    def _evaluation_id(self, evaluation_name: str, target_id: str) -> str:
        return make_canonical_id("eval", evaluation_name, target_id)
