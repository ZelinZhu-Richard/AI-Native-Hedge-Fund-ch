"""Document processing pipeline entrypoints."""

from pipelines.document_processing.evidence_extraction import run_evidence_extraction_pipeline
from pipelines.document_processing.fixture_ingestion import run_fixture_ingestion_pipeline

__all__ = ["run_evidence_extraction_pipeline", "run_fixture_ingestion_pipeline"]
