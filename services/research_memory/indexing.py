from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from libraries.core import build_provenance
from libraries.schemas import (
    BacktestRun,
    Document,
    DocumentKind,
    EvidenceSearchResult,
    Experiment,
    Hypothesis,
    Memo,
    MemoryScope,
    PaperTrade,
    PortfolioProposal,
    ResearchArtifactReference,
    ResearchBrief,
    RetrievalContext,
    RetrievalQuery,
    RetrievalResult,
    ReviewNote,
    ReviewTargetType,
    Signal,
    SupportingEvidenceLink,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from services.research_memory.loaders import ResearchMemoryWorkspace

SUPPORTED_METADATA_FILTERS = frozenset(
    {
        "status",
        "review_status",
        "validation_status",
        "stance",
        "grade",
        "audience",
    }
)


class SearchableArtifactKind(StrEnum):
    """Internal classification used to build evidence-specific citations."""

    HYPOTHESIS = "hypothesis"
    COUNTER_HYPOTHESIS = "counter_hypothesis"
    EVIDENCE_ASSESSMENT = "evidence_assessment"
    RESEARCH_BRIEF = "research_brief"
    MEMO = "memo"
    EXPERIMENT = "experiment"
    REVIEW_NOTE = "review_note"
    EVIDENCE = "evidence"


@dataclass(frozen=True)
class CatalogEntry:
    """One searchable persisted artifact plus derived search metadata."""

    artifact_kind: SearchableArtifactKind
    artifact_reference: ResearchArtifactReference
    searchable_fields: dict[str, str]
    metadata: dict[str, str]
    cited_evidence_span_ids: tuple[str, ...] = ()
    evidence_link_ids: tuple[str, ...] = ()
    review_target_type: ReviewTargetType | None = None
    review_target_id: str | None = None


@dataclass(frozen=True)
class SearchMatch:
    """Matched catalog entry with deterministic ranking context."""

    entry: CatalogEntry
    matched_fields: list[str]
    score: float | None
    snippet: str | None


def build_catalog(
    *,
    workspace: ResearchMemoryWorkspace,
    clock: Clock,
) -> list[CatalogEntry]:
    """Build in-memory searchable references from persisted artifacts."""

    documents_by_id = {stored.model.document_id: stored.model for stored in workspace.documents}
    hypotheses_by_id = {stored.model.hypothesis_id: stored.model for stored in workspace.hypotheses}
    signals_by_id = {stored.model.signal_id: stored.model for stored in workspace.signals}
    proposals_by_id = {
        stored.model.portfolio_proposal_id: stored.model for stored in workspace.portfolio_proposals
    }
    paper_trades_by_id = {stored.model.paper_trade_id: stored.model for stored in workspace.paper_trades}
    backtest_runs_by_id = {stored.model.backtest_run_id: stored.model for stored in workspace.backtest_runs}

    supporting_links_by_id: dict[str, SupportingEvidenceLink] = {}
    for stored_hypothesis in workspace.hypotheses:
        for link in stored_hypothesis.model.supporting_evidence_links:
            supporting_links_by_id[link.supporting_evidence_link_id] = link
    for stored_counter_hypothesis in workspace.counter_hypotheses:
        for link in stored_counter_hypothesis.model.supporting_evidence_links:
            supporting_links_by_id[link.supporting_evidence_link_id] = link
    for stored_brief in workspace.research_briefs:
        for link in stored_brief.model.supporting_evidence_links:
            supporting_links_by_id[link.supporting_evidence_link_id] = link

    entries: list[CatalogEntry] = []
    references_by_artifact_id: dict[str, ResearchArtifactReference] = {}

    def register(entry: CatalogEntry) -> None:
        entries.append(entry)
        references_by_artifact_id[entry.artifact_reference.artifact_id] = entry.artifact_reference

    for stored_hypothesis in workspace.hypotheses:
        doc_id, doc_kind = _document_context_from_links(
            links=stored_hypothesis.model.supporting_evidence_links,
            documents_by_id=documents_by_id,
        )
        reference = _build_reference(
            scope=MemoryScope.HYPOTHESIS,
            artifact_type="Hypothesis",
            artifact_id=stored_hypothesis.model.hypothesis_id,
            storage_uri=stored_hypothesis.uri,
            company_id=stored_hypothesis.model.company_id,
            document_id=doc_id,
            document_kind=doc_kind,
            primary_timestamp=stored_hypothesis.model.created_at,
            title=stored_hypothesis.model.title,
            summary=stored_hypothesis.model.thesis,
            source_reference_ids=stored_hypothesis.model.provenance.source_reference_ids,
            clock=clock,
        )
        register(
            CatalogEntry(
                artifact_kind=SearchableArtifactKind.HYPOTHESIS,
                artifact_reference=reference,
                searchable_fields={
                    "title": stored_hypothesis.model.title,
                    "thesis": stored_hypothesis.model.thesis,
                    "assumptions": " ".join(stored_hypothesis.model.assumptions),
                    "uncertainties": " ".join(stored_hypothesis.model.uncertainties),
                    "validation_steps": " ".join(stored_hypothesis.model.validation_steps),
                    "catalyst": stored_hypothesis.model.catalyst or "",
                },
                metadata={
                    "status": stored_hypothesis.model.status.value,
                    "review_status": stored_hypothesis.model.review_status.value,
                    "validation_status": stored_hypothesis.model.validation_status.value,
                    "stance": stored_hypothesis.model.stance.value,
                },
                cited_evidence_span_ids=tuple(
                    link.evidence_span_id for link in stored_hypothesis.model.supporting_evidence_links
                ),
                evidence_link_ids=tuple(
                    link.supporting_evidence_link_id
                    for link in stored_hypothesis.model.supporting_evidence_links
                ),
            )
        )

    for stored_counter_hypothesis in workspace.counter_hypotheses:
        parent_hypothesis = hypotheses_by_id.get(stored_counter_hypothesis.model.hypothesis_id)
        company_id = parent_hypothesis.company_id if parent_hypothesis is not None else None
        doc_id, doc_kind = _document_context_from_links(
            links=stored_counter_hypothesis.model.supporting_evidence_links,
            documents_by_id=documents_by_id,
        )
        reference = _build_reference(
            scope=MemoryScope.COUNTER_HYPOTHESIS,
            artifact_type="CounterHypothesis",
            artifact_id=stored_counter_hypothesis.model.counter_hypothesis_id,
            storage_uri=stored_counter_hypothesis.uri,
            company_id=company_id,
            document_id=doc_id,
            document_kind=doc_kind,
            primary_timestamp=stored_counter_hypothesis.model.created_at,
            title=stored_counter_hypothesis.model.title,
            summary=stored_counter_hypothesis.model.thesis,
            source_reference_ids=stored_counter_hypothesis.model.provenance.source_reference_ids,
            clock=clock,
        )
        register(
            CatalogEntry(
                artifact_kind=SearchableArtifactKind.COUNTER_HYPOTHESIS,
                artifact_reference=reference,
                searchable_fields={
                    "title": stored_counter_hypothesis.model.title,
                    "thesis": stored_counter_hypothesis.model.thesis,
                    "challenged_assumptions": " ".join(
                        stored_counter_hypothesis.model.challenged_assumptions
                    ),
                    "missing_evidence": " ".join(
                        stored_counter_hypothesis.model.missing_evidence
                    ),
                    "causal_gaps": " ".join(stored_counter_hypothesis.model.causal_gaps),
                    "unresolved_questions": " ".join(
                        stored_counter_hypothesis.model.unresolved_questions
                    ),
                },
                metadata={
                    "review_status": stored_counter_hypothesis.model.review_status.value,
                    "validation_status": stored_counter_hypothesis.model.validation_status.value,
                },
                cited_evidence_span_ids=tuple(
                    link.evidence_span_id
                    for link in stored_counter_hypothesis.model.supporting_evidence_links
                ),
                evidence_link_ids=tuple(
                    link.supporting_evidence_link_id
                    for link in stored_counter_hypothesis.model.supporting_evidence_links
                ),
            )
        )

    for stored_assessment in workspace.evidence_assessments:
        doc_id, doc_kind = _document_context_from_link_ids(
            link_ids=stored_assessment.model.supporting_evidence_link_ids,
            supporting_links_by_id=supporting_links_by_id,
            documents_by_id=documents_by_id,
        )
        reference = _build_reference(
            scope=MemoryScope.EVIDENCE_ASSESSMENT,
            artifact_type="EvidenceAssessment",
            artifact_id=stored_assessment.model.evidence_assessment_id,
            storage_uri=stored_assessment.uri,
            company_id=stored_assessment.model.company_id,
            document_id=doc_id,
            document_kind=doc_kind,
            primary_timestamp=stored_assessment.model.created_at,
            title=f"Evidence assessment for {stored_assessment.model.company_id}",
            summary=stored_assessment.model.support_summary,
            source_reference_ids=stored_assessment.model.provenance.source_reference_ids,
            clock=clock,
        )
        register(
            CatalogEntry(
                artifact_kind=SearchableArtifactKind.EVIDENCE_ASSESSMENT,
                artifact_reference=reference,
                searchable_fields={
                    "support_summary": stored_assessment.model.support_summary,
                    "key_gaps": " ".join(stored_assessment.model.key_gaps),
                    "contradiction_notes": " ".join(stored_assessment.model.contradiction_notes),
                },
                metadata={
                    "review_status": stored_assessment.model.review_status.value,
                    "validation_status": stored_assessment.model.validation_status.value,
                    "grade": stored_assessment.model.grade.value,
                },
                cited_evidence_span_ids=tuple(
                    supporting_links_by_id[link_id].evidence_span_id
                    for link_id in stored_assessment.model.supporting_evidence_link_ids
                    if link_id in supporting_links_by_id
                ),
                evidence_link_ids=tuple(stored_assessment.model.supporting_evidence_link_ids),
            )
        )

    for stored_brief in workspace.research_briefs:
        doc_id, doc_kind = _document_context_from_links(
            links=stored_brief.model.supporting_evidence_links,
            documents_by_id=documents_by_id,
        )
        reference = _build_reference(
            scope=MemoryScope.RESEARCH_BRIEF,
            artifact_type="ResearchBrief",
            artifact_id=stored_brief.model.research_brief_id,
            storage_uri=stored_brief.uri,
            company_id=stored_brief.model.company_id,
            document_id=doc_id,
            document_kind=doc_kind,
            primary_timestamp=stored_brief.model.created_at,
            title=stored_brief.model.title,
            summary=stored_brief.model.context_summary,
            source_reference_ids=stored_brief.model.provenance.source_reference_ids,
            clock=clock,
        )
        register(
            CatalogEntry(
                artifact_kind=SearchableArtifactKind.RESEARCH_BRIEF,
                artifact_reference=reference,
                searchable_fields={
                    "title": stored_brief.model.title,
                    "context_summary": stored_brief.model.context_summary,
                    "core_hypothesis": stored_brief.model.core_hypothesis,
                    "counter_hypothesis_summary": stored_brief.model.counter_hypothesis_summary,
                    "uncertainty_summary": stored_brief.model.uncertainty_summary,
                    "key_counterarguments": " ".join(stored_brief.model.key_counterarguments),
                    "next_validation_steps": " ".join(stored_brief.model.next_validation_steps),
                },
                metadata={
                    "review_status": stored_brief.model.review_status.value,
                    "validation_status": stored_brief.model.validation_status.value,
                },
                cited_evidence_span_ids=tuple(
                    link.evidence_span_id for link in stored_brief.model.supporting_evidence_links
                ),
                evidence_link_ids=tuple(
                    link.supporting_evidence_link_id
                    for link in stored_brief.model.supporting_evidence_links
                ),
            )
        )

    for stored_memo in workspace.memos:
        company_id = _company_id_for_memo(
            memo=stored_memo.model,
            hypotheses_by_id=hypotheses_by_id,
            proposals_by_id=proposals_by_id,
        )
        doc_id, doc_kind = _document_context_for_memo(
            memo=stored_memo.model,
            hypotheses_by_id=hypotheses_by_id,
            documents_by_id=documents_by_id,
        )
        reference = _build_reference(
            scope=MemoryScope.MEMO,
            artifact_type="Memo",
            artifact_id=stored_memo.model.memo_id,
            storage_uri=stored_memo.uri,
            company_id=company_id,
            document_id=doc_id,
            document_kind=doc_kind,
            primary_timestamp=stored_memo.model.generated_at,
            title=stored_memo.model.title,
            summary=stored_memo.model.executive_summary,
            source_reference_ids=stored_memo.model.provenance.source_reference_ids,
            clock=clock,
        )
        register(
            CatalogEntry(
                artifact_kind=SearchableArtifactKind.MEMO,
                artifact_reference=reference,
                searchable_fields={
                    "title": stored_memo.model.title,
                    "executive_summary": stored_memo.model.executive_summary,
                    "key_points": " ".join(stored_memo.model.key_points),
                    "key_risks": " ".join(stored_memo.model.key_risks),
                    "open_questions": " ".join(stored_memo.model.open_questions),
                },
                metadata={
                    "status": stored_memo.model.status.value,
                    "audience": stored_memo.model.audience,
                },
            )
        )

    for stored_experiment in workspace.experiments:
        company_id = _company_id_for_experiment(
            experiment=stored_experiment.model,
            hypotheses_by_id=hypotheses_by_id,
            backtest_runs_by_id=backtest_runs_by_id,
        )
        doc_id, doc_kind = _document_context_for_experiment(
            experiment=stored_experiment.model,
            hypotheses_by_id=hypotheses_by_id,
            documents_by_id=documents_by_id,
        )
        reference = _build_reference(
            scope=MemoryScope.EXPERIMENT,
            artifact_type="Experiment",
            artifact_id=stored_experiment.model.experiment_id,
            storage_uri=stored_experiment.uri,
            company_id=company_id,
            document_id=doc_id,
            document_kind=doc_kind,
            primary_timestamp=stored_experiment.model.started_at,
            title=stored_experiment.model.name,
            summary=stored_experiment.model.objective,
            source_reference_ids=stored_experiment.model.provenance.source_reference_ids,
            clock=clock,
        )
        register(
            CatalogEntry(
                artifact_kind=SearchableArtifactKind.EXPERIMENT,
                artifact_reference=reference,
                searchable_fields={
                    "name": stored_experiment.model.name,
                    "objective": stored_experiment.model.objective,
                    "notes": " ".join(stored_experiment.model.notes),
                },
                metadata={"status": stored_experiment.model.status.value},
            )
        )

    for stored_review_note in workspace.review_notes:
        company_id = _company_id_for_review_note(
            review_note=stored_review_note.model,
            research_briefs={item.model.research_brief_id: item.model for item in workspace.research_briefs},
            signals_by_id=signals_by_id,
            proposals_by_id=proposals_by_id,
            paper_trades_by_id=paper_trades_by_id,
        )
        reference = _build_reference(
            scope=MemoryScope.REVIEW_NOTE,
            artifact_type="ReviewNote",
            artifact_id=stored_review_note.model.review_note_id,
            storage_uri=stored_review_note.uri,
            company_id=company_id,
            document_id=None,
            document_kind=None,
            primary_timestamp=stored_review_note.model.created_at,
            title=f"Review note on {stored_review_note.model.target_type.value}",
            summary=stored_review_note.model.body,
            source_reference_ids=stored_review_note.model.provenance.source_reference_ids,
            clock=clock,
        )
        register(
            CatalogEntry(
                artifact_kind=SearchableArtifactKind.REVIEW_NOTE,
                artifact_reference=reference,
                searchable_fields={"body": stored_review_note.model.body},
                metadata={},
                review_target_type=stored_review_note.model.target_type,
                review_target_id=stored_review_note.model.target_id,
            )
        )

    evidence_citations = _build_evidence_citations(
        entries=entries,
        references_by_artifact_id=references_by_artifact_id,
    )
    for stored_evidence_span in workspace.evidence_spans:
        document = documents_by_id.get(stored_evidence_span.model.document_id or "")
        reference = _build_reference(
            scope=MemoryScope.EVIDENCE,
            artifact_type="EvidenceSpan",
            artifact_id=stored_evidence_span.model.evidence_span_id,
            storage_uri=stored_evidence_span.uri,
            company_id=document.company_id if document is not None else None,
            document_id=stored_evidence_span.model.document_id,
            document_kind=document.kind if document is not None else None,
            primary_timestamp=stored_evidence_span.model.captured_at,
            title=None,
            summary=stored_evidence_span.model.text,
            source_reference_ids=_dedupe_preserve_order(
                [
                    stored_evidence_span.model.source_reference_id,
                    *stored_evidence_span.model.provenance.source_reference_ids,
                ]
            ),
            clock=clock,
        )
        register(
            CatalogEntry(
                artifact_kind=SearchableArtifactKind.EVIDENCE,
                artifact_reference=reference,
                searchable_fields={
                    "text": stored_evidence_span.model.text,
                    "speaker": stored_evidence_span.model.speaker or "",
                },
                metadata={},
                cited_evidence_span_ids=tuple(
                    reference.artifact_id
                    for reference in evidence_citations.get(
                        stored_evidence_span.model.evidence_span_id,
                        [],
                    )
                ),
            )
        )

    return entries


def search_catalog(
    *,
    catalog: list[CatalogEntry],
    query: RetrievalQuery,
    clock: Clock,
) -> RetrievalContext:
    """Search the in-memory catalog with deterministic filtering and ranking."""

    unsupported_metadata_filters = sorted(
        set(query.metadata_filters).difference(SUPPORTED_METADATA_FILTERS)
    )
    if unsupported_metadata_filters:
        raise ValueError(
            "Unsupported metadata filter keys: " + ", ".join(unsupported_metadata_filters)
        )

    matches = [
        match
        for entry in catalog
        if (match := _match_entry(entry=entry, query=query)) is not None
    ]
    sorted_matches = sorted(
        matches,
        key=lambda match: _sort_key(match=match, keyword_search=bool(query.keyword_terms)),
    )[: query.limit]

    results: list[RetrievalResult] = []
    evidence_results: list[EvidenceSearchResult] = []
    for rank, match in enumerate(sorted_matches, start=1):
        provenance = build_provenance(
            clock=clock,
            transformation_name="day18_research_memory_retrieval",
            source_reference_ids=match.entry.artifact_reference.source_reference_ids,
            upstream_artifact_ids=[match.entry.artifact_reference.artifact_id],
            notes=[f"retrieval_query_id={query.retrieval_query_id}"],
        )
        if match.entry.artifact_reference.scope is MemoryScope.EVIDENCE:
            evidence_results.append(
                EvidenceSearchResult(
                    evidence_search_result_id=make_canonical_id(
                        "erslt",
                        query.retrieval_query_id,
                        match.entry.artifact_reference.artifact_id,
                    ),
                    artifact_reference=match.entry.artifact_reference,
                    quote=match.entry.searchable_fields["text"],
                    source_reference_id=match.entry.artifact_reference.source_reference_ids[0]
                    if match.entry.artifact_reference.source_reference_ids
                    else "",
                    document_id=match.entry.artifact_reference.document_id or "",
                    document_kind=match.entry.artifact_reference.document_kind,
                    citing_artifact_references=_citation_references_for_entry(
                        match.entry,
                        catalog=catalog,
                    ),
                    rank=rank,
                    matched_fields=match.matched_fields,
                    score=match.score,
                    provenance=provenance,
                )
            )
        else:
            results.append(
                RetrievalResult(
                    retrieval_result_id=make_canonical_id(
                        "rrslt",
                        query.retrieval_query_id,
                        match.entry.artifact_reference.artifact_id,
                    ),
                    artifact_reference=match.entry.artifact_reference,
                    scope=match.entry.artifact_reference.scope,
                    rank=rank,
                    matched_fields=match.matched_fields,
                    snippet=match.snippet,
                    score=match.score,
                    provenance=provenance,
                )
            )

    notes: list[str] = [
        "Search is metadata-first with deterministic substring matching only.",
        "semantic_retrieval_used=False",
    ]
    if not results and not evidence_results:
        notes.append("No matching artifacts were found.")
    return RetrievalContext(
        query=query,
        results=results,
        evidence_results=evidence_results,
        notes=notes,
        semantic_retrieval_used=False,
    )


def _match_entry(*, entry: CatalogEntry, query: RetrievalQuery) -> SearchMatch | None:
    matched_fields: list[str] = []
    if entry.artifact_reference.scope not in query.scopes:
        return None
    matched_fields.append("scope")
    if query.company_id is not None:
        if entry.artifact_reference.company_id != query.company_id:
            return None
        matched_fields.append("company_id")
    if query.artifact_types:
        if entry.artifact_reference.artifact_type not in query.artifact_types:
            return None
        matched_fields.append("artifact_type")
    if query.document_kinds:
        if entry.artifact_reference.document_kind not in query.document_kinds:
            return None
        matched_fields.append("document_kind")
    if query.time_start is not None and entry.artifact_reference.primary_timestamp < query.time_start:
        return None
    if query.time_end is not None and entry.artifact_reference.primary_timestamp > query.time_end:
        return None
    if query.time_start is not None or query.time_end is not None:
        matched_fields.append("primary_timestamp")
    for key, value in query.metadata_filters.items():
        if entry.metadata.get(key) != value:
            return None
        matched_fields.append(key)

    score: float | None = None
    if query.keyword_terms:
        keyword_matched_fields: list[str] = []
        for keyword_term in query.keyword_terms:
            normalized_term = keyword_term.lower()
            fields_for_term = [
                field_name
                for field_name, field_value in entry.searchable_fields.items()
                if normalized_term in field_value.lower()
            ]
            if not fields_for_term:
                return None
            keyword_matched_fields.extend(fields_for_term)
        matched_fields.extend(sorted(set(keyword_matched_fields)))
        score = float(len(set(keyword_matched_fields)))

    return SearchMatch(
        entry=entry,
        matched_fields=_dedupe_preserve_order(matched_fields),
        score=score,
        snippet=_build_snippet(entry=entry, keyword_terms=query.keyword_terms),
    )


def _sort_key(*, match: SearchMatch, keyword_search: bool) -> tuple[Any, ...]:
    timestamp = match.entry.artifact_reference.primary_timestamp.astimezone(UTC)
    if keyword_search:
        return (
            -(match.score or 0.0),
            -timestamp.timestamp(),
            match.entry.artifact_reference.artifact_id,
        )
    return (
        -timestamp.timestamp(),
        match.entry.artifact_reference.artifact_id,
    )


def _build_reference(
    *,
    scope: MemoryScope,
    artifact_type: str,
    artifact_id: str,
    storage_uri: str,
    company_id: str | None,
    document_id: str | None,
    document_kind: DocumentKind | None,
    primary_timestamp: datetime,
    title: str | None,
    summary: str | None,
    source_reference_ids: list[str],
    clock: Clock,
) -> ResearchArtifactReference:
    return ResearchArtifactReference(
        research_artifact_reference_id=make_canonical_id("rref", scope.value, artifact_id),
        scope=scope,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        storage_uri=storage_uri,
        company_id=company_id,
        document_id=document_id,
        document_kind=document_kind,
        primary_timestamp=primary_timestamp,
        title=title,
        summary=summary,
        source_reference_ids=source_reference_ids,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day18_research_artifact_reference",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=[artifact_id],
        ),
    )


