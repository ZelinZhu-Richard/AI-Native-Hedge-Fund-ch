from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    ComparisonSummary,
    CoverageSummary,
    EvaluationDimension,
    EvaluationReport,
    EvaluationStatus,
    MetricValue,
    ProvenanceRecord,
)

FIXED_NOW = datetime(2026, 3, 18, 10, 0, tzinfo=UTC)


def test_metric_value_requires_exactly_one_representation() -> None:
    with pytest.raises(ValidationError):
        MetricValue(
            metric_value_id="mval_test",
            numeric_value=1.0,
            boolean_value=True,
            text_value=None,
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_comparison_summary_requires_ordered_variants() -> None:
    with pytest.raises(ValidationError):
        ComparisonSummary(
            comparison_summary_id="cmpsum_test",
            evaluation_report_id="evrep_test",
            target_id="abres_test",
            comparison_metric_name="net_pnl",
            expected_family_count=4,
            observed_family_count=4,
            ordered_strategy_variant_ids=[],
            mechanical_order_only=True,
            notes=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_coverage_summary_requires_consistent_counts_and_ratio() -> None:
    with pytest.raises(ValidationError):
        CoverageSummary(
            coverage_summary_id="covsum_test",
            evaluation_report_id="evrep_test",
            dimension=EvaluationDimension.PROVENANCE_COMPLETENESS,
            target_type="signal_slice",
            target_id="sig_slice_test",
            covered_count=1,
            missing_count=1,
            total_count=3,
            coverage_ratio=0.5,
            notes=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_evaluation_report_requires_structured_outputs() -> None:
    with pytest.raises(ValidationError):
        EvaluationReport(
            evaluation_report_id="evrep_test",
            target_type="ablation_result",
            target_id="abres_test",
            generated_at=FIXED_NOW,
            overall_status=EvaluationStatus.NOT_EVALUATED,
            metric_ids=[],
            failure_case_ids=[],
            robustness_check_ids=[],
            comparison_summary_id=None,
            coverage_summary_ids=[],
            notes=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
