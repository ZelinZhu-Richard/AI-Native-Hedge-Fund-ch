from __future__ import annotations

from libraries.utils import (
    make_company_id,
    make_document_id,
    make_prefixed_id,
    make_source_reference_id,
    validate_prefixed_id,
)


def test_make_prefixed_id_uses_expected_prefix() -> None:
    identifier = make_prefixed_id("memo")

    assert validate_prefixed_id(identifier, "memo")
    assert identifier.startswith("memo_")


def test_canonical_source_reference_id_is_deterministic() -> None:
    first = make_source_reference_id(
        source_type=" newswire ",
        external_id="NEWS:APEX:001",
        uri="HTTPS://NEWS.EXAMPLE.COM/APEX/001",
    )
    second = make_source_reference_id(
        source_type="newswire",
        external_id="news:apex:001",
        uri="https://news.example.com/apex/001",
    )

    assert first == second


def test_company_and_document_ids_are_stable() -> None:
    company_id = make_company_id(
        legal_name="  Apex Instruments, Inc. ",
        ticker="APEX",
        country_of_risk="US",
    )
    document_id = make_document_id(
        document_kind="filing",
        source_reference_id="src_example",
        external_id="0001983210-26-000041",
    )

    assert company_id.startswith("co_")
    assert document_id.startswith("doc_")
