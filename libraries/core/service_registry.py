from __future__ import annotations

from libraries.core.service_framework import BaseService
from services.audit import AuditLoggingService
from services.backtesting import BacktestingService
from services.feature_store import FeatureStoreService
from services.ingestion import IngestionService
from services.memo import MemoGenerationService
from services.paper_execution import PaperExecutionService
from services.parsing import ParsingService
from services.portfolio import PortfolioConstructionService
from services.research_orchestrator import ResearchOrchestrationService
from services.risk_engine import RiskEngineService
from services.signal_generation import SignalGenerationService


def build_service_registry() -> dict[str, BaseService]:
    """Instantiate the Day 1 default service registry."""

    services: list[BaseService] = [
        IngestionService(),
        ParsingService(),
        ResearchOrchestrationService(),
        FeatureStoreService(),
        SignalGenerationService(),
        BacktestingService(),
        RiskEngineService(),
        PortfolioConstructionService(),
        PaperExecutionService(),
        MemoGenerationService(),
        AuditLoggingService(),
    ]
    return {service.capability_name: service for service in services}
