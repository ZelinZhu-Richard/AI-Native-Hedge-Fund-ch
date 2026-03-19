from __future__ import annotations

from libraries.core.service_framework import BaseService
from libraries.time import Clock
from services.audit import AuditLoggingService
from services.backtesting import BacktestingService
from services.evaluation import EvaluationService
from services.experiment_registry import ExperimentRegistryService
from services.feature_store import FeatureStoreService
from services.ingestion import IngestionService
from services.memo import MemoGenerationService
from services.paper_execution import PaperExecutionService
from services.parsing import ParsingService
from services.portfolio import PortfolioConstructionService
from services.research_orchestrator import ResearchOrchestrationService
from services.risk_engine import RiskEngineService
from services.signal_generation import SignalGenerationService


def build_service_registry(clock: Clock | None = None) -> dict[str, BaseService]:
    """Instantiate the Day 1 default service registry."""

    services: list[BaseService] = [
        IngestionService(clock=clock),
        ParsingService(clock=clock),
        ResearchOrchestrationService(clock=clock),
        FeatureStoreService(clock=clock),
        SignalGenerationService(clock=clock),
        BacktestingService(clock=clock),
        EvaluationService(clock=clock),
        ExperimentRegistryService(clock=clock),
        RiskEngineService(clock=clock),
        PortfolioConstructionService(clock=clock),
        PaperExecutionService(clock=clock),
        MemoGenerationService(clock=clock),
        AuditLoggingService(clock=clock),
    ]
    return {service.capability_name: service for service in services}
