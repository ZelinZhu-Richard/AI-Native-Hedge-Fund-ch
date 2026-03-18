from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TypeVar, cast

from pydantic import Field, model_validator

from libraries.schemas import Feature, Signal, StrategyVariantSignal, StrictModel
from libraries.time import parse_datetime_value
from libraries.time.clock import ensure_utc

T = TypeVar("T", bound=StrictModel)


class SyntheticDailyPriceBar(StrictModel):
    """One synthetic daily bar used by the Day 6 simulation skeleton."""

    timestamp: str = Field(description="ISO timestamp representing the daily decision bar close.")
    open: float = Field(gt=0.0, description="Synthetic open price for the bar.")
    close: float = Field(gt=0.0, description="Synthetic close price for the bar.")

    @property
    def timestamp_dt(self) -> datetime:
        """Return the parsed timezone-aware bar timestamp."""

        return parse_datetime_value(self.timestamp)


class SyntheticPriceFixture(StrictModel):
    """Synthetic test-only daily price path for mechanical backtest validation."""

    fixture_name: str = Field(description="Human-readable fixture name.")
    description: str = Field(description="Description explaining the fixture purpose.")
    symbol: str = Field(description="Synthetic symbol used by the fixture.")
    company_id: str | None = Field(
        default=None,
        description="Optional covered company identifier when the fixture is company-specific.",
    )
    bars: list[SyntheticDailyPriceBar] = Field(
        default_factory=list,
        description="Synthetic daily bars sorted by timestamp.",
    )

    @model_validator(mode="after")
    def validate_bars(self) -> SyntheticPriceFixture:
        """Require at least two strictly ordered bars."""

        if len(self.bars) < 2:
            raise ValueError("Synthetic price fixtures require at least two daily bars.")
        timestamps = [bar.timestamp_dt for bar in self.bars]
        if timestamps != sorted(timestamps):
            raise ValueError("Synthetic price bars must be sorted by timestamp.")
        if len(set(timestamps)) != len(timestamps):
            raise ValueError("Synthetic price bars must not reuse timestamps.")
        return self


class LoadedBacktestInputs(StrictModel):
    """Typed bundle of signals, features, and price bars for one company backtest."""

    company_id: str = Field(description="Covered company identifier.")
    signal_root: Path = Field(description="Root path containing persisted signal artifacts.")
    feature_root: Path = Field(description="Root path containing persisted feature artifacts.")
    price_fixture_path: Path = Field(description="Path to the synthetic price fixture.")
    signals: list[Signal | StrategyVariantSignal] = Field(
        default_factory=list,
        description="Persisted signals eligible for the run before temporal filtering.",
    )
    research_signals_by_id: dict[str, Signal] = Field(
        default_factory=dict,
        description="Research-signal artifacts keyed by signal ID for lineage revalidation.",
    )
    features_by_id: dict[str, Feature] = Field(
        default_factory=dict,
        description="Feature artifacts keyed by feature ID for lineage revalidation.",
    )
    price_fixture: SyntheticPriceFixture = Field(
        description="Synthetic price fixture used for the Day 6 simulation."
    )


def load_backtest_inputs(
    *,
    signal_root: Path,
    feature_root: Path,
    price_fixture_path: Path,
    company_id: str | None = None,
) -> LoadedBacktestInputs:
    """Load Day 5 signal and feature artifacts plus the synthetic price fixture."""

    signals = _load_models(signal_root / "signals", Signal)
    features = _load_models(feature_root / "features", Feature)
    resolved_company_id = _resolve_company_id(company_id=company_id, signals=signals)
    company_signals = [signal for signal in signals if signal.company_id == resolved_company_id]
    if not company_signals:
        raise ValueError(f"No signals were found for `{resolved_company_id}`.")

    feature_map = {
        feature.feature_id: feature
        for feature in features
        if feature.company_id == resolved_company_id
    }
    if not feature_map:
        raise ValueError(f"No features were found for `{resolved_company_id}`.")

    missing_feature_ids = sorted(
        {
            feature_id
            for signal in company_signals
            for feature_id in signal.feature_ids
            if feature_id not in feature_map
        }
    )
    if missing_feature_ids:
        raise ValueError(
            "Backtesting requires all referenced features to be present. Missing: "
            + ", ".join(missing_feature_ids)
        )

    price_fixture = SyntheticPriceFixture.model_validate(
        json.loads(price_fixture_path.read_text(encoding="utf-8"))
    )
    if price_fixture.company_id is not None and price_fixture.company_id != resolved_company_id:
        raise ValueError(
            f"Price fixture company `{price_fixture.company_id}` does not match `{resolved_company_id}`."
        )

    return LoadedBacktestInputs(
        company_id=resolved_company_id,
        signal_root=signal_root,
        feature_root=feature_root,
        price_fixture_path=price_fixture_path,
        signals=cast(list[Signal | StrategyVariantSignal], list(company_signals)),
        research_signals_by_id={signal.signal_id: signal for signal in company_signals},
        features_by_id=feature_map,
        price_fixture=price_fixture,
    )


def _resolve_company_id(*, company_id: str | None, signals: list[Signal]) -> str:
    """Resolve one company identifier from persisted signal artifacts."""

    available_company_ids = sorted({signal.company_id for signal in signals})
    if company_id is not None:
        if company_id not in available_company_ids:
            raise ValueError(f"Company `{company_id}` was not found under the signal root.")
        return company_id
    if len(available_company_ids) != 1:
        raise ValueError(
            "Backtesting requires an explicit company_id when signals contain zero or multiple companies."
        )
    return available_company_ids[0]


def bar_timestamp(bar: SyntheticDailyPriceBar) -> datetime:
    """Return one bar timestamp normalized to UTC."""

    return ensure_utc(bar.timestamp_dt)


def _load_models(directory: Path, model_cls: type[T]) -> list[T]:
    """Load JSON models from a category directory."""

    if not directory.exists():
        return []
    return [
        model_cls.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
