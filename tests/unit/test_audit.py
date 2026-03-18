from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from libraries.config import get_settings
from libraries.schemas import AuditOutcome
from libraries.time import FrozenClock
from services.audit import AuditEventRequest, AuditLoggingService

FIXED_NOW = datetime(2026, 3, 18, 10, 0, tzinfo=UTC)


def test_audit_logging_service_persists_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()
    try:
        service = AuditLoggingService(clock=FrozenClock(FIXED_NOW))
        response = service.record_event(
            AuditEventRequest(
                event_type="unit_test_event",
                actor_type="service",
                actor_id="unit_test",
                target_type="workflow",
                target_id="wf_test",
                action="completed",
                outcome=AuditOutcome.WARNING,
                reason="Testing audit persistence.",
                request_id="req_test",
                related_artifact_ids=["art_1", "art_2"],
                notes=["note_a", "note_b"],
            )
        )

        audit_path = artifact_root / "audit" / "audit_logs" / f"{response.audit_log.audit_log_id}.json"
        assert audit_path.exists()
        assert response.audit_log.outcome == AuditOutcome.WARNING
        assert response.audit_log.related_artifact_ids == ["wf_test", "art_1", "art_2"]
        assert response.storage_location.artifact_id == response.audit_log.audit_log_id
    finally:
        get_settings.cache_clear()