def _document_context_from_links(
    *,
    links: list[SupportingEvidenceLink],
    documents_by_id: dict[str, Document],
) -> tuple[str | None, DocumentKind | None]:
    resolved_documents = [
        document
        for link in links
        for document in [documents_by_id.get(link.document_id or "")]
        if document is not None
    ]
    if not resolved_documents:
        return None, None
    unique_document_ids = {document.document_id for document in resolved_documents}
    unique_document_kinds = {document.kind for document in resolved_documents}
    document_id = next(iter(unique_document_ids)) if len(unique_document_ids) == 1 else None
    document_kind = next(iter(unique_document_kinds)) if len(unique_document_kinds) == 1 else None
    return document_id, document_kind


def _document_context_from_link_ids(
    *,
    link_ids: list[str],
    supporting_links_by_id: dict[str, SupportingEvidenceLink],
    documents_by_id: dict[str, Document],
) -> tuple[str | None, DocumentKind | None]:
    links = [
        supporting_links_by_id[link_id]
        for link_id in link_ids
        if link_id in supporting_links_by_id
    ]
    return _document_context_from_links(links=links, documents_by_id=documents_by_id)


def _document_context_for_memo(
    *,
    memo: Memo,
    hypotheses_by_id: dict[str, Hypothesis],
    documents_by_id: dict[str, Document],
) -> tuple[str | None, DocumentKind | None]:
    links = [
        link
        for hypothesis_id in memo.related_hypothesis_ids
        for link in (
            hypotheses_by_id[hypothesis_id].supporting_evidence_links
            if hypothesis_id in hypotheses_by_id
            else []
        )
    ]
    return _document_context_from_links(links=links, documents_by_id=documents_by_id)


