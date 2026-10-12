"""Tests for end-to-end document processing pipeline."""

from pathlib import Path
from docuvision.pipeline.orchestrator import DocumentPipeline


def test_pipeline_invoice_deterministic_run(sample_invoice_pdf: Path):
    # Running with use_vlm=False tests the deterministic table extraction + fallback mapper
    pipeline = DocumentPipeline()
    result = pipeline.process(
        source=sample_invoice_pdf,
        schema_name="invoice",
        dpi=150,
        use_vlm=False,
    )

    assert result.metadata.filename == "sample_invoice.pdf"
    assert result.metadata.total_pages == 1
    assert len(result.tables) >= 1
    assert result.schema_name == "invoice"
    assert "line_items" in result.structured_data
    assert len(result.structured_data["line_items"]) >= 1
    assert result.markdown_summary is not None
    assert "Document Extraction Summary" in result.markdown_summary
    assert result.latency_ms > 0.0


def test_pipeline_multipage_generic_run(multipage_pdf: Path):
    pipeline = DocumentPipeline()
    result = pipeline.process(
        source=multipage_pdf,
        schema_name="generic",
        dpi=150,
        use_vlm=False,
    )

    assert result.metadata.total_pages == 2
    assert len(result.pages) == 2
    assert len(result.tables) >= 2
    assert result.validation_passed is True
