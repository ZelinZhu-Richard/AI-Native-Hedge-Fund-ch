from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from libraries.schemas import (
    Company,
    ResolutionConfidence,
    ResolutionDecisionStatus,
)
from services.ingestion.payloads import RawCompanyReference


@dataclass(frozen=True)
class CompanyMatchOutcome:
    """Deterministic company-match outcome used by the entity-resolution service."""

    candidate_company_ids: list[str]
    selected_company_id: str | None
    status: ResolutionDecisionStatus
    confidence: ResolutionConfidence
    rule_name: str
    rationale: str
    matched_aliases: list[str]


def normalize_match_text(value: str) -> str:
    """Normalize match text for deterministic exact comparisons."""

    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(normalized.split())


def resolve_company_reference(
    *,
    raw_company: RawCompanyReference,
    companies_by_id: dict[str, Company],
    company_alias_map: dict[str, set[str]] | None = None,
) -> CompanyMatchOutcome:
    """Resolve one raw company reference against canonical company records."""

    cik_matches = _identifier_matches(
        companies=companies_by_id.values(),
        identifier_value=raw_company.cik,
        accessor=lambda company: company.cik,
    )
    if cik_matches:
        return _match_outcome(
            candidate_company_ids=cik_matches,
            rule_name="exact_cik",
            rationale="Resolved from an exact CIK match.",
            confidence=ResolutionConfidence.HIGH,
        )

    figi_matches = _identifier_matches(
        companies=companies_by_id.values(),
        identifier_value=raw_company.figi,
        accessor=lambda company: company.figi,
    )
    if figi_matches:
        return _match_outcome(
            candidate_company_ids=figi_matches,
            rule_name="exact_figi",
            rationale="Resolved from an exact FIGI match.",
            confidence=ResolutionConfidence.HIGH,
        )

    isin_matches = _identifier_matches(
        companies=companies_by_id.values(),
        identifier_value=raw_company.isin,
        accessor=lambda company: company.isin,
    )
    if isin_matches:
        return _match_outcome(
            candidate_company_ids=isin_matches,
            rule_name="exact_isin",
            rationale="Resolved from an exact ISIN match.",
            confidence=ResolutionConfidence.HIGH,
        )

    lei_matches = _identifier_matches(
        companies=companies_by_id.values(),
        identifier_value=raw_company.lei,
        accessor=lambda company: company.lei,
    )
    if lei_matches:
        return _match_outcome(
            candidate_company_ids=lei_matches,
            rule_name="exact_lei",
            rationale="Resolved from an exact LEI match.",
            confidence=ResolutionConfidence.HIGH,
        )

    ticker_exchange_matches = _ticker_exchange_matches(
        companies=companies_by_id.values(),
        ticker=raw_company.ticker,
        exchange=raw_company.exchange,
    )
    if ticker_exchange_matches:
        return _match_outcome(
            candidate_company_ids=ticker_exchange_matches,
            rule_name="exact_ticker_exchange",
            rationale="Resolved from an exact ticker and exchange match.",
            confidence=ResolutionConfidence.MEDIUM,
        )

    legal_name_matches = _legal_name_matches(
        companies=companies_by_id.values(),
        legal_name=raw_company.legal_name,
    )
    if legal_name_matches:
        return _match_outcome(
            candidate_company_ids=legal_name_matches,
            rule_name="exact_legal_name",
            rationale="Resolved from an exact normalized legal-name match.",
            confidence=ResolutionConfidence.MEDIUM,
        )

    alias_matches = _alias_matches(
        alias_map=company_alias_map or {},
        alias_text=raw_company.legal_name,
    )
    if alias_matches:
        return _match_outcome(
            candidate_company_ids=alias_matches,
            rule_name="exact_preserved_alias",
            rationale="Resolved from an exact preserved company-alias match.",
            confidence=ResolutionConfidence.MEDIUM,
            matched_aliases=[normalize_match_text(raw_company.legal_name)],
        )

    return CompanyMatchOutcome(
        candidate_company_ids=[],
        selected_company_id=None,
        status=ResolutionDecisionStatus.UNRESOLVED,
        confidence=ResolutionConfidence.UNRESOLVED,
        rule_name="no_supported_identifier_match",
        rationale="No exact identifier or legal-name match resolved this company reference.",
        matched_aliases=[],
    )


