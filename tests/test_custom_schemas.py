"""Tests for dynamic custom schemas."""

from docuvision.core.schemas import (
    create_dynamic_schema,
    delete_custom_schema,
    get_schema_class,
    save_custom_schema,
)


def test_create_dynamic_schema():
    fields = [
        {"name": "contract_id", "type": "string", "required": True, "description": "Legal contract number"},
        {"name": "signatory_count", "type": "integer", "required": False, "description": "Number of signers"},
        {"name": "is_active", "type": "boolean", "required": False, "description": "Active flag"},
    ]
    schema_cls = create_dynamic_schema("service_contract", fields)
    assert schema_cls.__name__ == "ServiceContractSchema"

    instance = schema_cls.model_validate(
        {
            "contract_id": "CNT-2026-99",
            "signatory_count": 3,
            "is_active": True,
        }
    )
    assert instance.contract_id == "CNT-2026-99"
    assert instance.signatory_count == 3
    assert instance.is_active is True


def test_save_and_delete_custom_schema():
    fields = [
        {"name": "bol_number", "type": "string", "required": True},
        {"name": "cargo_weight", "type": "float", "required": False},
    ]
    file_path = save_custom_schema("bill_of_lading", fields, description="Shipping document")
    assert file_path.exists()

    retrieved = get_schema_class("bill_of_lading")
    assert retrieved.__name__ == "BillOfLadingSchema"

    # Cleanup
    deleted = delete_custom_schema("bill_of_lading")
    assert deleted is True
    assert not file_path.exists()
