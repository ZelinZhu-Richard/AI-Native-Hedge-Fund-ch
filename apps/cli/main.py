from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from apps.api.builders import (
    build_capability_descriptors,
    build_daily_workflow_result,
    build_demo_run_result,
    build_service_manifest,
)
from apps.api.state import api_clock, service_registry
from libraries.schemas import DataRefreshMode
from libraries.schemas.research import AblationView
from libraries.time import parse_datetime_value
from pipelines.daily_operations import DEFAULT_DAILY_ARTIFACT_ROOT, run_daily_workflow
from pipelines.demo import run_end_to_end_demo
from services.monitoring import ListRecentRunSummariesRequest, MonitoringService
from services.operator_review import ListReviewQueueRequest, OperatorReviewService


def main(argv: Sequence[str] | None = None) -> int:
    """Run the unified local CLI."""

    parser = argparse.ArgumentParser(prog="anhf", description="ANHF local interface CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("manifest", help="Show the local interface manifest.")
    manifest_parser.add_argument("--json", action="store_true")

    capabilities_parser = subparsers.add_parser(
        "capabilities",
        help="List normalized services, agents, and workflow capabilities.",
    )
    capabilities_parser.add_argument("--json", action="store_true")

    demo_parser = subparsers.add_parser("demo", help="Run the end-to-end local demo.")
    demo_subparsers = demo_parser.add_subparsers(dest="demo_command", required=True)
    demo_run_parser = demo_subparsers.add_parser("run", help="Run the end-to-end local demo.")
    demo_run_parser.add_argument("--fixtures-root", type=Path, default=None)
    demo_run_parser.add_argument("--price-fixture-path", type=Path, default=None)
    demo_run_parser.add_argument("--base-root", type=Path, default=None)
    demo_run_parser.add_argument("--requested-by", default="cli_demo_run")
    demo_run_parser.add_argument("--frozen-time", default=None)
    demo_run_parser.add_argument("--json", action="store_true")

    daily_parser = subparsers.add_parser("daily", help="Run the local daily workflow.")
    daily_subparsers = daily_parser.add_subparsers(dest="daily_command", required=True)
    daily_run_parser = daily_subparsers.add_parser("run", help="Run the local daily workflow.")
    daily_run_parser.add_argument("--artifact-root", type=Path, default=DEFAULT_DAILY_ARTIFACT_ROOT)
    daily_run_parser.add_argument("--fixtures-root", type=Path, default=None)
    daily_run_parser.add_argument(
        "--data-refresh-mode",
        choices=[mode.value for mode in DataRefreshMode],
        default=DataRefreshMode.FIXTURE_REFRESH.value,
    )
    daily_run_parser.add_argument("--company-id", default=None)
    daily_run_parser.add_argument("--as-of-time", default=None)
    daily_run_parser.add_argument("--requested-by", default="cli_daily_run")
    daily_run_parser.add_argument(
        "--ablation-view",
        choices=[view.value for view in AblationView],
        default=AblationView.TEXT_ONLY.value,
    )
    daily_run_parser.add_argument(
        "--assumed-reference-price",
        action="append",
        default=[],
        help="Repeatable SYMBOL=PRICE mapping used for paper-trade candidate sizing.",
    )
    daily_run_parser.add_argument("--no-generate-memo-skeleton", action="store_true")
    daily_run_parser.add_argument("--no-retrieval-context", action="store_true")
    daily_run_parser.add_argument("--json", action="store_true")

    review_parser = subparsers.add_parser("review", help="Inspect the review queue.")
    review_subparsers = review_parser.add_subparsers(dest="review_command", required=True)
    review_queue_parser = review_subparsers.add_parser("queue", help="Show the current review queue.")
    review_queue_parser.add_argument("--json", action="store_true")

    monitoring_parser = subparsers.add_parser(
        "monitoring",
        help="Inspect monitoring summaries.",
    )
    monitoring_subparsers = monitoring_parser.add_subparsers(
        dest="monitoring_command",
        required=True,
    )
    recent_runs_parser = monitoring_subparsers.add_parser(
        "recent-runs",
        help="Show recent monitoring run summaries.",
    )
    recent_runs_parser.add_argument("--service-name", default=None)
    recent_runs_parser.add_argument("--workflow-name", default=None)
    recent_runs_parser.add_argument("--limit", type=int, default=20)
    recent_runs_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "manifest":
        return _run_manifest(json_output=args.json)
    if args.command == "capabilities":
        return _run_capabilities(json_output=args.json)
    if args.command == "demo" and args.demo_command == "run":
        return _run_demo(args=args)
    if args.command == "daily" and args.daily_command == "run":
        return _run_daily(args=args)
    if args.command == "review" and args.review_command == "queue":
        return _run_review_queue(json_output=args.json)
    if args.command == "monitoring" and args.monitoring_command == "recent-runs":
        return _run_recent_runs(args=args)
    raise ValueError(f"Unsupported CLI command selection: {args.command}")


def _run_manifest(*, json_output: bool) -> int:
    manifest = build_service_manifest(
        generated_at=api_clock.now(),
        service_capabilities=[service.capability() for service in service_registry.values()],
    )
    if json_output:
        print(manifest.model_dump_json(indent=2))
    else:
        print(f"project_name={manifest.project_name}")
        print(f"environment={manifest.environment}")
        print(f"artifact_root={manifest.artifact_root}")
        print(f"capability_count={len(manifest.capabilities)}")
    return 0


def _run_capabilities(*, json_output: bool) -> int:
    descriptors = build_capability_descriptors(
        service_capabilities=[service.capability() for service in service_registry.values()]
    )
    if json_output:
        print(
            json.dumps(
                {
                "items": [descriptor.model_dump(mode="json") for descriptor in descriptors],
                "total": len(descriptors),
                },
                indent=2,
            )
        )
    else:
        for descriptor in descriptors:
            print(f"{descriptor.kind}:{descriptor.name} - {descriptor.description}")
    return 0


def _run_demo(*, args: argparse.Namespace) -> int:
    response = run_end_to_end_demo(
        fixtures_root=args.fixtures_root,
        price_fixture_path=args.price_fixture_path,
        base_root=args.base_root,
        requested_by=args.requested_by,
        frozen_time=(
            parse_datetime_value(args.frozen_time) if args.frozen_time is not None else None
        ),
    )
    result = build_demo_run_result(response=response, invocation_kind="cli")
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"demo_run_id={result.demo_run_id}")
        print(f"status={result.status.value}")
        print(f"manifest_path={result.manifest_path}")
        print(f"base_root={result.artifact_root}")
        print(f"company_id={result.company_id}")
    return 0