def _document_context_for_experiment(
    *,
    experiment: Experiment,
    hypotheses_by_id: dict[str, Hypothesis],
    documents_by_id: dict[str, Document],
) -> tuple[str | None, DocumentKind | None]:
    links = [
        link
        for hypothesis_id in experiment.hypothesis_ids
        for link in (
            hypotheses_by_id[hypothesis_id].supporting_evidence_links
            if hypothesis_id in hypotheses_by_id
            else []
        )
    ]
    return _document_context_from_links(links=links, documents_by_id=documents_by_id)


def _company_id_for_memo(
    *,
    memo: Memo,
    hypotheses_by_id: dict[str, Hypothesis],
    proposals_by_id: dict[str, PortfolioProposal],
) -> str | None:
    hypothesis_company_ids = {
        hypothesis.company_id
        for hypothesis_id in memo.related_hypothesis_ids
        if (hypothesis := hypotheses_by_id.get(hypothesis_id)) is not None
    }
    if len(hypothesis_company_ids) == 1:
        return next(iter(hypothesis_company_ids))
    if memo.related_portfolio_proposal_id is not None:
        proposal = proposals_by_id.get(memo.related_portfolio_proposal_id)
        if proposal is not None:
            company_ids = {idea.company_id for idea in proposal.position_ideas}
            if len(company_ids) == 1:
                return next(iter(company_ids))
    return None


