from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from libraries.core import build_provenance
from libraries.schemas import (
    RetryPolicy,
    RunbookEntry,
    RunFailureAction,
    WorkflowDefinition,
    WorkflowStepDefinition,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id

DAILY_WORKFLOW_NAME = "daily_workflow"
DEFAULT_FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ingestion"


@dataclass(frozen=True)
class DailyStepSpec:
    """Code-owned definition and runbook metadata for one daily step."""

    step_name: str
    sequence_index: int
    dependency_step_names: tuple[str, ...]
    owning_service: str
    description: str
    retry_policy: RetryPolicy
    failure_action: RunFailureAction
    expected_outputs: tuple[str, ...]
    operator_checks: tuple[str, ...]
    failure_triage_instructions: tuple[str, ...]
    manual_review_required: bool = False
    next_manual_action: str | None = None


DAILY_STEP_SPECS: tuple[DailyStepSpec, ...] = (
    DailyStepSpec(
        step_name="fixture_refresh_and_normalization",
        sequence_index=1,
        dependency_step_names=(),
        owning_service="ingestion",
        description="Refresh fixture-backed source inputs and normalize canonical ingestion artifacts.",
        retry_policy=RetryPolicy(
            max_attempts=2,
            automatic_retry_enabled=True,
            backoff_seconds=0,
            retryable=True,
        ),
        failure_action=RunFailureAction.FAIL_WORKFLOW,
        expected_outputs=(
            "Normalized source references and company-linked document artifacts under artifacts/ingestion/.",
            "Entity-resolution and timing artifacts when available.",
        ),
        operator_checks=(
            "Confirm the expected fixtures were discovered and normalized.",
            "Check timing and entity-resolution notes for missing or ambiguous inputs.",
        ),
        failure_triage_instructions=(
            "Verify the fixture root exists and contains readable raw fixture files.",
            "Inspect ingestion run summaries and timing anomalies before rerunning.",
        ),
    ),
    DailyStepSpec(
        step_name="evidence_extraction",
        sequence_index=2,
        dependency_step_names=("fixture_refresh_and_normalization",),
        owning_service="parsing",
        description="Build parsed document text, segments, evidence spans, and derived extraction artifacts.",
        retry_policy=RetryPolicy(
            max_attempts=2,
            automatic_retry_enabled=True,
            backoff_seconds=0,
            retryable=True,
        ),
        failure_action=RunFailureAction.FAIL_WORKFLOW,
        expected_outputs=(
            "Parsing artifacts under artifacts/parsing/, including evidence spans and extracted claims.",
            "Document-level timing and entity-link refreshes when applicable.",
        ),
        operator_checks=(
            "Confirm each normalized document produced parsed text and evidence spans.",
            "Check extraction notes for empty bundles, timing anomalies, or unresolved entity links.",
        ),
        failure_triage_instructions=(
            "Verify normalized document, source reference, and raw payload artifacts all exist.",
            "Inspect parsing run summaries for the failing document path and rerun after fixing the source inputs.",
        ),
    ),
    DailyStepSpec(
        step_name="research_workflow",
        sequence_index=3,
        dependency_step_names=("evidence_extraction",),
        owning_service="research_orchestrator",
        description="Run the deterministic research workflow over current evidence and advisory retrieval context.",
        retry_policy=RetryPolicy(
            max_attempts=1,
            automatic_retry_enabled=False,
            backoff_seconds=0,
            retryable=False,
        ),
        failure_action=RunFailureAction.FAIL_WORKFLOW,
        expected_outputs=(
            "Evidence assessment and, when support is sufficient, hypothesis, counter-hypothesis, research brief, and memo artifacts.",
        ),
        operator_checks=(
            "Inspect whether the workflow produced a hypothesis or only an evidence assessment.",
            "Review retrieval-context notes so operators know what prior work informed the run.",
        ),
        failure_triage_instructions=(
            "Check parsing outputs and company scoping for multi-company ambiguity.",
            "Inspect the research workflow run summary and audit logs for explicit failure notes.",
        ),
        manual_review_required=True,
        next_manual_action="Review the generated research brief or evidence assessment before relying on it downstream.",
    ),
    DailyStepSpec(
        step_name="feature_signal_pipeline",
        sequence_index=4,
        dependency_step_names=("research_workflow",),
        owning_service="signal_generation",
        description="Map features, generate candidate signals, and run deterministic signal arbitration.",
        retry_policy=RetryPolicy(
            max_attempts=1,
            automatic_retry_enabled=False,
            backoff_seconds=0,
            retryable=False,
        ),
        failure_action=RunFailureAction.FAIL_WORKFLOW,
        expected_outputs=(
            "Feature, signal, and signal-arbitration artifacts under signal_generation/ and signal_arbitration/.",
        ),
        operator_checks=(
            "Confirm candidate signals have timing-safe availability metadata.",
            "Inspect arbitration notes for exclusions, conflicts, or review-required outcomes.",
        ),
        failure_triage_instructions=(
            "Check research artifacts and feature-mapping notes for missing upstream lineage.",
            "Inspect signal-generation and arbitration run summaries before rerunning.",
        ),
        manual_review_required=True,
        next_manual_action="Review candidate signals and arbitration outcomes before proposal construction is treated as trustworthy input.",
    ),
    DailyStepSpec(
        step_name="portfolio_workflow",
        sequence_index=5,
        dependency_step_names=("feature_signal_pipeline",),
        owning_service="portfolio",
        description="Construct a portfolio proposal, attach attribution, stress testing, and risk checks.",
        retry_policy=RetryPolicy(
            max_attempts=1,
            automatic_retry_enabled=False,
            backoff_seconds=0,
            retryable=False,
        ),
        failure_action=RunFailureAction.FAIL_WORKFLOW,
        expected_outputs=(
            "Portfolio proposal, position ideas, attribution artifacts, stress-test outputs, and risk checks.",
        ),
        operator_checks=(
            "Inspect proposal blocking issues, attribution summaries, and stress fragility warnings.",
            "Confirm the proposal remains explicitly review-required.",
        ),
        failure_triage_instructions=(
            "Check the latest signals and arbitration outputs for missing or withheld portfolio inputs.",
            "Inspect portfolio notes and risk warnings before rerunning construction.",
        ),
        manual_review_required=True,
        next_manual_action="Review the proposal, attribution, and stress results before any paper-trade promotion.",
    ),
    DailyStepSpec(
        step_name="review_queue_sync",
        sequence_index=6,
        dependency_step_names=("portfolio_workflow",),
        owning_service="operator_review",
        description="Refresh the operator review queue for newly produced research, signal, and portfolio artifacts.",
        retry_policy=RetryPolicy(
            max_attempts=1,
            automatic_retry_enabled=False,
            backoff_seconds=0,
            retryable=False,
        ),
        failure_action=RunFailureAction.ATTENTION_REQUIRED_STOP,
        expected_outputs=(
            "Updated review queue items under artifacts/review/queue_items/.",
        ),
        operator_checks=(
            "Confirm new reviewable artifacts appear in the queue with conservative recommendations.",
            "Check that unresolved portfolio proposals remain visible to reviewers.",
        ),
        failure_triage_instructions=(
            "Inspect review-root readability and queue-item persistence paths.",
            "Re-sync the queue after fixing storage or artifact-loading issues.",
        ),
        manual_review_required=True,
        next_manual_action="Open the review queue and inspect newly surfaced research, signal, and portfolio items.",
    ),
    DailyStepSpec(
        step_name="paper_trade_candidate_generation",
        sequence_index=7,
        dependency_step_names=("review_queue_sync",),
        owning_service="paper_execution",
        description="Attempt paper-trade candidate creation without auto-approving the parent proposal.",
        retry_policy=RetryPolicy(
            max_attempts=1,
            automatic_retry_enabled=False,
            backoff_seconds=0,
            retryable=False,
        ),
        failure_action=RunFailureAction.ATTENTION_REQUIRED_STOP,
        expected_outputs=(
            "Paper-trade candidates only when the parent proposal is explicitly approved and non-blocked.",
            "Otherwise an explicit review-required stop with zero trades.",
        ),
        operator_checks=(
            "Confirm zero trades were created when the proposal was not explicitly approved.",
            "If trades were created, confirm the parent proposal approval path is visible and auditable.",
        ),
        failure_triage_instructions=(
            "Check proposal status, blocking issues, and review decisions before rerunning.",
            "Do not bypass the review gate to create trades.",
        ),
        manual_review_required=True,
        next_manual_action="Apply explicit portfolio review before requesting paper-trade candidates again.",
    ),
    DailyStepSpec(
        step_name="operations_summary",
        sequence_index=8,
        dependency_step_names=("paper_trade_candidate_generation",),
        owning_service="monitoring",
        description="Collect health checks and recent run summaries for the current daily operating slice.",
        retry_policy=RetryPolicy(
            max_attempts=2,
            automatic_retry_enabled=True,
            backoff_seconds=0,
            retryable=True,
        ),
        failure_action=RunFailureAction.PARTIAL_CONTINUE,
        expected_outputs=(
            "Current health-check artifacts and recent run-summary views for operators.",
        ),
        operator_checks=(
            "Inspect failed or attention-required run summaries after the daily run completes.",
            "Review open monitoring alerts before considering the daily cycle healthy.",
        ),
        failure_triage_instructions=(
            "Verify monitoring storage is readable and the service registry still loads.",
            "Re-run health checks after fixing any monitoring-root or artifact-path issues.",
        ),
    ),
)


def build_workflow_definition(*, clock: Clock) -> WorkflowDefinition:
    """Build the code-owned workflow definition for the daily local run."""

    now = clock.now()
    step_definitions = [
        WorkflowStepDefinition(
            step_name=spec.step_name,
            sequence_index=spec.sequence_index,
            dependency_step_names=list(spec.dependency_step_names),
            owning_service=spec.owning_service,
            description=spec.description,
            retry_policy=spec.retry_policy,
            failure_action=spec.failure_action,
            manual_review_gate=spec.manual_review_required,
        )
        for spec in DAILY_STEP_SPECS
    ]
    return WorkflowDefinition(
        workflow_definition_id=make_canonical_id("wdef", DAILY_WORKFLOW_NAME, "day21"),
        workflow_name=DAILY_WORKFLOW_NAME,
        description=(
            "Local deterministic daily operating workflow for fixture refresh, research, signals, "
            "portfolio construction, review queue sync, paper-trade gating, and monitoring summary generation."
        ),
        step_definitions=step_definitions,
        notes=[
            "Manual local orchestration only. This is not a production scheduler.",
            "Paper-trade progression remains review-gated and should normally stop in attention_required state.",
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="daily_orchestration_workflow_definition",
            upstream_artifact_ids=[spec.step_name for spec in step_definitions],
            notes=["code_owned_definition=true"],
        ),
        created_at=now,
        updated_at=now,
    )


def build_runbook_entries(*, clock: Clock) -> list[RunbookEntry]:
    """Build persisted runbook entries from the code-owned step registry."""

    now = clock.now()
    return [
        RunbookEntry(
            runbook_entry_id=make_canonical_id("runbook", DAILY_WORKFLOW_NAME, spec.step_name),
            step_name=spec.step_name,
            purpose=spec.description,
            expected_outputs=list(spec.expected_outputs),
            operator_checks=list(spec.operator_checks),
            failure_triage_instructions=list(spec.failure_triage_instructions),
            manual_review_required=spec.manual_review_required,
            next_manual_action=spec.next_manual_action,
            provenance=build_provenance(
                clock=clock,
                transformation_name="daily_orchestration_runbook_entry",
                upstream_artifact_ids=[spec.step_name],
            ),
            created_at=now,
            updated_at=now,
        )
        for spec in DAILY_STEP_SPECS
    ]


def get_step_specs() -> tuple[DailyStepSpec, ...]:
    """Return the ordered code-owned step registry for the daily workflow."""

    return DAILY_STEP_SPECS
