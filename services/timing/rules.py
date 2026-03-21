from __future__ import annotations

from libraries.schemas.timing import (
    DataAvailabilityRule,
    DataAvailabilityTarget,
    MarketName,
    SameDayAvailabilityPolicy,
)

US_EQUITIES_TIMEZONE = "America/New_York"


def public_document_daily_equity_rule() -> DataAvailabilityRule:
    """Return the conservative daily document-availability rule."""

    return DataAvailabilityRule(
        rule_name="public_document_daily_equity",
        applies_to=DataAvailabilityTarget.DOCUMENT,
        market=MarketName.US_EQUITIES,
        timezone=US_EQUITIES_TIMEZONE,
        requires_publication_time=True,
        same_day_policy=SameDayAvailabilityPolicy.PRE_OPEN_SAME_DAY_ELSE_NEXT_SESSION,
        delay_minutes=0,
        buffer_minutes=0,
        notes=[
            "Documents first visible before the regular market open may influence that trading day's close decision.",
            "Documents first visible during regular trading or after-hours are delayed until the next market open.",
        ],
    )


def derived_feature_from_inputs_rule() -> DataAvailabilityRule:
    """Return the rule used to materialize feature availability."""

    return DataAvailabilityRule(
        rule_name="derived_feature_from_inputs",
        applies_to=DataAvailabilityTarget.FEATURE,
        market=MarketName.US_EQUITIES,
        timezone="UTC",
        requires_publication_time=False,
        same_day_policy=SameDayAvailabilityPolicy.MAX_INPUT_AVAILABILITY,
        delay_minutes=0,
        buffer_minutes=0,
        notes=["Feature availability is the maximum availability across the upstream inputs."],
    )


def derived_signal_from_features_rule() -> DataAvailabilityRule:
    """Return the rule used to materialize signal availability."""

    return DataAvailabilityRule(
        rule_name="derived_signal_from_features",
        applies_to=DataAvailabilityTarget.SIGNAL,
        market=MarketName.US_EQUITIES,
        timezone="UTC",
        requires_publication_time=False,
        same_day_policy=SameDayAvailabilityPolicy.MAX_INPUT_AVAILABILITY,
        delay_minutes=0,
        buffer_minutes=0,
        notes=["Signal availability is the maximum availability across contributing features."],
    )


def daily_price_bar_close_rule() -> DataAvailabilityRule:
    """Return the rule used to treat daily price bars as decision-ready."""

    return DataAvailabilityRule(
        rule_name="daily_price_bar_close",
        applies_to=DataAvailabilityTarget.PRICE_BAR,
        market=MarketName.US_EQUITIES,
        timezone=US_EQUITIES_TIMEZONE,
        requires_publication_time=False,
        same_day_policy=SameDayAvailabilityPolicy.BAR_CLOSE,
        delay_minutes=0,
        buffer_minutes=0,
        notes=["Synthetic daily price bars become usable at the recorded bar close time."],
    )


TIMING_RULES = {
    "public_document_daily_equity": public_document_daily_equity_rule,
    "derived_feature_from_inputs": derived_feature_from_inputs_rule,
    "derived_signal_from_features": derived_signal_from_features_rule,
    "daily_price_bar_close": daily_price_bar_close_rule,
}


__all__ = [
    "TIMING_RULES",
    "US_EQUITIES_TIMEZONE",
    "daily_price_bar_close_rule",
    "derived_feature_from_inputs_rule",
    "derived_signal_from_features_rule",
    "public_document_daily_equity_rule",
]
