"""Tests for multi-sheet Excel workbook export."""

import io
from pathlib import Path
import openpyxl

from docuvision.core.models import DocumentMetadata, DocumentResult, Table, TableCell
from docuvision.pipeline.excel_exporter import ExcelExporter


def test_excel_export_three_sheets(tmp_path: Path):
    exporter = ExcelExporter()

    meta = DocumentMetadata(
        filename="test_statement.pdf",
        file_size_bytes=10240,
        total_pages=1,
        mime_type="application/pdf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        created_at="2026-10-12T12:00:00Z",
    )

    cells = [
        TableCell(row_idx=0, col_idx=0, text="Account", is_header=True),
        TableCell(row_idx=0, col_idx=1, text="Balance", is_header=True),
        TableCell(row_idx=1, col_idx=0, text="Cash", is_header=False),
        TableCell(row_idx=1, col_idx=1, text="50000.00", is_header=False, numeric_value=50000.0),
    ]

    table = Table(
        table_id="table_p1_0",
        page_number=1,
        rows=2,
        cols=2,
        headers=["Account", "Balance"],
        cells=cells,
        matrix=[["Account", "Balance"], ["Cash", "50000.00"]],
    )

    result = DocumentResult(
        metadata=meta,
        pages=[],
        tables=[table],
        structured_data={"total_assets": 50000.0, "currency": "USD"},
        schema_name="balance_sheet",
        validation_passed=True,
        validation_errors=[],
        latency_ms=120.5,
    )

    # Export to bytes
    raw_bytes = exporter.export_to_bytes(result)
    assert len(raw_bytes) > 2000

    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes))
    sheet_names = wb.sheetnames
    assert "Document Overview" in sheet_names
    assert "Extracted Tables" in sheet_names
    assert "Audit & Validation" in sheet_names

    # Check Overview Sheet Content
    ws_ov = wb["Document Overview"]
    assert ws_ov["B5"].value == "test_statement.pdf"

    # Check Tables Sheet Content
    ws_tab = wb["Extracted Tables"]
    assert ws_tab["A2"].value == "Account"
    assert ws_tab["B2"].value == "Balance"
    assert ws_tab["A3"].value == "Cash"

    # Check File writing
    out_file = tmp_path / "statement.xlsx"
    exporter.export_to_file(result, out_file)
    assert out_file.exists()
    assert out_file.stat().st_size > 2000
