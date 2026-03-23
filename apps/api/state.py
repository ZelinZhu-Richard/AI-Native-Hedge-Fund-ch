from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol, TypeVar, cast

from libraries.config import get_settings
from libraries.core import load_local_models
from libraries.core.service_registry import build_service_registry
from libraries.schemas import StrictModel
from libraries.time import SystemClock

TModel = TypeVar("TModel", bound=StrictModel)


class _CreatedAtModel(Protocol):
    created_at: datetime

api_clock = SystemClock()
service_registry = build_service_registry(clock=api_clock)


def artifact_root() -> Path:
    """Resolve the current artifact root from runtime settings."""

    return get_settings().resolved_artifact_root


def load_persisted_models(directory: Path, model_cls: type[TModel]) -> list[TModel]:
    """Load persisted artifacts for API inspection surfaces."""

    models = load_local_models(directory, model_cls)
    return sorted(models, key=lambda model: _as_created_at_model(model).created_at, reverse=True)


def _as_created_at_model(model: TModel) -> _CreatedAtModel:
    return cast(_CreatedAtModel, model)
