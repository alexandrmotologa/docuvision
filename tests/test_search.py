"""Tests for SQLite FTS5 search index."""

from __future__ import annotations

from pathlib import Path

from docuvision.core.models import (
    DocumentMetadata,
    DocumentPage,
    DocumentResult,
    Table,
    TableCell,
)
from docuvision.search.index import DocumentSearchIndex


def _create_mock_result(
    filename: str = "test_doc.pdf",
    sha256: str = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
    content: str = "Acme Corp Quarterly Financial Statement 2026",
    structured: dict | None = None,
) -> DocumentResult:
    return DocumentResult(
        metadata=DocumentMetadata(
            filename=filename,
            file_path=f"/path/to/{filename}",
            file_size_bytes=1024,
            total_pages=1,
            mime_type="application/pdf",
            sha256_hash=sha256,
            created_at="2026-10-12T12:00:00Z",
        ),
        pages=[
            DocumentPage(
                page_number=1,
                width=612.0,
                height=792.0,
                text_content=content,
            )
        ],
        tables=[
            Table(
                table_id="tbl_1",
                page_number=1,
                headers=["Description", "Amount"],
                matrix=[["Description", "Amount"], ["Software Licensing", "$15000.00"]],
                markdown="| Description | Amount |\n| --- | --- |\n| Software Licensing | $15000.00 |",
                cells=[
                    TableCell(row_idx=0, col_idx=0, text="Description", is_header=True),
                    TableCell(row_idx=0, col_idx=1, text="Amount", is_header=True),
                    TableCell(row_idx=1, col_idx=0, text="Software Licensing"),
                    TableCell(row_idx=1, col_idx=1, text="$15000.00", numeric_value=15000.0),
                ],
            )
        ],
        structured_data=structured or {"company": "Acme Corp", "total_revenue": 15000.0},
        schema_name="balance_sheet",
    )


def test_index_and_search(tmp_path: Path):
    db_file = tmp_path / "test_search.db"
    index = DocumentSearchIndex(db_path=db_file)

    assert index.count() == 0

    doc1 = _create_mock_result(
        filename="invoice_101.pdf",
        sha256="1111111111111111111111111111111111111111111111111111111111111111",
        content="Invoice 101 for Cloud Computing Services from Global Logistics Ltd",
        structured={"invoice_id": "INV-101", "vendor": "Global Logistics"},
    )
    doc2 = _create_mock_result(
        filename="balance_sheet_2026.pdf",
        sha256="2222222222222222222222222222222222222222222222222222222222222222",
        content="Acme Corp Consolidated Balance Sheet and Cash Flows for fiscal year 2026",
        structured={"company": "Acme Corp", "net_income": 450000.0},
    )

    doc_id1 = index.index_document(doc1)
    doc_id2 = index.index_document(doc2)

    assert doc_id1 == "1111111111111111"
    assert doc_id2 == "2222222222222222"
    assert index.count() == 2

    # Search for "Cloud Computing"
    hits = index.search("Cloud Computing")
    assert len(hits) >= 1
    assert hits[0].filename == "invoice_101.pdf"
    assert "INV-101" in str(hits[0].structured_data_preview)

    # Search for "Acme Corp"
    hits = index.search("Acme Corp")
    assert len(hits) >= 1
    assert hits[0].filename == "balance_sheet_2026.pdf"

    # Search for table text: "Software Licensing"
    hits = index.search("Licensing")
    assert len(hits) >= 1

    # Empty search returns empty list
    assert index.search("   ") == []

    # Non-existent search
    assert index.search("nonexistenttermXYZ") == []


def test_index_directory(tmp_path: Path):
    db_file = tmp_path / "test_search_dir.db"
    index = DocumentSearchIndex(db_path=db_file)

    batch_dir = tmp_path / "batch_out"
    batch_dir.mkdir()

    doc = _create_mock_result(filename="receipt_99.pdf", content="Espresso Coffee Bar")
    (batch_dir / "doc1.json").write_text(doc.model_dump_json(), encoding="utf-8")
    (batch_dir / "batch_summary.json").write_text('{"summary": true}', encoding="utf-8")

    count = index.index_directory(batch_dir)
    assert count == 1
    assert index.count() == 1

    hits = index.search("Espresso")
    assert len(hits) == 1
    assert hits[0].filename == "receipt_99.pdf"


def test_delete_and_clear(tmp_path: Path):
    db_file = tmp_path / "test_ops.db"
    index = DocumentSearchIndex(db_path=db_file)

    doc = _create_mock_result()
    index.index_document(doc)
    assert index.count() == 1

    deleted = index.delete_by_hash(doc.metadata.sha256_hash)
    assert deleted is True
    assert index.count() == 0

    index.index_document(doc)
    assert index.count() == 1
    index.clear()
    assert index.count() == 0
