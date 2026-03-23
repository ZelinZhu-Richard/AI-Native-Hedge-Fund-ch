from __future__ import annotations

from libraries.core.service_framework import BaseService
from libraries.time import Clock
from services.audit import AuditLoggingService
from services.backtest_reconciliation import BacktestReconciliationService
from services.backtesting import BacktestingService
from services.daily_orchestration import DailyOrchestrationService
from services.data_quality import DataQualityService
from services.entity_resolution import EntityResolutionService
from services.evaluation import EvaluationService
from services.experiment_registry import ExperimentRegistryService
from services.feature_store import FeatureStoreService
from services.ingestion import IngestionService
from services.memo import MemoGenerationService
from services.monitoring import MonitoringService
from services.operator_review import OperatorReviewService
from services.paper_execution import PaperExecutionService
from services.parsing import ParsingService
from services.portfolio import PortfolioConstructionService
from services.portfolio_analysis import PortfolioAnalysisService
from services.red_team import RedTeamService
from services.research_memory import ResearchMemoryService
from services.research_orchestrator import ResearchOrchestrationService
from services.risk_engine import RiskEngineService
from services.signal_arbitration import SignalArbitrationService
from services.signal_generation import SignalGenerationService
from services.timing import TimingService


def build_service_registry(clock: Clock | None = None) -> dict[str, BaseService]:
    """Instantiate the current local service registry."""

    services: list[BaseService] = [
        IngestionService(clock=clock),
        DataQualityService(clock=clock),
        ParsingService(clock=clock),
        ResearchOrchestrationService(clock=clock),
        ResearchMemoryService(clock=clock),
        FeatureStoreService(clock=clock),
        SignalGenerationService(clock=clock),
        SignalArbitrationService(clock=clock),
        BacktestingService(clock=clock),
        BacktestReconciliationService(clock=clock),
        EntityResolutionService(clock=clock),
        EvaluationService(clock=clock),
        ExperimentRegistryService(clock=clock),
        RiskEngineService(clock=clock),
        PortfolioConstructionService(clock=clock),
        PortfolioAnalysisService(clock=clock),
        PaperExecutionService(clock=clock),
        OperatorReviewService(clock=clock),
        MemoGenerationService(clock=clock),
        AuditLoggingService(clock=clock),
        MonitoringService(clock=clock),
        RedTeamService(clock=clock),
        TimingService(clock=clock),
        DailyOrchestrationService(clock=clock),
    ]
    return {service.capability_name: service for service in services}