def _run_daily(*, args: argparse.Namespace) -> int:
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
    result = build_daily_workflow_result(response=response, invocation_kind="cli")
    if args.json:
        print(result.model_dump_json(indent=2))
    else:
        print(f"workflow_run_id={result.workflow_run_id}")
        print(f"status={result.status.value}")
        print(f"artifact_root={result.artifact_root}")
    return 0


def _run_review_queue(*, json_output: bool) -> int:
    service = service_registry["operator_review"]
    assert isinstance(service, OperatorReviewService)
    response = service.list_review_queue(ListReviewQueueRequest())
    if json_output:
        print(response.model_dump_json(indent=2))
    else:
        print(f"total={response.total}")
        for item in response.items[:10]:
            print(f"{item.target_type.value}:{item.target_id} [{item.queue_status.value}] {item.title}")
    return 0


def _run_recent_runs(*, args: argparse.Namespace) -> int:
    service = service_registry["monitoring"]
    assert isinstance(service, MonitoringService)
    response = service.list_recent_run_summaries(
        ListRecentRunSummariesRequest(
            service_name=args.service_name,
            workflow_name=args.workflow_name,
            limit=args.limit,
        )
    )
    if args.json:
        print(response.model_dump_json(indent=2))
    else:
        print(f"total={response.total}")
        for item in response.items[:10]:
            print(f"{item.workflow_name}:{item.workflow_run_id} [{item.status.value}]")
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
