from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from libraries.config import get_settings
from libraries.schemas import AblationView, DataRefreshMode
from libraries.time import Clock, SystemClock, parse_datetime_value
from services.daily_orchestration import (
    DailyOrchestrationService,
    RunDailyWorkflowRequest,
    RunDailyWorkflowResponse,
)

DEFAULT_DAILY_ARTIFACT_ROOT = get_settings().resolved_artifact_root / "daily_runs" / "latest"


def run_daily_workflow(
    *,
    artifact_root: Path | None = None,
    fixtures_root: Path | None = None,
    data_refresh_mode: DataRefreshMode = DataRefreshMode.FIXTURE_REFRESH,
    company_id: str | None = None,
    as_of_time: datetime | None = None,
    generate_memo_skeleton: bool = True,
    include_retrieval_context: bool = True,
    ablation_view: AblationView = AblationView.TEXT_ONLY,
    assumed_reference_prices: dict[str, float] | None = None,
    requested_by: str = "pipeline_daily_workflow",
    clock: Clock | None = None,
) -> RunDailyWorkflowResponse:
    """Run the local deterministic daily operating workflow."""

    service = DailyOrchestrationService(clock=clock or SystemClock())
    return service.run_daily_workflow(
        RunDailyWorkflowRequest(
            artifact_root=artifact_root or DEFAULT_DAILY_ARTIFACT_ROOT,
            fixtures_root=fixtures_root,
            data_refresh_mode=data_refresh_mode,
            company_id=company_id,
            as_of_time=as_of_time,
            generate_memo_skeleton=generate_memo_skeleton,
            include_retrieval_context=include_retrieval_context,
            ablation_view=ablation_view,
            assumed_reference_prices=assumed_reference_prices or {},
            requested_by=requested_by,
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the daily workflow as a small local CLI."""

    parser = argparse.ArgumentParser(description="Run the Nexus Tensor Alpha local daily workflow.")
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_DAILY_ARTIFACT_ROOT)
    parser.add_argument("--fixtures-root", type=Path, default=None)
    parser.add_argument(
        "--data-refresh-mode",
        choices=[mode.value for mode in DataRefreshMode],
        default=DataRefreshMode.FIXTURE_REFRESH.value,
    )
    parser.add_argument("--company-id", default=None)
    parser.add_argument(
        "--as-of-time",
        default=None,
        help="Timezone-aware ISO-8601 timestamp used as the point-in-time boundary.",
    )
    parser.add_argument("--requested-by", default="daily_workflow_cli")
    parser.add_argument(
        "--ablation-view",
        choices=[view.value for view in AblationView],
        default=AblationView.TEXT_ONLY.value,
    )
    parser.add_argument(
        "--assumed-reference-price",
        action="append",
        default=[],
        help="Repeatable SYMBOL=PRICE mapping used for paper-trade candidate sizing.",
    )
    parser.add_argument(
        "--no-generate-memo-skeleton",
        action="store_true",
        help="Disable memo-skeleton generation in the research workflow.",
    )
    parser.add_argument(
        "--no-retrieval-context",
        action="store_true",
        help="Disable advisory research-memory retrieval in the research workflow.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    response = run_daily_workflow(
        artifact_root=args.artifact_root,
        fixtures_root=args.fixtures_root,
        data_refresh_mode=DataRefreshMode(args.data_refresh_mode),
        company_id=args.company_id,
        as_of_time=parse_datetime_value(args.as_of_time) if args.as_of_time else None,
        generate_memo_skeleton=not args.no_generate_memo_skeleton,
        include_retrieval_context=not args.no_retrieval_context,
        ablation_view=AblationView(args.ablation_view),
        assumed_reference_prices=_parse_reference_prices(args.assumed_reference_price),
        requested_by=args.requested_by,
    )
    print(f"workflow_execution_id={response.workflow_execution.workflow_execution_id}")
    print(f"workflow_status={response.workflow_execution.status.value}")
    print(f"artifact_root={args.artifact_root}")
    print(f"orchestration_root={args.artifact_root / 'orchestration'}")
    return 0


def _parse_reference_prices(values: Sequence[str]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(
                "assumed reference prices must use SYMBOL=PRICE format, for example APEX=102.0"
            )
        symbol, price_text = value.split("=", 1)
        symbol = symbol.strip().upper()
        price = float(price_text)
        if not symbol:
            raise ValueError("assumed reference price symbols must be non-empty.")
        if price <= 0.0:
            raise ValueError("assumed reference price values must be positive.")
        prices[symbol] = price
    return prices


if __name__ == "__main__":
    raise SystemExit(main())
