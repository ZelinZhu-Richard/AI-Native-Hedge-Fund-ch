from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

import services.daily_orchestration.service as orchestration_service_module
from libraries.schemas import (
    ManualInterventionRequirement,
    WorkflowStatus,
)
from libraries.time import FrozenClock
from services.daily_orchestration.definitions import get_step_specs
from services.daily_orchestration.executors import DailyWorkflowState, StepExecutionOutcome
from services.daily_orchestration.service import (
    DailyOrchestrationService,
    RunDailyWorkflowRequest,
)

FIXED_NOW = datetime(2026, 3, 21, 10, 0, tzinfo=UTC)


def test_daily_workflow_orders_steps_and_links_child_run_summaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        orchestration_service_module,
        "build_executor_registry",
        lambda: _success_registry(),
    )
    service = DailyOrchestrationService(clock=FrozenClock(FIXED_NOW))

    response = service.run_daily_workflow(
        RunDailyWorkflowRequest(
            artifact_root=tmp_path / "artifacts",
            requested_by="unit_test",
        )
    )

    expected_steps = [spec.step_name for spec in get_step_specs()]
    assert [step.step_name for step in response.run_steps] == expected_steps
    assert response.workflow_execution.status is WorkflowStatus.SUCCEEDED
    assert response.workflow_execution.linked_child_run_summary_ids == [
        f"runsum_{step_name}" for step_name in expected_steps
    ]


def test_retryable_step_retries_once_then_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"fixture_refresh_and_normalization": 0}
    registry = _success_registry()

    def flaky_fixture_refresh(_state: DailyWorkflowState) -> StepExecutionOutcome:
        attempts["fixture_refresh_and_normalization"] += 1
        if attempts["fixture_refresh_and_normalization"] == 1:
            raise RuntimeError("transient fixture error")
        return StepExecutionOutcome(
            status=WorkflowStatus.SUCCEEDED,
            notes=["fixture refresh recovered"],
            child_workflow_ids=["fixture_refresh_and_normalization_wf"],
            child_run_summary_ids=["runsum_fixture_refresh_and_normalization"],
            produced_artifact_ids=["artifact_fixture_refresh_and_normalization"],
        )

    registry["fixture_refresh_and_normalization"] = flaky_fixture_refresh
    monkeypatch.setattr(
        orchestration_service_module,
        "build_executor_registry",
        lambda: registry,
    )
    service = DailyOrchestrationService(clock=FrozenClock(FIXED_NOW))

    response = service.run_daily_workflow(
        RunDailyWorkflowRequest(
            artifact_root=tmp_path / "artifacts",
            requested_by="unit_test",
        )
    )

    first_step = response.run_steps[0]
    assert response.workflow_execution.status is WorkflowStatus.SUCCEEDED
    assert first_step.attempt_count == 2
    assert any("Retrying step `fixture_refresh_and_normalization`" in note for note in first_step.notes)


def test_retryable_failure_stops_workflow_after_second_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _success_registry()

    def always_fail(_state: DailyWorkflowState) -> StepExecutionOutcome:
        raise RuntimeError("fixture refresh remained broken")

    registry["fixture_refresh_and_normalization"] = always_fail
    monkeypatch.setattr(
        orchestration_service_module,
        "build_executor_registry",
        lambda: registry,
    )
    service = DailyOrchestrationService(clock=FrozenClock(FIXED_NOW))

    response = service.run_daily_workflow(
        RunDailyWorkflowRequest(
            artifact_root=tmp_path / "artifacts",
            requested_by="unit_test",
        )
    )

    assert response.workflow_execution.status is WorkflowStatus.FAILED
    assert response.run_steps[0].attempt_count == 2
    assert response.run_steps[0].status is WorkflowStatus.FAILED
    assert all(step.status is WorkflowStatus.QUEUED for step in response.run_steps[1:])


def test_manual_review_gate_marks_workflow_attention_required_without_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _success_registry()

    def paper_trade_gate(_state: DailyWorkflowState) -> StepExecutionOutcome:
        return StepExecutionOutcome(
            status=WorkflowStatus.ATTENTION_REQUIRED,
            notes=["Proposal requires explicit approval before paper-trade creation."],
            manual_intervention_requirement=ManualInterventionRequirement(
                gate_reason="Explicit PM review is still required.",
                blocking=True,
                required_role="portfolio_reviewer",
                related_artifact_ids=["proposal_1"],
                operator_instructions=["Review the proposal before retrying paper-trade generation."],
            ),
            stop_workflow=False,
        )

    registry["paper_trade_candidate_generation"] = paper_trade_gate
    monkeypatch.setattr(
        orchestration_service_module,
        "build_executor_registry",
        lambda: registry,
    )
    service = DailyOrchestrationService(clock=FrozenClock(FIXED_NOW))

    response = service.run_daily_workflow(
        RunDailyWorkflowRequest(
            artifact_root=tmp_path / "artifacts",
            requested_by="unit_test",
        )
    )

    paper_trade_step = next(
        step for step in response.run_steps if step.step_name == "paper_trade_candidate_generation"
    )
    operations_summary_step = next(
        step for step in response.run_steps if step.step_name == "operations_summary"
    )

    assert response.workflow_execution.status is WorkflowStatus.ATTENTION_REQUIRED
    assert paper_trade_step.status is WorkflowStatus.ATTENTION_REQUIRED
    assert paper_trade_step.manual_intervention_requirement is not None
    assert operations_summary_step.status is WorkflowStatus.SUCCEEDED


def _success_registry() -> dict[str, Callable[[DailyWorkflowState], StepExecutionOutcome]]:
    registry: dict[str, Callable[[DailyWorkflowState], StepExecutionOutcome]] = {}
    for spec in get_step_specs():
        registry[spec.step_name] = _make_success_executor(spec.step_name)
    return registry


def _make_success_executor(
    step_name: str,
) -> Callable[[DailyWorkflowState], StepExecutionOutcome]:
    def executor(_state: DailyWorkflowState) -> StepExecutionOutcome:
        return StepExecutionOutcome(
            status=WorkflowStatus.SUCCEEDED,
            notes=[f"{step_name} completed"],
            child_workflow_ids=[f"{step_name}_wf"],
            child_run_summary_ids=[f"runsum_{step_name}"],
            produced_artifact_ids=[f"artifact_{step_name}"],
        )

    return executor
