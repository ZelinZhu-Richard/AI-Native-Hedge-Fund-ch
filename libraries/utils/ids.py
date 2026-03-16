from __future__ import annotations

from hashlib import sha256
from uuid import uuid4


def _normalize_part(value: str) -> str:
    """Normalize identifier input parts for stable hashing."""

    return " ".join(value.strip().lower().split())


def make_prefixed_id(prefix: str) -> str:
    """Create a deterministic-looking entity identifier with a stable prefix."""

    normalized_prefix = prefix.strip().lower()
    if not normalized_prefix or "_" in normalized_prefix:
        raise ValueError("Prefix must be non-empty and must not contain underscores.")
    return f"{normalized_prefix}_{uuid4().hex}"


def make_canonical_id(prefix: str, *parts: str) -> str:
    """Create a deterministic canonical identifier from stable source parts."""

    normalized_prefix = prefix.strip().lower()
    if not normalized_prefix or "_" in normalized_prefix:
        raise ValueError("Prefix must be non-empty and must not contain underscores.")
    if not parts:
        raise ValueError("At least one canonical ID part is required.")
    normalized_parts = [_normalize_part(part) for part in parts if _normalize_part(part)]
    if not normalized_parts:
        raise ValueError("Canonical ID parts must contain at least one non-empty value.")
    digest = sha256("||".join(normalized_parts).encode("utf-8")).hexdigest()[:24]
    return f"{normalized_prefix}_{digest}"


def make_company_id(
    *,
    legal_name: str,
    cik: str | None = None,
    ticker: str | None = None,
    country_of_risk: str | None = None,
) -> str:
    """Build a deterministic company ID from the strongest available identifiers."""

    if cik:
        return make_canonical_id("co", cik)
    parts = [part for part in [ticker, legal_name, country_of_risk] if part]
    return make_canonical_id("co", *parts)


def make_source_reference_id(*, source_type: str, external_id: str | None, uri: str) -> str:
    """Build a deterministic source reference ID."""

    parts = [source_type, uri]
    if external_id:
        parts.insert(1, external_id)
    return make_canonical_id("src", *parts)


def make_document_id(*, document_kind: str, source_reference_id: str, external_id: str | None) -> str:
    """Build a deterministic document ID."""

    parts = [document_kind, source_reference_id]
    if external_id:
        parts.append(external_id)
    return make_canonical_id("doc", *parts)


def validate_prefixed_id(identifier: str, prefix: str) -> bool:
    """Validate that an identifier uses the expected entity prefix."""

    return identifier.startswith(f"{prefix.strip().lower()}_")
