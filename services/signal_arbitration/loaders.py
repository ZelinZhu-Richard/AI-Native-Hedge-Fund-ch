from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.schemas import (
    ArbitrationDecision,
    EvidenceAssessment,
    ResearchBrief,
    Signal,
    SignalBundle,
    StrictModel,
)
from libraries.schemas.base import TimestampedModel
from services.signal_arbitration.storage import load_models

TArtifact = TypeVar("TArtifact", bound=TimestampedModel)


class LoadedSignalArbitrationInputs(StrictModel):
    """Typed bundle of persisted artifacts used for deterministic signal arbitration."""

    company_id: str = Field(description="Covered company identifier.")
    signals: list[Signal] = Field(
        default_factory=list,
        description="Same-company signal artifacts visible to arbitration.",
    )
    evidence_assessments_by_hypothesis_id: dict[str, EvidenceAssessment] = Field(
        default_factory=dict,
        description="Evidence assessments keyed by hypothesis identifier when available.",
    )
    research_briefs_by_hypothesis_id: dict[str, ResearchBrief] = Field(
        default_factory=dict,
        description="Research briefs keyed by hypothesis identifier when available.",
    )


def load_signal_arbitration_inputs(
    *,
    signal_root: Path,
    research_root: Path,
    company_id: str | None = None,
    as_of_time: datetime | None = None,
) -> LoadedSignalArbitrationInputs:
    """Load same-company signals plus research support context for arbitration."""

    signals = _apply_signal_cutoff(
        load_models(root=signal_root, category="signals", model_cls=Signal),
        as_of_time=as_of_time,
    )
    if company_id is None:
        available_company_ids = sorted({signal.company_id for signal in signals})
        if len(available_company_ids) != 1:
            raise ValueError(
                "Signal arbitration requires an explicit company_id when the signal root contains zero or multiple companies."
            )
        resolved_company_id = available_company_ids[0]
    else:
        resolved_company_id = company_id

    company_signals = [signal for signal in signals if signal.company_id == resolved_company_id]
    evidence_assessments = [
        assessment
        for assessment in _apply_created_at_cutoff(
            load_models(
                root=research_root,
                category="evidence_assessments",
                model_cls=EvidenceAssessment,
            ),
            as_of_time=as_of_time,
        )
        if assessment.company_id == resolved_company_id and assessment.hypothesis_id is not None
    ]
    research_briefs = [
        brief
        for brief in _apply_created_at_cutoff(
            load_models(root=research_root, category="research_briefs", model_cls=ResearchBrief),
            as_of_time=as_of_time,
        )
        if brief.company_id == resolved_company_id and brief.hypothesis_id is not None
    ]
    evidence_assessments_by_hypothesis_id: dict[str, EvidenceAssessment] = {}
    for assessment in evidence_assessments:
        hypothesis_id = assessment.hypothesis_id
        if hypothesis_id is not None:
            evidence_assessments_by_hypothesis_id[hypothesis_id] = assessment
    research_briefs_by_hypothesis_id: dict[str, ResearchBrief] = {}
    for brief in research_briefs:
        hypothesis_id = brief.hypothesis_id
        if hypothesis_id is not None:
            research_briefs_by_hypothesis_id[hypothesis_id] = brief
    return LoadedSignalArbitrationInputs(
        company_id=resolved_company_id,
        signals=sorted(
            company_signals,
            key=lambda signal: (signal.effective_at, signal.signal_id),
            reverse=True,
        ),
        evidence_assessments_by_hypothesis_id=evidence_assessments_by_hypothesis_id,
        research_briefs_by_hypothesis_id=research_briefs_by_hypothesis_id,
    )


def load_latest_signal_bundle(
    *,
    signal_arbitration_root: Path,
    company_id: str,
    as_of_time: datetime | None = None,
) -> tuple[SignalBundle | None, ArbitrationDecision | None]:
    """Load the latest eligible signal bundle and its decision for one company."""

    bundles = [
        bundle
        for bundle in load_models(
            root=signal_arbitration_root,
            category="signal_bundles",
            model_cls=SignalBundle,
        )
        if bundle.company_id == company_id
        and (as_of_time is None or bundle.created_at <= as_of_time)
        and (bundle.as_of_time is None or as_of_time is None or bundle.as_of_time <= as_of_time)
    ]
    if not bundles:
        return None, None
    bundle = max(
        bundles,
        key=lambda candidate: (
            candidate.as_of_time or candidate.created_at,
            candidate.created_at,
            candidate.signal_bundle_id,
        ),
    )
    decisions = {
        decision.arbitration_decision_id: decision
        for decision in load_models(
            root=signal_arbitration_root,
            category="arbitration_decisions",
            model_cls=ArbitrationDecision,
        )
    }
    return bundle, decisions.get(bundle.arbitration_decision_id)


def _apply_created_at_cutoff(
    artifacts: list[TArtifact],
    *,
    as_of_time: datetime | None,
) -> list[TArtifact]:
    """Apply an optional creation-time cutoff to persisted artifacts."""

    if as_of_time is None:
        return artifacts
    return [artifact for artifact in artifacts if artifact.created_at <= as_of_time]


def _apply_signal_cutoff(
    signals: list[Signal],
    *,
    as_of_time: datetime | None,
) -> list[Signal]:
    """Apply an optional point-in-time cutoff to persisted signals."""

    if as_of_time is None:
        return signals
    return [
        signal
        for signal in signals
        if signal.created_at <= as_of_time and signal.effective_at <= as_of_time
    ]
