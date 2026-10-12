"""Pytest test fixtures and authentic synthetic PDF generator."""

from __future__ import annotations

import io
from pathlib import Path
import pymupdf
import pytest


def create_sample_invoice_pdf() -> bytes:
    """Generate an authentic PDF invoice with vector lines, text, and tables."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4 standard

    # 1. Header & Title
    page.insert_text((50, 60), "INVOICE", fontsize=24, color=(0.1, 0.2, 0.4))
    page.insert_text((50, 90), "Invoice Number: INV-2026-9042", fontsize=11)
    page.insert_text((50, 105), "Date: 2026-10-12", fontsize=11)
    page.insert_text((50, 120), "Due Date: 2026-11-12", fontsize=11)

    page.insert_text((350, 90), "Vendor: Acme Cloud Services Inc.", fontsize=11)
    page.insert_text((350, 105), "Customer: CyberTech Industries", fontsize=11)
    page.insert_text((350, 120), "Currency: USD", fontsize=11)

    # 2. Table Layout
    table_top = 160
    table_bottom = 280
    left = 50
    right = 545

    col_widths = [245, 80, 80, 90]  # Sum = 495
    col_x = [left]
    for w in col_widths:
        col_x.append(col_x[-1] + w)

    row_y = [table_top, table_top + 25, table_top + 55, table_top + 85, table_bottom]

    # Draw table bounding rectangle
    page.draw_rect(pymupdf.Rect(left, table_top, right, table_bottom), color=(0.3, 0.3, 0.3), width=1)

    # Draw horizontal grid lines
    for y in row_y[1:-1]:
        page.draw_line(pymupdf.Point(left, y), pymupdf.Point(right, y), color=(0.7, 0.7, 0.7), width=0.5)

    # Draw vertical grid lines
    for x in col_x[1:-1]:
        page.draw_line(pymupdf.Point(x, table_top), pymupdf.Point(x, table_bottom), color=(0.7, 0.7, 0.7), width=0.5)

    # Header Row
    headers = ["Description", "Quantity", "Unit Price", "Total Price"]
    for i, h in enumerate(headers):
        page.insert_text((col_x[i] + 8, table_top + 17), h, fontsize=10, color=(0.1, 0.1, 0.1))

    # Data Rows
    rows_data = [
        ["Cloud Storage SSD 500GB", "2", "45.00", "90.00"],
        ["Dedicated Database Cluster", "1", "350.00", "350.00"],
        ["Security WAF Protection", "1", "60.00", "60.00"],
    ]

    for r_idx, row in enumerate(rows_data):
        y_text = row_y[r_idx + 1] + 18
        for c_idx, val in enumerate(row):
            page.insert_text((col_x[c_idx] + 8, y_text), val, fontsize=10)

    # Totals
    page.insert_text((380, 310), "Subtotal: $500.00", fontsize=11)
    page.insert_text((380, 330), "Tax (10%): $50.00", fontsize=11)
    page.insert_text((380, 350), "Total Amount: $550.00", fontsize=12, color=(0.1, 0.2, 0.4))

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def create_multipage_pdf() -> bytes:
    """Generate a 2-page document with distinct tables on each page."""
    doc = pymupdf.open()

    # Page 1
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((50, 50), "Quarterly Financial Overview - Page 1", fontsize=16)
    p1.draw_rect(pymupdf.Rect(50, 100, 500, 200), color=(0.2, 0.2, 0.2))
    p1.draw_line(pymupdf.Point(50, 130), pymupdf.Point(500, 130))
    p1.draw_line(pymupdf.Point(275, 100), pymupdf.Point(275, 200))
    p1.insert_text((60, 120), "Metric", fontsize=11)
    p1.insert_text((285, 120), "Q1 Actual", fontsize=11)
    p1.insert_text((60, 160), "Revenue", fontsize=10)
    p1.insert_text((285, 160), "$1,250,000", fontsize=10)

    # Page 2
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((50, 50), "Operating Expenses - Page 2", fontsize=16)
    p2.draw_rect(pymupdf.Rect(50, 100, 500, 200), color=(0.2, 0.2, 0.2))
    p2.draw_line(pymupdf.Point(50, 130), pymupdf.Point(500, 130))
    p2.draw_line(pymupdf.Point(275, 100), pymupdf.Point(275, 200))
    p2.insert_text((60, 120), "Category", fontsize=11)
    p2.insert_text((285, 120), "Budget", fontsize=11)
    p2.insert_text((60, 160), "Research & Development", fontsize=10)
    p2.insert_text((285, 160), "$450,000", fontsize=10)

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


@pytest.fixture
def sample_invoice_bytes() -> bytes:
    return create_sample_invoice_pdf()


@pytest.fixture
def sample_invoice_pdf(tmp_path: Path, sample_invoice_bytes: bytes) -> Path:
    pdf_file = tmp_path / "sample_invoice.pdf"
    pdf_file.write_bytes(sample_invoice_bytes)
    return pdf_file


@pytest.fixture
def multipage_pdf(tmp_path: Path) -> Path:
    pdf_file = tmp_path / "multipage_report.pdf"
    pdf_file.write_bytes(create_multipage_pdf())
    return pdf_file
