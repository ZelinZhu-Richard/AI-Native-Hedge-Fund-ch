from __future__ import annotations

from uuid import uuid4


def make_prefixed_id(prefix: str) -> str:
    """Create a deterministic-looking entity identifier with a stable prefix."""

    normalized_prefix = prefix.strip().lower()
    if not normalized_prefix or "_" in normalized_prefix:
        raise ValueError("Prefix must be non-empty and must not contain underscores.")
    return f"{normalized_prefix}_{uuid4().hex}"


def validate_prefixed_id(identifier: str, prefix: str) -> bool:
    """Validate that an identifier uses the expected entity prefix."""

    return identifier.startswith(f"{prefix.strip().lower()}_")