def _company_id_for_experiment(
    *,
    experiment: Experiment,
    hypotheses_by_id: dict[str, Hypothesis],
    backtest_runs_by_id: dict[str, BacktestRun],
) -> str | None:
    hypothesis_company_ids = {
        hypothesis.company_id
        for hypothesis_id in experiment.hypothesis_ids
        if (hypothesis := hypotheses_by_id.get(hypothesis_id)) is not None
    }
    if len(hypothesis_company_ids) == 1:
        return next(iter(hypothesis_company_ids))
    backtest_company_ids = {
        run.company_id
        for backtest_run_id in experiment.backtest_run_ids
        if (run := backtest_runs_by_id.get(backtest_run_id)) is not None
    }
    if len(backtest_company_ids) == 1:
        return next(iter(backtest_company_ids))
    return None


def _company_id_for_review_note(
    *,
    review_note: ReviewNote,
    research_briefs: dict[str, ResearchBrief],
    signals_by_id: dict[str, Signal],
    proposals_by_id: dict[str, PortfolioProposal],
    paper_trades_by_id: dict[str, PaperTrade],
) -> str | None:
    if review_note.target_type is ReviewTargetType.RESEARCH_BRIEF:
        brief = research_briefs.get(review_note.target_id)
        return brief.company_id if brief is not None else None
    if review_note.target_type is ReviewTargetType.SIGNAL:
        signal = signals_by_id.get(review_note.target_id)
        return signal.company_id if signal is not None else None
    if review_note.target_type is ReviewTargetType.PORTFOLIO_PROPOSAL:
        proposal = proposals_by_id.get(review_note.target_id)
        if proposal is not None:
            company_ids = {idea.company_id for idea in proposal.position_ideas}
            if len(company_ids) == 1:
                return next(iter(company_ids))
        return None
    if review_note.target_type is ReviewTargetType.PAPER_TRADE:
        trade = paper_trades_by_id.get(review_note.target_id)
        if trade is None:
            return None
        proposal = proposals_by_id.get(trade.portfolio_proposal_id)
        if proposal is None:
            return None
        for idea in proposal.position_ideas:
            if idea.position_idea_id == trade.position_idea_id:
                return idea.company_id
        return None
    return None


