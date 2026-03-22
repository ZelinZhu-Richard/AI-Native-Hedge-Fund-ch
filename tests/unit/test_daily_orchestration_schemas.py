from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    AblationView,
    DataRefreshMode,
    ManualInterventionRequirement,
    RetryPolicy,
    RunbookEntry,
    RunFailureAction,
    RunStep,
    ScheduledRunConfig,
    ScheduleMode,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStatus,
    WorkflowStepDefinition,
)
from libraries.schemas.base import ProvenanceRecord

FIXED_NOW = datetime(2026, 3, 21, 9, 0, tzinfo=UTC)
PROVENANCE = ProvenanceRecord(processing_time=FIXED_NOW)


def test_workflow_definition_and_execution_validate() -> None:
    retry_policy = RetryPolicy(
        max_attempts=2,
        automatic_retry_enabled=True,
        backoff_seconds=0,
        retryable=True,
    )
    workflow_definition = WorkflowDefinition(
        workflow_definition_id="wdef_daily",
        workflow_name="daily_workflow",
        description="Local daily workflow.",
        step_definitions=[
            WorkflowStepDefinition(
                step_name="step_one",
                sequence_index=1,
                dependency_step_names=[],
                owning_service="ingestion",
                description="First step.",
                retry_policy=retry_policy,
                failure_action=RunFailureAction.FAIL_WORKFLOW,
                manual_review_gate=False,
            ),
            WorkflowStepDefinition(
                step_name="step_two",
                sequence_index=2,
                dependency_step_names=["step_one"],
                owning_service="parsing",
                description="Second step.",
                retry_policy=RetryPolicy(
                    max_attempts=1,
                    automatic_retry_enabled=False,
                    backoff_seconds=0,
                    retryable=False,
                ),
                failure_action=RunFailureAction.ATTENTION_REQUIRED_STOP,
                manual_review_gate=True,
            ),
        ],
        notes=[],
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    scheduled_run_config = ScheduledRunConfig(
        scheduled_run_config_id="srcfg_daily",
        workflow_definition_id=workflow_definition.workflow_definition_id,
        schedule_mode=ScheduleMode.MANUAL_LOCAL,
        enabled=True,
        artifact_roots={"artifact_root": Path("/tmp/daily")},
        default_requester="unit_test",
        data_refresh_mode=DataRefreshMode.FIXTURE_REFRESH,
        company_id="co_apex",
        fixtures_root=Path("/tmp/fixtures"),
        ablation_view=AblationView.TEXT_ONLY,
        assumed_reference_prices={"APEX": 101.5},
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    run_step = RunStep(
        run_step_id="rstep_one",
        workflow_execution_id="dwflow_1",
        step_name="step_one",
        sequence_index=1,
        dependency_step_ids=[],
        owning_service="ingestion",
        status=WorkflowStatus.SUCCEEDED,
        attempt_count=1,
        retry_policy=retry_policy,
        failure_action=RunFailureAction.FAIL_WORKFLOW,
        child_workflow_ids=["ingest_1"],
        child_run_summary_ids=["runsum_ingestion"],
        produced_artifact_ids=["src_1"],
        notes=["completed"],
        manual_intervention_requirement=None,
        started_at=FIXED_NOW,
        completed_at=FIXED_NOW,
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    execution = WorkflowExecution(
        workflow_execution_id="dwflow_1",
        workflow_definition_id=workflow_definition.workflow_definition_id,
        scheduled_run_config_id=scheduled_run_config.scheduled_run_config_id,
        status=WorkflowStatus.SUCCEEDED,
        step_ids=[run_step.run_step_id],
        linked_child_run_summary_ids=run_step.child_run_summary_ids,
        produced_artifact_ids=run_step.produced_artifact_ids,
        started_at=FIXED_NOW,
        completed_at=FIXED_NOW,
        notes=["completed"],
        provenance=PROVENANCE,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert workflow_definition.step_definitions[1].dependency_step_names == ["step_one"]
    assert scheduled_run_config.assumed_reference_prices["APEX"] == 101.5
    assert execution.status is WorkflowStatus.SUCCEEDED


def test_retry_policy_rejects_automatic_retry_without_retryable() -> None:
    with pytest.raises(ValidationError):
        RetryPolicy(
            max_attempts=2,
            automatic_retry_enabled=True,
            backoff_seconds=0,
            retryable=False,
        )


def test_runbook_entry_requires_next_action_for_manual_review() -> None:
    with pytest.raises(ValidationError):
        RunbookEntry(
            runbook_entry_id="runbook_1",
            step_name="paper_trade_candidate_generation",
            purpose="Review gate.",
            expected_outputs=["Either trades or an explicit stop."],
            operator_checks=["Check proposal approval state."],
            failure_triage_instructions=["Review proposal notes."],
            manual_review_required=True,
            next_manual_action=None,
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_run_step_rejects_reverse_timestamps() -> None:
    with pytest.raises(ValidationError):
        RunStep(
            run_step_id="rstep_bad",
            workflow_execution_id="dwflow_1",
            step_name="research_workflow",
            sequence_index=3,
            dependency_step_ids=["rstep_prev"],
            owning_service="research_orchestrator",
            status=WorkflowStatus.FAILED,
            attempt_count=1,
            retry_policy=RetryPolicy(
                max_attempts=1,
                automatic_retry_enabled=False,
                backoff_seconds=0,
                retryable=False,
            ),
            failure_action=RunFailureAction.FAIL_WORKFLOW,
            child_workflow_ids=[],
            child_run_summary_ids=[],
            produced_artifact_ids=[],
            notes=["failed"],
            manual_intervention_requirement=ManualInterventionRequirement(
                gate_reason="Needs operator attention.",
                blocking=True,
                required_role="operator",
                related_artifact_ids=[],
                operator_instructions=["Inspect step notes."],
            ),
            started_at=FIXED_NOW,
            completed_at=datetime(2026, 3, 21, 8, 0, tzinfo=UTC),
            provenance=PROVENANCE,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )
