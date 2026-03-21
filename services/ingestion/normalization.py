from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from pydantic import Field

from libraries.core import build_provenance
from libraries.schemas import (
    AvailabilityWindow,
    Company,
    DataLayer,
    DocumentStatus,
    EarningsCall,
    Filing,
    NewsItem,
    PriceSeriesMetadata,
    PriceSeriesStatus,
    SourceReference,
    StrictModel,
    TimingAnomaly,
)
from libraries.time import Clock, parse_datetime_value, resolve_effective_time
from libraries.utils import (
    make_canonical_id,
    make_company_id,
    make_document_id,
    make_source_reference_id,
)
from services.ingestion.payloads import (
    RawCompanyFixture,
    RawCompanyReference,
    RawFilingFixture,
    RawFixturePayload,
    RawNewsFixture,
    RawPriceSeriesMetadataFixture,
    RawTranscriptFixture,
)
from services.timing import TimingService


class FixtureNormalizationResult(StrictModel):
    """Normalized artifacts produced from a single raw fixture."""

    fixture_name: str = Field(description="Name of the source fixture that was normalized.")
    fixture_type: str = Field(description="Fixture type processed by the normalization flow.")
    ingested_at: datetime = Field(description="UTC timestamp when the local ingestion ran.")
    source_reference: SourceReference = Field(description="Canonical source reference record.")
    source_availability_window: AvailabilityWindow | None = Field(
        default=None,
        description="Conservative availability window resolved for the source when applicable.",
    )
    company: Company | None = Field(default=None, description="Canonical company record if created.")
    filing: Filing | None = Field(default=None, description="Canonical filing if created.")
    earnings_call: EarningsCall | None = Field(
        default=None, description="Canonical earnings call record if created."
    )
    news_item: NewsItem | None = Field(default=None, description="Canonical news item if created.")
    price_series_metadata: PriceSeriesMetadata | None = Field(
        default=None,
        description="Canonical price series metadata record if created.",
    )
    timing_anomalies: list[TimingAnomaly] = Field(
        default_factory=list,
        description="Structured timing anomalies detected during normalization.",
    )


