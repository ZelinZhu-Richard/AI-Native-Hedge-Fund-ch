from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import pytest

from libraries.schemas import (
    CounterHypothesis,
    CritiqueKind,
    DataLayer,
    DocumentKind,
    DocumentStatus,
    EvidenceAssessment,
    EvidenceGrade,
    EvidenceLinkRole,
    EvidenceSpan,
    Experiment,
    ExperimentStatus,
    Filing,
    FilingForm,
    Hypothesis,
    HypothesisStatus,
    Memo,
    MemoryScope,
    MemoStatus,
    NewsItem,
    ResearchBrief,
    ResearchReviewStatus,
    ResearchStance,
    ResearchValidationStatus,
    RetrievalQuery,
    ReviewNote,
    ReviewTargetType,
    StrictModel,
    SupportingEvidenceLink,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.time import FrozenClock
from services.research_memory import ResearchMemoryService, SearchResearchMemoryRequest

FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


def test_research_memory_returns_real_artifact_references_and_evidence_citations(
    tmp_path: Path,
) -> None:
    workspace_root = _build_workspace(tmp_path / "artifacts")
    response = ResearchMemoryService(clock=FrozenClock(FIXED_NOW)).search_research_memory(
        SearchResearchMemoryRequest(
            workspace_root=workspace_root,
            query=RetrievalQuery(
                retrieval_query_id="rqry_evidence",
                scopes=[MemoryScope.EVIDENCE],
                company_id="co_apex",
                keyword_terms=["demand"],
                limit=10,
            ),
        )
    )

    assert len(response.retrieval_context.evidence_results) == 1
    evidence_result = response.retrieval_context.evidence_results[0]
    assert evidence_result.artifact_reference.artifact_type == "EvidenceSpan"
    assert _uri_exists(evidence_result.artifact_reference.storage_uri)
    assert evidence_result.artifact_reference.source_reference_ids == ["src_apex_news"]
    citing_types = {
        reference.artifact_type for reference in evidence_result.citing_artifact_references
    }
    assert {"Hypothesis", "CounterHypothesis", "ResearchBrief"} <= citing_types


def test_research_memory_filters_by_document_kind_and_time_window(tmp_path: Path) -> None:
    workspace_root = _build_workspace(tmp_path / "artifacts")
    response = ResearchMemoryService(clock=FrozenClock(FIXED_NOW)).search_research_memory(
        SearchResearchMemoryRequest(
            workspace_root=workspace_root,
            query=RetrievalQuery(
                retrieval_query_id="rqry_doc_kind",
                scopes=[MemoryScope.EVIDENCE, MemoryScope.HYPOTHESIS],
                document_kinds=[DocumentKind.NEWS_ITEM],
                time_end=FIXED_NOW + timedelta(hours=4, minutes=30),
                limit=20,
            ),
        )
    )

    assert response.retrieval_context.evidence_results
    assert response.retrieval_context.results
    assert all(
        result.artifact_reference.document_kind is DocumentKind.NEWS_ITEM
        for result in response.retrieval_context.results
    )
    assert all(
        result.document_kind is DocumentKind.NEWS_ITEM
        for result in response.retrieval_context.evidence_results
    )
    assert all(
        result.artifact_reference.artifact_id != "hyp_zeta"
        for result in response.retrieval_context.results
    )


def test_research_memory_filters_by_artifact_type_company_and_metadata(tmp_path: Path) -> None:
    workspace_root = _build_workspace(tmp_path / "artifacts")
    response = ResearchMemoryService(clock=FrozenClock(FIXED_NOW)).search_research_memory(
        SearchResearchMemoryRequest(
            workspace_root=workspace_root,
            query=RetrievalQuery(
                retrieval_query_id="rqry_memo",
                scopes=[MemoryScope.MEMO],
                company_id="co_apex",
                artifact_types=["Memo"],
                metadata_filters={"audience": "pm"},
                keyword_terms=["demand"],
                limit=10,
            ),
        )
    )

    assert [result.artifact_reference.artifact_type for result in response.retrieval_context.results] == [
        "Memo"
    ]
    memo_result = response.retrieval_context.results[0]
    assert memo_result.artifact_reference.company_id == "co_apex"
    assert _uri_exists(memo_result.artifact_reference.storage_uri)
    assert "executive_summary" in memo_result.matched_fields or "key_points" in memo_result.matched_fields


def test_research_memory_rejects_unsupported_metadata_filters_and_handles_empty_results(
    tmp_path: Path,
) -> None:
    workspace_root = _build_workspace(tmp_path / "artifacts")
    service = ResearchMemoryService(clock=FrozenClock(FIXED_NOW))

    with pytest.raises(ValueError, match="Unsupported metadata filter keys"):
        service.search_research_memory(
            SearchResearchMemoryRequest(
                workspace_root=workspace_root,
                query=RetrievalQuery(
                    retrieval_query_id="rqry_bad_filter",
                    scopes=[MemoryScope.HYPOTHESIS],
                    metadata_filters={"unknown_field": "x"},
                    limit=5,
                ),
            )
        )

    empty_response = service.search_research_memory(
        SearchResearchMemoryRequest(
            workspace_root=workspace_root,
            query=RetrievalQuery(
                retrieval_query_id="rqry_empty",
                scopes=[
                    MemoryScope.EVIDENCE,
                    MemoryScope.HYPOTHESIS,
                    MemoryScope.MEMO,
                    MemoryScope.EXPERIMENT,
                    MemoryScope.REVIEW_NOTE,
                ],
                company_id="co_missing",
                limit=10,
            ),
        )
    )

    assert empty_response.retrieval_context.results == []
    assert empty_response.retrieval_context.evidence_results == []
    assert "No matching artifacts were found." in empty_response.retrieval_context.notes


def _build_workspace(workspace_root: Path) -> Path:
    news_document = NewsItem(
        document_id="doc_apex_news",
        company_id="co_apex",
        title="Apex demand recovery article",
        source_reference_id="src_apex_news",
        external_id="news_apex_1",
        data_layer=DataLayer.NORMALIZED,
        language="en",
        storage_uri=None,
        content_hash=None,
        source_published_at=FIXED_NOW,
        effective_at=FIXED_NOW,
        publication_timing=None,
        ingested_at=FIXED_NOW + timedelta(minutes=5),
        processed_at=FIXED_NOW + timedelta(minutes=10),
        status=DocumentStatus.NORMALIZED,
        tags=["apex", "demand"],
        provenance=_provenance(["src_apex_news"], processing_time=FIXED_NOW + timedelta(minutes=10)),
        created_at=FIXED_NOW + timedelta(minutes=10),
        updated_at=FIXED_NOW + timedelta(minutes=10),
        publisher="Newswire",
        author_names=["Analyst"],
        headline="Apex sees demand recovery",
        summary="Management pointed to improving enterprise demand.",
        relevance_score=0.9,
        embargo_lifted_at=None,
    )
    filing_document = Filing(
        document_id="doc_zeta_filing",
        company_id="co_zeta",
        title="Zeta 8-K filing",
        source_reference_id="src_zeta_filing",
        external_id="filing_zeta_1",
        data_layer=DataLayer.NORMALIZED,
        language="en",
        storage_uri=None,
        content_hash=None,
        source_published_at=FIXED_NOW + timedelta(hours=8),
        effective_at=FIXED_NOW + timedelta(hours=8),
        publication_timing=None,
        ingested_at=FIXED_NOW + timedelta(hours=8, minutes=5),
        processed_at=FIXED_NOW + timedelta(hours=8, minutes=10),
        status=DocumentStatus.NORMALIZED,
        tags=["zeta", "filing"],
        provenance=_provenance(
            ["src_zeta_filing"],
            processing_time=FIXED_NOW + timedelta(hours=8, minutes=10),
        ),
        created_at=FIXED_NOW + timedelta(hours=8, minutes=10),
        updated_at=FIXED_NOW + timedelta(hours=8, minutes=10),
        form_type=FilingForm.FORM_8K,
        accession_number="0000000000-26-000001",
        filing_date=date(2026, 3, 22),
        period_end_date=date(2025, 12, 31),
        amendment=False,
        exhibit_ids=[],
        raw_html_uri=None,
        normalized_text_uri=None,
    )

    apex_span = EvidenceSpan(
        evidence_span_id="span_apex",
        source_reference_id="src_apex_news",
        document_id="doc_apex_news",
        segment_id=None,
        text="Apex management said enterprise demand is recovering steadily.",
        start_char=None,
        end_char=None,
        page_number=None,
        speaker="CEO",
        captured_at=FIXED_NOW + timedelta(hours=1),
        confidence=None,
        provenance=_provenance(["src_apex_news"], processing_time=FIXED_NOW + timedelta(hours=1)),
        created_at=FIXED_NOW + timedelta(hours=1),
        updated_at=FIXED_NOW + timedelta(hours=1),
    )
    zeta_span = EvidenceSpan(
        evidence_span_id="span_zeta",
        source_reference_id="src_zeta_filing",
        document_id="doc_zeta_filing",
        segment_id=None,
        text="Zeta disclosed continued margin pressure in its filing.",
        start_char=None,
        end_char=None,
        page_number=1,
        speaker=None,
        captured_at=FIXED_NOW + timedelta(hours=9),
        confidence=None,
        provenance=_provenance(["src_zeta_filing"], processing_time=FIXED_NOW + timedelta(hours=9)),
        created_at=FIXED_NOW + timedelta(hours=9),
        updated_at=FIXED_NOW + timedelta(hours=9),
    )

    apex_link = _supporting_link(
        link_id="sel_apex",
        source_reference_id="src_apex_news",
        document_id="doc_apex_news",
        evidence_span_id="span_apex",
        quote=apex_span.text,
        note="Demand recovery supports a constructive view.",
        created_at=FIXED_NOW + timedelta(hours=1, minutes=5),
    )
    zeta_link = _supporting_link(
        link_id="sel_zeta",
        source_reference_id="src_zeta_filing",
        document_id="doc_zeta_filing",
        evidence_span_id="span_zeta",
        quote=zeta_span.text,
        note="Margin pressure supports a cautious stance.",
        created_at=FIXED_NOW + timedelta(hours=9, minutes=5),
    )

    apex_hypothesis = Hypothesis(
        hypothesis_id="hyp_apex",
        company_id="co_apex",
        title="Apex enterprise demand recovery",
        thesis="Apex should see improving demand over the next two quarters.",
        stance=ResearchStance.POSITIVE,
        status=HypothesisStatus.DRAFT,
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        time_horizon="next_two_quarters",
        catalyst="Upcoming enterprise bookings update",
        invalidation_conditions=["Demand weakens again"],
        supporting_evidence_links=[apex_link],
        assumptions=["Customers convert current pipeline"],
        uncertainties=["Recovery may remain uneven"],
        validation_steps=["Check next bookings print"],
        evidence_assessment_id="ea_apex",
        confidence=None,
        provenance=_provenance(
            ["src_apex_news"],
            upstream_artifact_ids=["span_apex"],
            processing_time=FIXED_NOW + timedelta(hours=2),
        ),
        created_at=FIXED_NOW + timedelta(hours=2),
        updated_at=FIXED_NOW + timedelta(hours=2),
    )
    zeta_hypothesis = Hypothesis(
        hypothesis_id="hyp_zeta",
        company_id="co_zeta",
        title="Zeta margin pressure persists",
        thesis="Zeta likely remains under margin pressure this quarter.",
        stance=ResearchStance.NEGATIVE,
        status=HypothesisStatus.DRAFT,
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        time_horizon="current_quarter",
        catalyst="Next cost update",
        invalidation_conditions=["Cost relief appears quickly"],
        supporting_evidence_links=[zeta_link],
        assumptions=["Cost controls lag"],
        uncertainties=["Management could offset pressure"],
        validation_steps=["Check next filing and call"],
        evidence_assessment_id=None,
        confidence=None,
        provenance=_provenance(
            ["src_zeta_filing"],
            upstream_artifact_ids=["span_zeta"],
            processing_time=FIXED_NOW + timedelta(hours=10),
        ),
        created_at=FIXED_NOW + timedelta(hours=10),
        updated_at=FIXED_NOW + timedelta(hours=10),
    )
    apex_counter = CounterHypothesis(
        counter_hypothesis_id="ch_apex",
        hypothesis_id="hyp_apex",
        title="Apex recovery could stall",
        thesis="Demand improvement may prove short-lived.",
        critique_kinds=[CritiqueKind.ASSUMPTION_RISK],
        supporting_evidence_links=[apex_link],
        challenged_assumptions=["Customers convert current pipeline"],
        missing_evidence=["Bookings trend remains thin"],
        causal_gaps=["Demand commentary is still qualitative"],
        unresolved_questions=["How broad is the recovery?"],
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        confidence=None,
        provenance=_provenance(
            ["src_apex_news"],
            upstream_artifact_ids=["hyp_apex", "span_apex"],
            processing_time=FIXED_NOW + timedelta(hours=3),
        ),
        created_at=FIXED_NOW + timedelta(hours=3),
        updated_at=FIXED_NOW + timedelta(hours=3),
    )
    apex_assessment = EvidenceAssessment(
        evidence_assessment_id="ea_apex",
        company_id="co_apex",
        hypothesis_id="hyp_apex",
        grade=EvidenceGrade.MODERATE,
        supporting_evidence_link_ids=["sel_apex"],
        support_summary="Current evidence supports a cautiously constructive demand view.",
        key_gaps=["Need harder bookings evidence"],
        contradiction_notes=["Recovery may remain uneven"],
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.PENDING_VALIDATION,
        confidence=None,
        provenance=_provenance(
            ["src_apex_news"],
            upstream_artifact_ids=["hyp_apex", "sel_apex"],
            processing_time=FIXED_NOW + timedelta(hours=4),
        ),
        created_at=FIXED_NOW + timedelta(hours=4),
        updated_at=FIXED_NOW + timedelta(hours=4),
    )
    apex_brief = ResearchBrief(
        research_brief_id="rb_apex",
        company_id="co_apex",
        title="Apex demand recovery brief",
        context_summary="Apex demand commentary improved after a weak prior period.",
        core_hypothesis=apex_hypothesis.thesis,
        counter_hypothesis_summary=apex_counter.thesis,
        hypothesis_id="hyp_apex",
        counter_hypothesis_id="ch_apex",
        evidence_assessment_id="ea_apex",
        supporting_evidence_links=[apex_link],
        key_counterarguments=["Recovery may be uneven"],
        confidence=None,
        uncertainty_summary="Recovery remains early and partly qualitative.",
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        next_validation_steps=["Check next enterprise bookings print"],
        provenance=_provenance(
            ["src_apex_news"],
            upstream_artifact_ids=["hyp_apex", "ch_apex", "ea_apex"],
            processing_time=FIXED_NOW + timedelta(hours=5),
        ),
        created_at=FIXED_NOW + timedelta(hours=5),
        updated_at=FIXED_NOW + timedelta(hours=5),
    )
    apex_memo = Memo(
        memo_id="memo_apex",
        title="Apex PM memo",
        status=MemoStatus.DRAFT,
        audience="pm",
        generated_at=FIXED_NOW + timedelta(hours=6),
        author_agent_run_id=None,
        related_hypothesis_ids=["hyp_apex"],
        related_portfolio_proposal_id=None,
        executive_summary="Apex demand appears to be recovering, but evidence remains moderate.",
        key_points=["Demand commentary improved", "Recovery still needs confirmation"],
        key_risks=["Recovery may not persist"],
        open_questions=["Will bookings confirm the demand signal?"],
        content_uri=None,
        provenance=_provenance(
            ["src_apex_news"],
            upstream_artifact_ids=["rb_apex", "hyp_apex"],
            processing_time=FIXED_NOW + timedelta(hours=6),
        ),
        created_at=FIXED_NOW + timedelta(hours=6),
        updated_at=FIXED_NOW + timedelta(hours=6),
    )
    apex_experiment = Experiment(
        experiment_id="exp_apex",
        name="Apex demand recovery experiment",
        objective="Test whether the Apex demand thesis survives deterministic review.",
        created_by="research_memory_test",
        status=ExperimentStatus.COMPLETED,
        experiment_config_id="expcfg_apex",
        run_context_id="runctx_apex",
        dataset_reference_ids=["dsref_apex"],
        model_reference_ids=[],
        hypothesis_ids=["hyp_apex"],
        backtest_run_ids=[],
        experiment_artifact_ids=[],
        experiment_metric_ids=[],
        started_at=FIXED_NOW + timedelta(hours=7),
        completed_at=FIXED_NOW + timedelta(hours=8),
        notes=["Metadata-first experiment record for retrieval testing."],
        provenance=_provenance(
            ["src_apex_news"],
            upstream_artifact_ids=["hyp_apex"],
            processing_time=FIXED_NOW + timedelta(hours=8),
        ),
        created_at=FIXED_NOW + timedelta(hours=7),
        updated_at=FIXED_NOW + timedelta(hours=8),
    )
    apex_review_note = ReviewNote(
        review_note_id="rnote_apex",
        target_type=ReviewTargetType.RESEARCH_BRIEF,
        target_id="rb_apex",
        author_id="reviewer_1",
        created_at=FIXED_NOW + timedelta(hours=9),
        body="Needs a clearer note about how durable the demand recovery is.",
        related_artifact_ids=["rb_apex", "hyp_apex"],
        provenance=_provenance(
            ["src_apex_news"],
            upstream_artifact_ids=["rb_apex"],
            processing_time=FIXED_NOW + timedelta(hours=9),
        ),
        updated_at=FIXED_NOW + timedelta(hours=9),
    )

    _write_model(workspace_root / "ingestion" / "normalized" / "news_items", "doc_apex_news", news_document)
    _write_model(
        workspace_root / "ingestion" / "normalized" / "filings",
        "doc_zeta_filing",
        filing_document,
    )
    _write_model(workspace_root / "parsing" / "evidence_spans", "span_apex", apex_span)
    _write_model(workspace_root / "parsing" / "evidence_spans", "span_zeta", zeta_span)
    _write_model(workspace_root / "research" / "hypotheses", "hyp_apex", apex_hypothesis)
    _write_model(workspace_root / "research" / "hypotheses", "hyp_zeta", zeta_hypothesis)
    _write_model(
        workspace_root / "research" / "counter_hypotheses",
        "ch_apex",
        apex_counter,
    )
    _write_model(
        workspace_root / "research" / "evidence_assessments",
        "ea_apex",
        apex_assessment,
    )
    _write_model(workspace_root / "research" / "research_briefs", "rb_apex", apex_brief)
    _write_model(workspace_root / "research" / "memos", "memo_apex", apex_memo)
    _write_model(workspace_root / "experiments" / "experiments", "exp_apex", apex_experiment)
    _write_model(workspace_root / "review" / "review_notes", "rnote_apex", apex_review_note)
    return workspace_root


def _supporting_link(
    *,
    link_id: str,
    source_reference_id: str,
    document_id: str,
    evidence_span_id: str,
    quote: str,
    note: str,
    created_at: datetime,
) -> SupportingEvidenceLink:
    return SupportingEvidenceLink(
        supporting_evidence_link_id=link_id,
        source_reference_id=source_reference_id,
        document_id=document_id,
        evidence_span_id=evidence_span_id,
        extracted_artifact_id=None,
        role=EvidenceLinkRole.SUPPORT,
        quote=quote,
        note=note,
        provenance=_provenance([source_reference_id], processing_time=created_at),
        created_at=created_at,
        updated_at=created_at,
    )


def _provenance(
    source_reference_ids: list[str],
    *,
    upstream_artifact_ids: list[str] | None = None,
    processing_time: datetime,
) -> ProvenanceRecord:
    return ProvenanceRecord(
        source_reference_ids=source_reference_ids,
        upstream_artifact_ids=upstream_artifact_ids or [],
        processing_time=processing_time,
    )


def _write_model(directory: Path, filename_stem: str, model: StrictModel) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{filename_stem}.json"
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def _uri_exists(uri: str) -> bool:
    return Path(urlparse(uri).path).exists()