def match_text_against_aliases(
    *,
    text: str,
    alias_map: dict[str, set[str]],
    rule_name: str,
    confidence: ResolutionConfidence,
    rationale: str,
) -> CompanyMatchOutcome:
    """Match one text field against exact preserved aliases deterministically."""

    normalized_text = normalize_match_text(text)
    if not normalized_text:
        return CompanyMatchOutcome(
            candidate_company_ids=[],
            selected_company_id=None,
            status=ResolutionDecisionStatus.UNRESOLVED,
            confidence=ResolutionConfidence.UNRESOLVED,
            rule_name=f"{rule_name}_empty_text",
            rationale="Text was empty after normalization.",
            matched_aliases=[],
        )

    padded_text = f" {normalized_text} "
    matched_aliases = sorted(
        alias
        for alias in alias_map
        if alias and len(alias) >= 2 and f" {alias} " in padded_text
    )
    candidate_company_ids = sorted(
        {
            company_id
            for alias in matched_aliases
            for company_id in alias_map.get(alias, set())
        }
    )
    if not candidate_company_ids:
        return CompanyMatchOutcome(
            candidate_company_ids=[],
            selected_company_id=None,
            status=ResolutionDecisionStatus.UNRESOLVED,
            confidence=ResolutionConfidence.UNRESOLVED,
            rule_name=f"{rule_name}_no_match",
            rationale="No preserved alias matched this text exactly.",
            matched_aliases=[],
        )
    return _match_outcome(
        candidate_company_ids=candidate_company_ids,
        rule_name=rule_name,
        rationale=rationale,
        confidence=confidence,
        matched_aliases=matched_aliases,
    )


def build_alias_map(
    *,
    canonical_names_by_company_id: dict[str, str],
    observed_aliases_by_company_id: dict[str, set[str]],
    observed_tickers_by_company_id: dict[str, set[str]],
) -> dict[str, set[str]]:
    """Build a normalized alias map for conservative text matching."""

    alias_map: dict[str, set[str]] = {}
    for company_id, legal_name in canonical_names_by_company_id.items():
        alias_map.setdefault(normalize_match_text(legal_name), set()).add(company_id)
    for company_id, aliases in observed_aliases_by_company_id.items():
        for alias in aliases:
            alias_map.setdefault(normalize_match_text(alias), set()).add(company_id)
    for company_id, tickers in observed_tickers_by_company_id.items():
        for ticker in tickers:
            alias_map.setdefault(normalize_match_text(ticker), set()).add(company_id)
    return {alias: company_ids for alias, company_ids in alias_map.items() if alias}


def _identifier_matches(
    *,
    companies: Iterable[Company],
    identifier_value: str | None,
    accessor: Callable[[Company], str | None],
) -> list[str]:
    """Return canonical company IDs for one exact identifier value."""

    if identifier_value is None:
        return []
    normalized_identifier = normalize_match_text(identifier_value)
    if not normalized_identifier:
        return []
    return sorted(
        {
            company.company_id
            for company in companies
            if accessor(company) is not None
            and normalize_match_text(str(accessor(company))) == normalized_identifier
        }
    )


def _ticker_exchange_matches(
    *,
    companies: Iterable[Company],
    ticker: str | None,
    exchange: str | None,
) -> list[str]:
    """Return canonical company IDs for one exact ticker and exchange pair."""

    if ticker is None or exchange is None:
        return []
    normalized_ticker = normalize_match_text(ticker)
    normalized_exchange = normalize_match_text(exchange)
    return sorted(
        {
            company.company_id
            for company in companies
            if company.ticker is not None
            and company.exchange is not None
            and normalize_match_text(company.ticker) == normalized_ticker
            and normalize_match_text(company.exchange) == normalized_exchange
        }
    )


def _legal_name_matches(
    *,
    companies: Iterable[Company],
    legal_name: str,
) -> list[str]:
    """Return canonical company IDs for one exact normalized legal name."""

    normalized_legal_name = normalize_match_text(legal_name)
    return sorted(
        {
            company.company_id
            for company in companies
            if normalize_match_text(company.legal_name) == normalized_legal_name
        }
    )


def _alias_matches(
    *,
    alias_map: dict[str, set[str]],
    alias_text: str,
) -> list[str]:
    """Return canonical company IDs for one exact preserved company-name alias."""

    normalized_alias = normalize_match_text(alias_text)
    if not normalized_alias:
        return []
    return sorted(alias_map.get(normalized_alias, set()))


def _match_outcome(
    *,
    candidate_company_ids: list[str],
    rule_name: str,
    rationale: str,
    confidence: ResolutionConfidence,
    matched_aliases: list[str] | None = None,
) -> CompanyMatchOutcome:
    """Build a resolved or ambiguous outcome from exact candidate matches."""

    if len(candidate_company_ids) == 1:
        return CompanyMatchOutcome(
            candidate_company_ids=candidate_company_ids,
            selected_company_id=candidate_company_ids[0],
            status=ResolutionDecisionStatus.RESOLVED,
            confidence=confidence,
            rule_name=rule_name,
            rationale=rationale,
            matched_aliases=matched_aliases or [],
        )
    return CompanyMatchOutcome(
        candidate_company_ids=candidate_company_ids,
        selected_company_id=None,
        status=ResolutionDecisionStatus.AMBIGUOUS,
        confidence=ResolutionConfidence.AMBIGUOUS,
        rule_name=f"{rule_name}_ambiguous",
        rationale="Multiple canonical companies matched the same exact identifier or alias.",
        matched_aliases=matched_aliases or [],
    )
