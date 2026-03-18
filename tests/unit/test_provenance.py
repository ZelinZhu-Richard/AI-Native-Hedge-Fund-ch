from __future__ import annotations

from datetime import UTC, datetime

from libraries.core import build_provenance
from libraries.time import FrozenClock


def test_build_provenance_captures_versions_and_clock() -> None:
    fixed_now = datetime(2026, 3, 16, 9, 0, tzinfo=UTC)
    provenance = build_provenance(
        clock=FrozenClock(fixed_now),
        transformation_name="unit_test",
        upstream_artifact_ids=["hyp_test"],
        agent_run_id="agent_run_test",
    )

    assert provenance.processing_time == fixed_now
    assert provenance.config_version == "week1"
    assert provenance.agent_run_id == "agent_run_test"
    assert provenance.upstream_artifact_ids == ["hyp_test"]
