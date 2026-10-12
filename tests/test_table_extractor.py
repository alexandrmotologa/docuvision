"""Tests for vector grid table extraction."""

from pathlib import Path

from docuvision.table.extractor import TableExtractor


def test_extract_invoice_table(sample_invoice_pdf: Path):
    extractor = TableExtractor()
    tables = extractor.extract_from_document(source=sample_invoice_pdf)

    assert len(tables) >= 1
    table = tables[0]
    assert table.rows >= 4
    assert table.cols == 4
    assert "Description" in table.headers[0]
    assert len(table.cells) == table.rows * table.cols

    # Verify Markdown export
    assert "| Description |" in table.markdown
    assert "|---|" in table.markdown or "| --- |" in table.markdown

    # Verify CSV export
    assert "Description,Quantity" in table.csv or "Description" in table.csv

    # Verify bounding box is normalized between 0.0 and 1.0
    assert table.bbox is not None
    assert 0.0 <= table.bbox.ymin <= 1.0
    assert 0.0 <= table.bbox.xmin <= 1.0
    assert 0.0 <= table.bbox.ymax <= 1.0
    assert 0.0 <= table.bbox.xmax <= 1.0


def test_extract_multipage_tables(multipage_pdf: Path):
    extractor = TableExtractor()
    tables = extractor.extract_from_document(source=multipage_pdf)

    assert len(tables) >= 2
    pages = {t.page_number for t in tables}
    assert 1 in pages
    assert 2 in pages


def test_parse_numeric():
    assert TableExtractor._parse_numeric("$1,250.50") == 1250.50
    assert TableExtractor._parse_numeric("€99.00") == 99.00
    assert TableExtractor._parse_numeric("45") == 45.0
    assert TableExtractor._parse_numeric("not-a-number") is None
