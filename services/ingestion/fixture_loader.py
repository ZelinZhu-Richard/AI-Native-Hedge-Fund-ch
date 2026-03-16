from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from services.ingestion.payloads import RAW_FIXTURE_PAYLOAD_ADAPTER, RawFixturePayload


@dataclass(frozen=True)
class LoadedRawFixture:
    """Exact fixture file contents paired with the validated typed payload."""

    path: Path
    raw_text: str
    payload: RawFixturePayload


def load_raw_fixture(path: Path) -> RawFixturePayload:
    """Load and validate a raw ingestion fixture from disk."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return cast(RawFixturePayload, RAW_FIXTURE_PAYLOAD_ADAPTER.validate_python(payload))


def load_fixture_record(path: Path) -> LoadedRawFixture:
    """Load a raw fixture while preserving the exact on-disk source payload."""

    raw_text = path.read_text(encoding="utf-8")
    payload = cast(RawFixturePayload, RAW_FIXTURE_PAYLOAD_ADAPTER.validate_python(json.loads(raw_text)))
    return LoadedRawFixture(path=path, raw_text=raw_text, payload=payload)


def discover_raw_fixture_paths(root: Path) -> list[Path]:
    """Discover JSON ingestion fixtures under a root directory."""

    return sorted(path for path in root.rglob("*.json") if path.is_file())