def normalize_raw_fixture(
    payload: RawFixturePayload,
    *,
    clock: Clock,
    fixture_path: str | None = None,
) -> FixtureNormalizationResult:
    """Normalize a raw fixture into canonical typed artifacts."""

    ingested_at = clock.now()
    timing_service = TimingService(clock=clock)
    source_reference = _build_source_reference(
        payload=payload,
        clock=clock,
        ingested_at=ingested_at,
        fixture_path=fixture_path,
    )
    source_publication_timing, source_timing_anomalies = timing_service.build_source_reference_timing(
        source_reference=source_reference
    )
    source_reference = source_reference.model_copy(update={"publication_timing": source_publication_timing})
    timing_anomalies = list(source_timing_anomalies)
    source_availability_window: AvailabilityWindow | None = None
    if isinstance(payload, RawFilingFixture):
        company = _normalize_company(
            raw_company=payload.company,
            source_reference=source_reference,
            clock=clock,
            ingested_at=ingested_at,
            fixture_path=fixture_path,
        )
        filing = Filing(
            document_id=make_document_id(
                document_kind="filing",
                source_reference_id=source_reference.source_reference_id,
                external_id=payload.accession_number,
            ),
            company_id=company.company_id,
            title=payload.title,
            source_reference_id=source_reference.source_reference_id,
            external_id=payload.external_id,
            data_layer=DataLayer.NORMALIZED,
            language="en",
            storage_uri=None,
            content_hash=_hash_text(payload.raw_text),
            source_published_at=source_reference.published_at,
            effective_at=source_reference.effective_at,
            ingested_at=ingested_at,
            processed_at=ingested_at,
            status=DocumentStatus.NORMALIZED,
            tags=["filing", payload.form_type.value.lower()],
            provenance=build_provenance(
                clock=clock,
                transformation_name="filing_normalization",
                source_reference_ids=[source_reference.source_reference_id],
                ingestion_time=ingested_at,
                notes=_fixture_notes(fixture_path),
            ),
            created_at=ingested_at,
            updated_at=ingested_at,
            form_type=payload.form_type,
            accession_number=payload.accession_number,
            filing_date=payload.filing_date,
            period_end_date=payload.period_end_date,
            amendment=payload.amendment,
            exhibit_ids=[],
            raw_html_uri=payload.uri,
            normalized_text_uri=None,
        )
        (
            document_timing,
            source_availability_window,
            document_timing_anomalies,
        ) = timing_service.build_document_timing(document=filing, source_reference=source_reference)
        filing = filing.model_copy(update={"publication_timing": document_timing})
        timing_anomalies.extend(document_timing_anomalies)
        return FixtureNormalizationResult(
            fixture_name=payload.fixture_name,
            fixture_type=payload.fixture_type,
            ingested_at=ingested_at,
            source_reference=source_reference,
            source_availability_window=source_availability_window,
            company=company,
            filing=filing,
            timing_anomalies=timing_anomalies,
        )
    if isinstance(payload, RawTranscriptFixture):
        company = _normalize_company(
            raw_company=payload.company,
            source_reference=source_reference,
            clock=clock,
            ingested_at=ingested_at,
            fixture_path=fixture_path,
        )
        earnings_call = EarningsCall(
            document_id=make_document_id(
                document_kind="earnings_call",
                source_reference_id=source_reference.source_reference_id,
                external_id=payload.external_id,
            ),
            company_id=company.company_id,
            title=payload.title,
            source_reference_id=source_reference.source_reference_id,
            external_id=payload.external_id,
            data_layer=DataLayer.NORMALIZED,
            language="en",
            storage_uri=None,
            content_hash=_hash_text(payload.raw_text),
            source_published_at=source_reference.published_at,
            effective_at=source_reference.effective_at,
            ingested_at=ingested_at,
            processed_at=ingested_at,
            status=DocumentStatus.NORMALIZED,
            tags=["earnings_call", f"q{payload.fiscal_quarter}"],
            provenance=build_provenance(
                clock=clock,
                transformation_name="earnings_call_normalization",
                source_reference_ids=[source_reference.source_reference_id],
                ingestion_time=ingested_at,
                notes=_fixture_notes(fixture_path),
            ),
            created_at=ingested_at,
            updated_at=ingested_at,
            call_datetime=parse_datetime_value(payload.call_datetime),
            fiscal_year=payload.fiscal_year,
            fiscal_quarter=payload.fiscal_quarter,
            prepared_remarks_uri=None,
            q_and_a_uri=None,
            participants=payload.participants,
        )
        (
            document_timing,
            source_availability_window,
            document_timing_anomalies,
        ) = timing_service.build_document_timing(
            document=earnings_call,
            source_reference=source_reference,
        )
        earnings_call = earnings_call.model_copy(update={"publication_timing": document_timing})
        timing_anomalies.extend(document_timing_anomalies)
        return FixtureNormalizationResult(
            fixture_name=payload.fixture_name,
            fixture_type=payload.fixture_type,
            ingested_at=ingested_at,
            source_reference=source_reference,
            source_availability_window=source_availability_window,
            company=company,
            earnings_call=earnings_call,
            timing_anomalies=timing_anomalies,
        )
    if isinstance(payload, RawNewsFixture):
        news_company: Company | None = None
        if payload.company is not None:
            news_company = _normalize_company(
                raw_company=payload.company,
                source_reference=source_reference,
                clock=clock,
                ingested_at=ingested_at,
                fixture_path=fixture_path,
            )
        news_item = NewsItem(
            document_id=make_document_id(
                document_kind="news_item",
                source_reference_id=source_reference.source_reference_id,
                external_id=payload.external_id,
            ),
            company_id=news_company.company_id if news_company is not None else None,
            title=payload.title,
            source_reference_id=source_reference.source_reference_id,
            external_id=payload.external_id,
            data_layer=DataLayer.NORMALIZED,
            language="en",
            storage_uri=None,
            content_hash=_hash_text(payload.raw_text),
            source_published_at=source_reference.published_at,
            effective_at=source_reference.effective_at,
            ingested_at=ingested_at,
            processed_at=ingested_at,
            status=DocumentStatus.NORMALIZED,
            tags=["news", payload.publisher.lower().replace(" ", "_")],
            provenance=build_provenance(
                clock=clock,
                transformation_name="news_item_normalization",
                source_reference_ids=[source_reference.source_reference_id],
                ingestion_time=ingested_at,
                notes=_fixture_notes(fixture_path),
            ),
            created_at=ingested_at,
            updated_at=ingested_at,
            publisher=payload.publisher,
            author_names=payload.author_names,
            headline=payload.headline,
            summary=payload.summary,
            relevance_score=None,
            embargo_lifted_at=None,
        )
        (
            document_timing,
            source_availability_window,
            document_timing_anomalies,
        ) = timing_service.build_document_timing(document=news_item, source_reference=source_reference)
        news_item = news_item.model_copy(update={"publication_timing": document_timing})
        timing_anomalies.extend(document_timing_anomalies)
        return FixtureNormalizationResult(
            fixture_name=payload.fixture_name,
            fixture_type=payload.fixture_type,
            ingested_at=ingested_at,
            source_reference=source_reference,
            source_availability_window=source_availability_window,
            company=news_company,
            news_item=news_item,
            timing_anomalies=timing_anomalies,
        )
    if isinstance(payload, RawCompanyFixture):
        company = _normalize_company(
            raw_company=payload.company,
            source_reference=source_reference,
            clock=clock,
            ingested_at=ingested_at,
            fixture_path=fixture_path,
        )
        return FixtureNormalizationResult(
            fixture_name=payload.fixture_name,
            fixture_type=payload.fixture_type,
            ingested_at=ingested_at,
            source_reference=source_reference,
            source_availability_window=None,
            company=company,
            timing_anomalies=timing_anomalies,
        )
    assert isinstance(payload, RawPriceSeriesMetadataFixture)
    timing_anomalies.extend(timing_service.validate_timezone_name(payload.timezone))
    company = _normalize_company(
        raw_company=payload.company,
        source_reference=source_reference,
        clock=clock,
        ingested_at=ingested_at,
        fixture_path=fixture_path,
    )
    price_series_metadata = PriceSeriesMetadata(
        price_series_metadata_id=make_canonical_id(
            "pxmeta",
            company.company_id,
            payload.dataset_name,
            payload.symbol,
        ),
        company_id=company.company_id,
        symbol=payload.symbol,
        exchange=payload.exchange,
        currency=payload.currency,
        frequency=payload.frequency,
        timezone=payload.timezone,
        dataset_name=payload.dataset_name,
        source_reference_id=source_reference.source_reference_id,
        vendor_symbol=payload.vendor_symbol,
        first_price_date=payload.first_price_date,
        last_price_date=payload.last_price_date,
        status=PriceSeriesStatus.PLACEHOLDER,
        provenance=build_provenance(
            clock=clock,
            transformation_name="price_series_metadata_normalization",
            source_reference_ids=[source_reference.source_reference_id],
            ingestion_time=ingested_at,
            notes=_fixture_notes(fixture_path),
        ),
        created_at=ingested_at,
        updated_at=ingested_at,
    )
    return FixtureNormalizationResult(
        fixture_name=payload.fixture_name,
        fixture_type=payload.fixture_type,
        ingested_at=ingested_at,
        source_reference=source_reference,
        source_availability_window=None,
        company=company,
        price_series_metadata=price_series_metadata,
        timing_anomalies=timing_anomalies,
    )


