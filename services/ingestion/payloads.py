from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from libraries.schemas import FilingForm, SourceType, StrictModel


class RawCompanyReference(StrictModel):
    """Raw company identity information carried inside source fixtures."""

    legal_name: str = Field(description="Company legal name from the upstream source.")
    ticker: str | None = Field(default=None, description="Ticker symbol if present in the source.")
    exchange: str | None = Field(default=None, description="Exchange code if present in the source.")
    cik: str | None = Field(default=None, description="SEC CIK if present in the source.")
    isin: str | None = Field(default=None, description="ISIN if present in the source.")
    lei: str | None = Field(default=None, description="LEI if present in the source.")
    figi: str | None = Field(default=None, description="FIGI if present in the source.")
    sector: str | None = Field(default=None, description="Sector classification if supplied.")
    industry: str | None = Field(default=None, description="Industry classification if supplied.")
    country_of_risk: str | None = Field(default=None, description="Country of risk if supplied.")


class RawSourceFixtureBase(StrictModel):
    """Shared source metadata for local ingestion fixtures."""

    fixture_name: str = Field(description="Human-readable fixture name.")
    source_type: SourceType = Field(description="Canonical source type for the fixture.")
    external_id: str = Field(description="Upstream source identifier.")
    uri: str = Field(description="Canonical upstream URI or stable local stand-in.")
    title: str = Field(description="Human-readable source title.")
    published_at: datetime | None = Field(
        default=None,
        description="Upstream publication or visibility timestamp when known.",
    )
    retrieved_at: datetime = Field(description="Timestamp when the fixture was retrieved upstream.")
    effective_at: datetime | None = Field(
        default=None,
        description="Timestamp when the information became actionable if distinct from publication.",
    )


class RawFilingFixture(RawSourceFixtureBase):
    """Raw filing payload fixture."""

    fixture_type: Literal["filing"] = "filing"
    company: RawCompanyReference = Field(description="Company metadata embedded in the filing source.")
    form_type: FilingForm = Field(description="Filing form classification.")
    accession_number: str = Field(description="SEC accession number or equivalent.")
    filing_date: date = Field(description="Official filing date.")
    period_end_date: date = Field(description="Period end date described by the filing.")
    amendment: bool = Field(default=False, description="Whether the filing is an amendment.")
    raw_text: str = Field(description="Raw filing text or a representative excerpt.")


class RawTranscriptFixture(RawSourceFixtureBase):
    """Raw earnings call transcript fixture."""

    fixture_type: Literal["earnings_call"] = "earnings_call"
    company: RawCompanyReference = Field(
        description="Company metadata embedded in the transcript source."
    )
    call_datetime: datetime = Field(description="Timestamp of the earnings call event.")
    fiscal_year: int = Field(ge=1900, description="Fiscal year discussed on the call.")
    fiscal_quarter: int = Field(ge=1, le=4, description="Fiscal quarter discussed on the call.")
    participants: list[str] = Field(default_factory=list, description="Call participants.")
    raw_text: str = Field(description="Raw transcript excerpt or transcript body.")


class RawNewsFixture(RawSourceFixtureBase):
    """Raw financial news fixture."""

    fixture_type: Literal["news_item"] = "news_item"
    company: RawCompanyReference | None = Field(
        default=None,
        description="Associated company metadata when the article is company-specific.",
    )
    publisher: str = Field(description="News publisher or wire service.")
    headline: str = Field(description="Headline from the upstream source.")
    summary: str | None = Field(default=None, description="Summary or deck from the source.")
    author_names: list[str] = Field(default_factory=list, description="Source bylines.")
    raw_text: str = Field(description="Raw article text or excerpt.")


class RawCompanyFixture(RawSourceFixtureBase):
    """Raw company reference-data fixture."""

    fixture_type: Literal["company"] = "company"
    company: RawCompanyReference = Field(description="Canonical company reference data payload.")
    as_of_time: datetime = Field(description="Timestamp the reference data is valid as of.")


class RawPriceSeriesMetadataFixture(RawSourceFixtureBase):
    """Raw price-series metadata fixture without actual price history."""

    fixture_type: Literal["price_series_metadata"] = "price_series_metadata"
    company: RawCompanyReference = Field(description="Associated company metadata.")
    symbol: str = Field(description="Primary tradable symbol.")
    exchange: str | None = Field(default=None, description="Primary exchange code.")
    currency: str = Field(description="Quoted currency for the series.")
    frequency: str = Field(description="Series frequency, for example `daily`.")
    timezone: str = Field(description="Source timezone for the market data feed.")
    dataset_name: str = Field(description="Canonical upstream dataset name.")
    vendor_symbol: str | None = Field(default=None, description="Vendor-specific symbol if different.")
    first_price_date: date | None = Field(default=None, description="First known price date.")
    last_price_date: date | None = Field(default=None, description="Most recent known price date.")


RawFixturePayload = Annotated[
    RawFilingFixture
    | RawTranscriptFixture
    | RawNewsFixture
    | RawCompanyFixture
    | RawPriceSeriesMetadataFixture,
    Field(discriminator="fixture_type"),
]

RAW_FIXTURE_PAYLOAD_ADAPTER: TypeAdapter[RawFixturePayload] = TypeAdapter(RawFixturePayload)
