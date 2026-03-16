from __future__ import annotations

from libraries.config import get_settings


def test_settings_resolve_local_artifact_root() -> None:
    settings = get_settings()

    assert settings.allow_live_trading is False
    assert settings.resolved_artifact_root.name == "artifacts"