def _build_source_reference(
    *,
    payload: RawFixturePayload,
    clock: Clock,
    ingested_at: datetime,
    fixture_path: str | None,
) -> SourceReference:
    """Construct a canonical source reference from a raw fixture payload."""

    published_at = _normalize_optional_datetime(payload.published_at)
    retrieved_at = parse_datetime_value(payload.retrieved_at)
    explicit_effective_at = _payload_effective_at(payload)
    content_hash = _hash_text(_payload_hash_input(payload))
    return SourceReference(
        source_reference_id=make_source_reference_id(
            source_type=payload.source_type.value,
            external_id=payload.external_id,
            uri=payload.uri,
        ),
        source_type=payload.source_type,
        external_id=payload.external_id,
        uri=payload.uri,
        title=payload.title,
        publisher=getattr(payload, "publisher", None),
        content_hash=content_hash,
        published_at=published_at,
        retrieved_at=retrieved_at,
        effective_at=resolve_effective_time(
            explicit_effective_at=explicit_effective_at,
            published_at=published_at,
            ingestion_time=retrieved_at,
        ),
        license=None,
        provenance=build_provenance(
            clock=clock,
            transformation_name="source_reference_normalization",
            ingestion_time=ingested_at,
            notes=_fixture_notes(fixture_path),
        ),
        created_at=ingested_at,
        updated_at=ingested_at,
    )


def _normalize_company(
    *,
    raw_company: RawCompanyReference,
    source_reference: SourceReference,
    clock: Clock,
    ingested_at: datetime,
    fixture_path: str | None,
) -> Company:
    """Construct a canonical company record from raw fixture metadata."""

    return Company(
        company_id=make_company_id(
            legal_name=raw_company.legal_name,
            cik=raw_company.cik,
            ticker=raw_company.ticker,
            country_of_risk=raw_company.country_of_risk,
        ),
        legal_name=raw_company.legal_name,
        ticker=raw_company.ticker,
        exchange=raw_company.exchange,
        cik=raw_company.cik,
        isin=raw_company.isin,
        lei=raw_company.lei,
        figi=raw_company.figi,
        sector=raw_company.sector,
        industry=raw_company.industry,
        country_of_risk=raw_company.country_of_risk,
        active=True,
        provenance=build_provenance(
            clock=clock,
            transformation_name="company_normalization",
            source_reference_ids=[source_reference.source_reference_id],
            ingestion_time=ingested_at,
            notes=_fixture_notes(fixture_path),
        ),
        created_at=ingested_at,
        updated_at=ingested_at,
    )


def _normalize_optional_datetime(value: datetime | None) -> datetime | None:
    """Normalize optional datetimes to timezone-aware UTC."""

    if value is None:
        return None
    return parse_datetime_value(value)


def _payload_effective_at(payload: RawFixturePayload) -> datetime | None:
    """Resolve the best effective timestamp candidate carried by the raw payload."""

    if payload.effective_at is not None:
        return parse_datetime_value(payload.effective_at)
    if isinstance(payload, RawCompanyFixture):
        return parse_datetime_value(payload.as_of_time)
    return None


def _fixture_notes(fixture_path: str | None) -> list[str]:
    """Build provenance notes for fixture-backed normalization."""

    if fixture_path is None:
        return []
    return [f"fixture_path={fixture_path}"]


def _hash_text(value: str) -> str:
    """Hash textual content for stable source/content fingerprints."""

    return sha256(value.encode("utf-8")).hexdigest()


def _payload_hash_input(payload: RawFixturePayload) -> str:
    """Build a stable payload fingerprint input for source references."""

    if isinstance(payload, (RawFilingFixture, RawTranscriptFixture, RawNewsFixture)):
        return payload.raw_text
    return payload.model_dump_json()
