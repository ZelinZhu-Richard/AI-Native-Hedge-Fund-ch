from __future__ import annotations

from libraries.utils import make_prefixed_id, validate_prefixed_id


def test_make_prefixed_id_uses_expected_prefix() -> None:
    identifier = make_prefixed_id("memo")

    assert validate_prefixed_id(identifier, "memo")
    assert identifier.startswith("memo_")
