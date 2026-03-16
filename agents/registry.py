from __future__ import annotations

from agents.counterargument_agent import DESCRIPTOR as COUNTERARGUMENT_AGENT
from agents.filing_ingestion_agent import DESCRIPTOR as FILING_INGESTION_AGENT
from agents.hypothesis_agent import DESCRIPTOR as HYPOTHESIS_AGENT
from agents.memo_writer_agent import DESCRIPTOR as MEMO_WRITER_AGENT
from agents.news_agent import DESCRIPTOR as NEWS_AGENT
from agents.portfolio_agent import DESCRIPTOR as PORTFOLIO_AGENT
from agents.risk_reviewer_agent import DESCRIPTOR as RISK_REVIEWER_AGENT
from agents.signal_builder_agent import DESCRIPTOR as SIGNAL_BUILDER_AGENT
from agents.transcript_agent import DESCRIPTOR as TRANSCRIPT_AGENT
from libraries.core.agent_framework import AgentDescriptor


def list_agent_descriptors() -> list[AgentDescriptor]:
    """Return the Day 1 agent roster."""

    return [
        FILING_INGESTION_AGENT,
        TRANSCRIPT_AGENT,
        NEWS_AGENT,
        HYPOTHESIS_AGENT,
        COUNTERARGUMENT_AGENT,
        SIGNAL_BUILDER_AGENT,
        RISK_REVIEWER_AGENT,
        PORTFOLIO_AGENT,
        MEMO_WRITER_AGENT,
    ]
