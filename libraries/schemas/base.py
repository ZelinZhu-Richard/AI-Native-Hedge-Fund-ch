from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _assert_timezone_aware(value: Any, *, field_name: str) -> None:
    """Reject naive datetimes anywhere inside a model field value."""

    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"Field `{field_name}` must use a timezone-aware datetime.")
        return
    if isinstance(value, Mapping):
        for nested_value in value.values():
            _assert_timezone_aware(nested_value, field_name=field_name)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested_value in value:
            _assert_timezone_aware(nested_value, field_name=field_name)


class StrictModel(BaseModel):
    """Repository-wide strict Pydantic base model."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    @model_validator(mode="after")
    def validate_datetime_awareness(self) -> Self:
        """Ensure all datetime values in the model are timezone-aware."""

        for field_name, value in self.__dict__.items():
            _assert_timezone_aware(value, field_name=field_name)
        return self


class TimestampedModel(StrictModel):
    """Base model for entities with creation and update timestamps."""

    created_at: datetime = Field(description="UTC timestamp when the entity record was created.")
    updated_at: datetime = Field(
        description="UTC timestamp when the entity record was last updated."
    )

    @model_validator(mode="after")
    def validate_timestamp_order(self) -> Self:
        """Ensure update time does not precede create time."""

        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be greater than or equal to created_at.")
        return self


class DataLayer(StrEnum):
    """Pipeline layer for a dataset or artifact."""

    RAW = "raw"
    NORMALIZED = "normalized"
    DERIVED = "derived"


class SourceType(StrEnum):
    """Upstream source system categories."""

    SEC_EDGAR = "sec_edgar"
    EARNINGS_TRANSCRIPT_VENDOR = "earnings_transcript_vendor"
    NEWSWIRE = "newswire"
    MARKET_DATA_FEED = "market_data_feed"
    INTERNAL_ANALYST = "internal_analyst"
    MANUAL_UPLOAD = "manual_upload"


class DocumentKind(StrEnum):
    """Canonical document categories."""

    DOCUMENT = "document"
    FILING = "filing"
    EARNINGS_CALL = "earnings_call"
    NEWS_ITEM = "news_item"


class DocumentStatus(StrEnum):
    """Document lifecycle status."""

    RECEIVED = "received"
    NORMALIZED = "normalized"
    PARSED = "parsed"
    REJECTED = "rejected"


class FilingForm(StrEnum):
    """Common filing form types."""

    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    FORM_20F = "20-F"
    FORM_6K = "6-K"
    FORM_S1 = "S-1"
    OTHER = "other"


class MarketEventType(StrEnum):
    """Canonical market or corporate event types."""

    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    M_AND_A = "m_and_a"
    PRODUCT = "product"
    REGULATORY = "regulatory"
    MANAGEMENT_CHANGE = "management_change"
    MACRO = "macro"


class HypothesisStatus(StrEnum):
    """Lifecycle for a research hypothesis."""

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    PROMOTED_TO_SIGNAL = "promoted_to_signal"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class FeatureStatus(StrEnum):
    """Lifecycle for a computed feature."""

    PROVISIONAL = "provisional"
    COMPUTED = "computed"
    STALE = "stale"
    INVALIDATED = "invalidated"


class SignalStatus(StrEnum):
    """Lifecycle for a signal."""

    CANDIDATE = "candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(StrEnum):
    """Direction of an expressed view."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class PositionIdeaStatus(StrEnum):
    """Lifecycle for a position idea."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED_FOR_PORTFOLIO = "approved_for_portfolio"
    REJECTED = "rejected"


class ConstraintType(StrEnum):
    """Portfolio constraint categories."""

    GROSS_EXPOSURE = "gross_exposure"
    NET_EXPOSURE = "net_exposure"
    SINGLE_NAME = "single_name"
    SECTOR = "sector"
    LIQUIDITY = "liquidity"
    TURNOVER = "turnover"
    BETA = "beta"


class RiskCheckStatus(StrEnum):
    """Risk check outcomes."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class Severity(StrEnum):
    """Severity level for alerts or check results."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PortfolioProposalStatus(StrEnum):
    """Lifecycle for a portfolio proposal."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class BacktestStatus(StrEnum):
    """Lifecycle for a backtest run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExperimentStatus(StrEnum):
    """Lifecycle for experiments and research programs."""

    DESIGN = "design"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class MemoStatus(StrEnum):
    """Lifecycle for research memos."""

    DRAFT = "draft"
    REVIEW = "review"
    FINAL = "final"


class AgentRunStatus(StrEnum):
    """Lifecycle for an agent run."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ESCALATED = "escalated"


class ReviewOutcome(StrEnum):
    """Human review outcomes."""

    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_REVISION = "needs_revision"
    ESCALATE = "escalate"


class PaperTradeStatus(StrEnum):
    """Lifecycle for simulated paper trades."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    SIMULATED = "simulated"
    CANCELLED = "cancelled"


class AuditOutcome(StrEnum):
    """Outcome of an auditable action."""

    SUCCESS = "success"
    WARNING = "warning"
    FAILURE = "failure"


class ConfidenceAssessment(StrictModel):
    """Confidence and uncertainty metadata for AI or statistical outputs."""

    confidence: float = Field(ge=0.0, le=1.0, description="Normalized confidence score.")
    uncertainty: float = Field(ge=0.0, le=1.0, description="Normalized uncertainty score.")
    method: str | None = Field(
        default=None,
        description="Method used to estimate confidence and uncertainty.",
    )
    rationale: str | None = Field(
        default=None,
        description="Short explanation of what drives the assessment.",
    )


class ProvenanceRecord(StrictModel):
    """Traceability metadata for artifacts and derived outputs."""

    source_reference_ids: list[str] = Field(
        default_factory=list,
        description="Direct source reference identifiers that support this entity.",
    )
    upstream_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifact identifiers used to derive this entity.",
    )
    data_snapshot_id: str | None = Field(
        default=None,
        description="Snapshot identifier capturing point-in-time data availability.",
    )
    transformation_name: str | None = Field(
        default=None,
        description="Name of the transformation or workflow that produced this entity.",
    )
    transformation_version: str | None = Field(
        default=None,
        description="Version string for the producing workflow or transformation.",
    )
    config_version: str | None = Field(
        default=None,
        description="Configuration or registry version that influenced generation.",
    )
    code_version: str | None = Field(
        default=None,
        description="Git SHA or release version used for generation.",
    )
    workflow_run_id: str | None = Field(
        default=None,
        description="Workflow or orchestration run identifier when available.",
    )
    agent_run_id: str | None = Field(
        default=None,
        description="Agent run identifier when the artifact came from an agent.",
    )
    experiment_id: str | None = Field(
        default=None,
        description="Experiment identifier associated with the artifact.",
    )
    model_name: str | None = Field(
        default=None,
        description="Model used for generation when AI-assisted output is involved.",
    )
    prompt_version: str | None = Field(
        default=None,
        description="Prompt or policy version used for AI-assisted generation.",
    )
    ingestion_time: datetime | None = Field(
        default=None,
        description="UTC timestamp when upstream data was first ingested.",
    )
    processing_time: datetime | None = Field(
        default=None,
        description="UTC timestamp when the current artifact was produced.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Free-form traceability notes or known caveats.",
    )
