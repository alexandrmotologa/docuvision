"""Tests for document schemas and dynamic catalog."""

from docuvision.core.schemas import (
    BalanceSheetSchema,
    GenericKeyValueSchema,
    InvoiceSchema,
    LabReportSchema,
    ReceiptSchema,
    SCHEMA_REGISTRY,
    get_schema_class,
    list_available_schemas,
)


def test_schema_registry_coverage():
    assert "invoice" in SCHEMA_REGISTRY
    assert "receipt" in SCHEMA_REGISTRY
    assert "balance_sheet" in SCHEMA_REGISTRY
    assert "lab_report" in SCHEMA_REGISTRY
    assert "generic" in SCHEMA_REGISTRY


def test_get_schema_class():
    assert get_schema_class("invoice") == InvoiceSchema
    assert get_schema_class("RECEIPT") == ReceiptSchema
    assert get_schema_class("balance-sheet") == BalanceSheetSchema
    assert get_schema_class("non_existent") == GenericKeyValueSchema


def test_invoice_schema_validation():
    valid_payload = {
        "invoice_number": "INV-1001",
        "invoice_date": "2026-10-12",
        "vendor_name": "Acme Inc",
        "customer_name": "Beta LLC",
        "line_items": [
            {"description": "Product X", "quantity": 1, "unit_price": 50.0, "total_price": 50.0}
        ],
        "total_amount": 50.0,
    }
    model = InvoiceSchema.model_validate(valid_payload)
    assert model.invoice_number == "INV-1001"
    assert len(model.line_items) == 1
    assert model.total_amount == 50.0


def test_list_available_schemas():
    schemas = list_available_schemas()
    assert len(schemas) >= 5
    for name, spec in schemas.items():
        assert "title" in spec
        assert "json_schema" in spec
