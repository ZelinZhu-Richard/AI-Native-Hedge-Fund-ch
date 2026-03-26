from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from libraries.schemas import (
    APIResponseEnvelope,
    CapabilityDescriptor,
    DataLayer,
    DemoRunResult,
    ErrorResponse,
    HealthCheckStatus,
    InterfaceWarning,
    ProvenanceRecord,
    ServiceManifest,
    StorageKind,
    WorkflowInvocationResult,
    WorkflowStatus,
)
from libraries.schemas.storage import ArtifactStorageLocation

NOW = datetime(2026, 3, 23, 10, 0, tzinfo=UTC)


def _storage_location(artifact_id: str) -> ArtifactStorageLocation:
    return ArtifactStorageLocation(
        artifact_storage_location_id=f"astore_{artifact_id}",
        artifact_id=artifact_id,
        storage_kind=StorageKind.LOCAL_FILESYSTEM,
        data_layer=DataLayer.DERIVED,
        uri=f"file:///tmp/{artifact_id}.json",
        provenance=ProvenanceRecord(processing_time=NOW),
        created_at=NOW,
        updated_at=NOW,
    )


def test_interface_envelope_and_warning_validate() -> None:
    warning = InterfaceWarning(
        warning_code="local_only",
        message="Local-only interface warning.",
        scope="system",
        related_ids=["route:/system/manifest"],
    )
    capability = CapabilityDescriptor(
        name="portfolio",
        kind="service",
        description="Construct portfolio proposals from signals.",
        inputs=["Signal"],
        outputs=["PortfolioProposal"],
        api_routes=["GET /portfolio/proposals"],
        cli_commands=[],
        config_keys=[],
        notes=[],
    )
    envelope = APIResponseEnvelope[CapabilityDescriptor](
        data=capability,
        warnings=[warning],
        notes=["canonical routes are preferred"],
        generated_at=NOW,
    )

    assert envelope.status == "ok"
    assert envelope.data.name == "portfolio"
    assert envelope.warnings[0].warning_code == "local_only"


def test_error_response_validates() -> None:
    error = ErrorResponse(
        error_code="not_found",
        message="No review queue item exists.",
        details=["target_id: missing"],
        path="/reviews/context/portfolio_proposal/missing",
        timestamp=NOW,
    )

    assert error.status == "error"
    assert error.error_code == "not_found"


def test_workflow_and_demo_results_validate() -> None:
    workflow = WorkflowInvocationResult(
        workflow_name="daily_workflow",
        invocation_kind="api",
        workflow_run_id="dwflow_test",
        status=WorkflowStatus.ATTENTION_REQUIRED,
        artifact_root=Path("/tmp/daily"),
        storage_locations=[_storage_location("dwflow_test")],
        produced_artifact_ids=["wfexec_test"],
        run_summary_ids=["rsum_test"],
        notes=["review required"],
        warnings=[
            InterfaceWarning(
                warning_code="review_required",
                message="The workflow stopped for review.",
                scope="daily_workflow",
            )
        ],
    )
    demo = DemoRunResult(
        workflow_name="demo_end_to_end",
        invocation_kind="cli",
        workflow_run_id="demo_test",
        status=WorkflowStatus.ATTENTION_REQUIRED,
        artifact_root=Path("/tmp/demo"),
        storage_locations=[_storage_location("demo_test")],
        produced_artifact_ids=["pprop_test"],
        run_summary_ids=["rsum_demo"],
        notes=["fixture-backed only"],
        warnings=[],
        demo_run_id="demo_test",
        manifest_path=Path("/tmp/demo/manifest.json"),
        company_id="company_apex_industries",
        portfolio_proposal_id="pprop_test",
        review_queue_total=3,
        paper_trade_candidate_count=0,
        health_status=HealthCheckStatus.WARN,
    )

    assert workflow.status is WorkflowStatus.ATTENTION_REQUIRED
    assert demo.health_status is HealthCheckStatus.WARN


def test_service_manifest_validates() -> None:
    manifest = ServiceManifest(
        project_name="Nexus Tensor Alpha",
        environment="local",
        artifact_root=Path("/tmp/artifacts"),
        generated_at=NOW,
        capabilities=[
            CapabilityDescriptor(
                name="demo_end_to_end",
                kind="workflow",
                description="Run the deterministic local end-to-end demo.",
                inputs=["fixtures root"],
                outputs=["demo manifest"],
                api_routes=["POST /workflows/demo/run"],
                cli_commands=["nta demo run"],
                config_keys=["ARTIFACT_ROOT"],
                notes=["review-bound"],
            )
        ],
        config_surface={
            "PROJECT_NAME": "Nexus Tensor Alpha",
            "ARTIFACT_ROOT": "artifacts",
        },
        warnings=[
            InterfaceWarning(
                warning_code="no_live_trading",
                message="Live trading is intentionally unavailable.",
                scope="system",
            )
        ],
    )

    assert manifest.project_name == "Nexus Tensor Alpha"
    assert manifest.capabilities[0].kind == "workflow"
