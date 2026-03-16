from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_api_health_and_version() -> None:
    health_response = client.get("/health")
    version_response = client.get("/version")

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
    assert version_response.status_code == 200
    assert version_response.json()["version"] == "0.1.0"


def test_capabilities_and_document_ingestion_placeholder() -> None:
    capabilities_response = client.get("/capabilities")
    ingest_response = client.post(
        "/documents/ingest",
        json={
            "source_reference_id": "src_test",
            "document_kind": "filing",
            "title": "Sample Filing",
            "raw_text": "payload",
            "requested_by": "integration_test",
        },
    )

    assert capabilities_response.status_code == 200
    assert len(capabilities_response.json()["services"]) >= 5
    assert ingest_response.status_code == 200
    assert ingest_response.json()["status"] == "queued"
