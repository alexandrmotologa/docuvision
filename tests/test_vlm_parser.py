"""Tests for robust VLM response parsing and repair."""

from docuvision.core.schemas import InvoiceSchema
from docuvision.vlm.parser import VLMParser


def test_extract_json_from_markdown_fences():
    parser = VLMParser()
    raw = """
    Here is the requested extraction:
    ```json
    {
      "invoice_number": "INV-777",
      "total_amount": 125.0
    }
    ```
    I hope this helps!
    """
    res = parser.parse_raw(raw)
    assert res.get("invoice_number") == "INV-777"
    assert res.get("total_amount") == 125.0


def test_repair_trailing_commas():
    parser = VLMParser()
    bad_json = """
    {
      "invoice_number": "INV-888",
      "items": [
        "A",
        "B",
      ],
      "total": 99.0,
    }
    """
    res = parser.parse_raw(bad_json)
    assert res.get("invoice_number") == "INV-888"
    assert len(res.get("items")) == 2


def test_repair_single_quotes_and_booleans():
    parser = VLMParser()
    bad_json = "{'vendor': 'Acme', 'is_paid': True, 'notes': None}"
    res = parser.parse_raw(bad_json)
    assert res.get("vendor") == "Acme"
    assert res.get("is_paid") is True
    assert res.get("notes") is None


def test_parse_and_validate():
    parser = VLMParser()
    good_raw = '{"invoice_number": "INV-001", "total_amount": 100.0, "line_items": []}'
    data, is_valid, errors = parser.parse_and_validate(good_raw, InvoiceSchema)
    assert is_valid is True
    assert len(errors) == 0
    assert data.get("invoice_number") == "INV-001"