def _build_evidence_citations(
    *,
    entries: list[CatalogEntry],
    references_by_artifact_id: dict[str, ResearchArtifactReference],
) -> dict[str, list[ResearchArtifactReference]]:
    citations: dict[str, list[ResearchArtifactReference]] = {}
    for entry in entries:
        if entry.artifact_kind is SearchableArtifactKind.EVIDENCE:
            continue
        for evidence_span_id in entry.cited_evidence_span_ids:
            citations.setdefault(evidence_span_id, []).append(
                references_by_artifact_id[entry.artifact_reference.artifact_id]
            )
    for evidence_span_id in citations:
        citations[evidence_span_id] = sorted(
            citations[evidence_span_id],
            key=lambda reference: (
                reference.primary_timestamp,
                reference.artifact_id,
            ),
            reverse=True,
        )
    return citations


def _citation_references_for_entry(
    entry: CatalogEntry,
    *,
    catalog: list[CatalogEntry],
) -> list[ResearchArtifactReference]:
    if entry.artifact_kind is not SearchableArtifactKind.EVIDENCE:
        return []
    evidence_span_id = entry.artifact_reference.artifact_id
    citations = [
        candidate.artifact_reference
        for candidate in catalog
        if candidate.artifact_kind is not SearchableArtifactKind.EVIDENCE
        and evidence_span_id in candidate.cited_evidence_span_ids
    ]
    return sorted(
        citations,
        key=lambda reference: (
            reference.primary_timestamp,
            reference.artifact_id,
        ),
        reverse=True,
    )


def _build_snippet(*, entry: CatalogEntry, keyword_terms: list[str]) -> str | None:
    if keyword_terms:
        lowered_terms = [term.lower() for term in keyword_terms]
        for field_value in entry.searchable_fields.values():
            lowered_value = field_value.lower()
            if any(term in lowered_value for term in lowered_terms):
                return field_value[:240]
    return entry.artifact_reference.summary[:240] if entry.artifact_reference.summary else None


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
