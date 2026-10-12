"""Tests for FastAPI Web Studio endpoints."""

from pathlib import Path
from fastapi.testclient import TestClient
from docuvision.web.app import app

client = TestClient(app)


def test_api_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "pymupdf_version" in data


def test_api_schemas():
    res = client.get("/api/schemas")
    assert res.status_code == 200
    data = res.json()
    assert "invoice" in data
    assert "receipt" in data


def test_api_vlm_status():
    res = client.get("/api/vlm/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data


def test_api_rasterize(sample_invoice_pdf: Path):
    with open(sample_invoice_pdf, "rb") as f:
        res = client.post("/api/rasterize?dpi=150", files={"file": ("invoice.pdf", f, "application/pdf")})
    assert res.status_code == 200
    data = res.json()
    assert data["total_pages"] == 1
    assert len(data["pages"]) == 1
    assert "image_base64" in data["pages"][0]


def test_api_tables(sample_invoice_pdf: Path):
    with open(sample_invoice_pdf, "rb") as f:
        res = client.post("/api/tables", files={"file": ("invoice.pdf", f, "application/pdf")})
    assert res.status_code == 200
    data = res.json()
    assert data["table_count"] >= 1
    assert len(data["tables"]) >= 1


def test_api_extract_deterministic(sample_invoice_pdf: Path):
    with open(sample_invoice_pdf, "rb") as f:
        res = client.post("/api/extract?schema_name=invoice&use_vlm=false&dpi=150", files={"file": ("invoice.pdf", f, "application/pdf")})
    assert res.status_code == 200
    data = res.json()
    assert data["metadata"]["filename"] == "invoice.pdf"
    assert len(data["tables"]) >= 1
    assert "line_items" in data["structured_data"]


def test_api_studio_ui():
    res = client.get("/")
    assert res.status_code == 200
    assert "DocuVision" in res.text
