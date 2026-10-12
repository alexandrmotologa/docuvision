"""Predefined document schemas and dynamic schema registry for DocuVision."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Invoice Schema
# ---------------------------------------------------------------------------
class InvoiceLineItem(BaseModel):
    """Line item on a commercial invoice."""

    description: str = Field(..., description="Item or service description")
    quantity: float = Field(default=1.0, description="Quantity billed")
    unit_price: float = Field(default=0.0, description="Price per individual unit")
    total_price: float = Field(default=0.0, description="Net item total")
    sku: Optional[str] = Field(default=None, description="SKU or product code")


class InvoiceSchema(BaseModel):
    """Commercial invoice extraction schema."""

    invoice_number: Optional[str] = Field(default=None, description="Invoice reference code or identifier")
    invoice_date: Optional[str] = Field(default=None, description="Issue date (YYYY-MM-DD or raw)")
    due_date: Optional[str] = Field(default=None, description="Payment due date")
    vendor_name: Optional[str] = Field(default=None, description="Issuing vendor or seller name")
    vendor_address: Optional[str] = Field(default=None, description="Physical or billing address of vendor")
    vendor_tax_id: Optional[str] = Field(default=None, description="Vendor VAT, EIN, or tax registration")
    customer_name: Optional[str] = Field(default=None, description="Recipient customer or organization name")
    customer_address: Optional[str] = Field(default=None, description="Customer billing or shipping address")
    customer_tax_id: Optional[str] = Field(default=None, description="Customer VAT or tax ID")
    line_items: List[InvoiceLineItem] = Field(default_factory=list, description="Enumerated line items")
    subtotal: Optional[float] = Field(default=None, description="Pre-tax subtotal amount")
    tax_rate: Optional[float] = Field(default=None, description="Tax percentage rate (e.g. 19.0 or 0.19)")
    tax_amount: Optional[float] = Field(default=None, description="Total sales or VAT tax applied")
    total_amount: Optional[float] = Field(default=None, description="Grand total payable")
    currency: str = Field(default="USD", description="Currency symbol or 3-letter ISO code")
    payment_terms: Optional[str] = Field(
        default=None, description="Payment terms (e.g. Net 30, Due on Receipt)"
    )


# ---------------------------------------------------------------------------
# Receipt Schema
# ---------------------------------------------------------------------------
class ReceiptItem(BaseModel):
    """Purchased item on a point-of-sale receipt."""

    name: str = Field(..., description="Product or service label")
    quantity: float = Field(default=1.0, description="Quantity purchased")
    price: float = Field(default=0.0, description="Extended item price")


class ReceiptSchema(BaseModel):
    """Point-of-sale retail receipt schema."""

    merchant_name: Optional[str] = Field(default=None, description="Store or restaurant name")
    merchant_address: Optional[str] = Field(default=None, description="Location address")
    merchant_phone: Optional[str] = Field(default=None, description="Contact phone number")
    transaction_date: Optional[str] = Field(default=None, description="Date of purchase")
    transaction_time: Optional[str] = Field(default=None, description="Time of purchase")
    receipt_number: Optional[str] = Field(default=None, description="Receipt or ticket number")
    items: List[ReceiptItem] = Field(default_factory=list, description="Purchased items")
    subtotal: Optional[float] = Field(default=None, description="Subtotal before taxes and tip")
    tax: Optional[float] = Field(default=None, description="Sales tax amount")
    tip: Optional[float] = Field(default=None, description="Tip or gratuity")
    total: Optional[float] = Field(default=None, description="Final charged amount")
    payment_method: Optional[str] = Field(default=None, description="Card brand, cash, or auth code")


# ---------------------------------------------------------------------------
# Balance Sheet Schema
# ---------------------------------------------------------------------------
class FinancialEntry(BaseModel):
    """Individual line item in an accounting financial statement."""

    line_item: str = Field(..., description="Accounting account or category title")
    amount: float = Field(..., description="Numeric value reported")
    notes: Optional[str] = Field(default=None, description="Footnote or cross-reference")


class BalanceSheetSchema(BaseModel):
    """Corporate balance sheet and statement of financial position schema."""

    entity_name: Optional[str] = Field(default=None, description="Legal company name")
    as_of_date: Optional[str] = Field(default=None, description="Reporting date (e.g. 'December 31, 2025')")
    currency: str = Field(default="USD", description="Reporting currency")
    scale: str = Field(default="exact", description="Unit scale: 'exact', 'thousands', 'millions'")

    current_assets: List[FinancialEntry] = Field(
        default_factory=list, description="Cash, receivables, inventory"
    )
    total_current_assets: Optional[float] = Field(default=None, description="Sum of current assets")

    non_current_assets: List[FinancialEntry] = Field(
        default_factory=list, description="PP&E, goodwill, intangibles"
    )
    total_non_current_assets: Optional[float] = Field(default=None, description="Sum of non-current assets")
    total_assets: Optional[float] = Field(default=None, description="Grand total assets")

    current_liabilities: List[FinancialEntry] = Field(
        default_factory=list, description="Accounts payable, short-term debt"
    )
    total_current_liabilities: Optional[float] = Field(default=None, description="Sum of current liabilities")

    long_term_liabilities: List[FinancialEntry] = Field(
        default_factory=list, description="Bonds, long-term lease obligations"
    )
    total_long_term_liabilities: Optional[float] = Field(
        default=None, description="Sum of long-term liabilities"
    )
    total_liabilities: Optional[float] = Field(default=None, description="Grand total liabilities")

    stockholders_equity: List[FinancialEntry] = Field(
        default_factory=list, description="Retained earnings, common stock"
    )
    total_equity: Optional[float] = Field(default=None, description="Total shareholders equity")
    total_liabilities_and_equity: Optional[float] = Field(
        default=None, description="Total liabilities plus equity"
    )


# ---------------------------------------------------------------------------
# Clinical / Medical Lab Report Schema
# ---------------------------------------------------------------------------
class LabTestResult(BaseModel):
    """Specific biomarker or test line on a clinical report."""

    test_name: str = Field(..., description="Biomarker or panel item name")
    result_value: str = Field(..., description="Observed quantitative or qualitative result")
    units: Optional[str] = Field(default=None, description="Measurement units (e.g. 'mg/dL', 'mmol/L')")
    reference_range: Optional[str] = Field(default=None, description="Normal biological reference range")
    flag: Optional[str] = Field(
        default=None, description="Abnormal indicator: 'Normal', 'High', 'Low', 'Critical'"
    )


class LabReportSchema(BaseModel):
    """Clinical laboratory test results and diagnostic panel schema."""

    patient_name: Optional[str] = Field(default=None, description="Patient full name")
    patient_id: Optional[str] = Field(default=None, description="Patient MRN or identification number")
    patient_dob: Optional[str] = Field(default=None, description="Patient date of birth")
    collection_date: Optional[str] = Field(default=None, description="Specimen collection timestamp")
    laboratory_name: Optional[str] = Field(default=None, description="Diagnostic facility name")
    ordering_physician: Optional[str] = Field(default=None, description="Physician who ordered testing")
    tests: List[LabTestResult] = Field(default_factory=list, description="Array of test results")
    clinical_notes: Optional[str] = Field(
        default=None, description="Pathologist comments or diagnostic impressions"
    )


# ---------------------------------------------------------------------------
# Generic Flexible Schema
# ---------------------------------------------------------------------------
class GenericKeyValueSchema(BaseModel):
    """Flexible key-value and summary schema for untyped documents."""

    document_title: Optional[str] = Field(default=None, description="Deduced document title")
    document_type: Optional[str] = Field(default=None, description="Document categorization")
    summary: Optional[str] = Field(default=None, description="High-level executive summary")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted key-value attributes")
    key_metrics: Dict[str, float] = Field(default_factory=dict, description="Identified numerical metrics")


# ---------------------------------------------------------------------------
# Schema Registry & Dynamic Custom Schema Engine
# ---------------------------------------------------------------------------
SCHEMA_REGISTRY: Dict[str, Type[BaseModel]] = {
    "invoice": InvoiceSchema,
    "receipt": ReceiptSchema,
    "balance_sheet": BalanceSheetSchema,
    "lab_report": LabReportSchema,
    "generic": GenericKeyValueSchema,
}

CUSTOM_SCHEMAS_DIR = Path("./.docuvision/schemas")


def create_dynamic_schema(
    schema_name: str,
    fields: List[Dict[str, Any]],
    docstring: Optional[str] = None,
) -> Type[BaseModel]:
    """Dynamically construct a Pydantic model class from field definitions."""
    from pydantic import create_model

    field_definitions: Dict[str, Any] = {}

    type_mapping = {
        "string": (Optional[str], None),
        "str": (Optional[str], None),
        "number": (Optional[float], None),
        "float": (Optional[float], None),
        "integer": (Optional[int], None),
        "int": (Optional[int], None),
        "boolean": (Optional[bool], None),
        "bool": (Optional[bool], None),
        "list_strings": (List[str], []),
        "list_objects": (List[Dict[str, Any]], []),
        "dict": (Dict[str, Any], {}),
    }

    for f in fields:
        fname = f.get("name", "").strip().replace(" ", "_")
        if not fname:
            continue
        ftype_str = f.get("type", "string").lower().strip()
        fdesc = f.get("description", "")
        frequired = bool(f.get("required", False))

        type_tuple = type_mapping.get(ftype_str, (Optional[str], None))
        python_type, default_val = type_tuple

        if frequired:
            field_definitions[fname] = (python_type, Field(..., description=fdesc))
        else:
            if isinstance(default_val, list):
                field_definitions[fname] = (python_type, Field(default_factory=list, description=fdesc))
            elif isinstance(default_val, dict):
                field_definitions[fname] = (python_type, Field(default_factory=dict, description=fdesc))
            else:
                field_definitions[fname] = (python_type, Field(default=default_val, description=fdesc))

    model_name = "".join(part.capitalize() for part in schema_name.replace("-", "_").split("_")) + "Schema"
    dynamic_model = create_model(model_name, **field_definitions)
    dynamic_model.__doc__ = docstring or f"Custom dynamic schema for {schema_name}"
    return dynamic_model


def save_custom_schema(schema_name: str, fields: List[Dict[str, Any]], description: str = "") -> Path:
    """Persist a custom schema definition as JSON and register into runtime."""
    import json

    CUSTOM_SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    target_file = CUSTOM_SCHEMAS_DIR / f"{schema_name.lower().strip()}.json"

    payload = {
        "name": schema_name.lower().strip(),
        "description": description,
        "fields": fields,
    }
    target_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # Register into runtime
    model_cls = create_dynamic_schema(schema_name, fields, docstring=description)
    SCHEMA_REGISTRY[schema_name.lower().strip()] = model_cls
    return target_file


def load_custom_schemas() -> None:
    """Load all persisted custom schemas from disk into SCHEMA_REGISTRY."""
    import json

    if not CUSTOM_SCHEMAS_DIR.exists():
        return

    for f in CUSTOM_SCHEMAS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            s_name = data.get("name") or f.stem
            s_desc = data.get("description", "")
            s_fields = data.get("fields", [])
            model_cls = create_dynamic_schema(s_name, s_fields, docstring=s_desc)
            SCHEMA_REGISTRY[s_name.lower().strip()] = model_cls
        except Exception:
            pass


def delete_custom_schema(schema_name: str) -> bool:
    """Delete a custom schema from disk and unregister."""
    target_file = CUSTOM_SCHEMAS_DIR / f"{schema_name.lower().strip()}.json"
    if target_file.exists():
        target_file.unlink()
        SCHEMA_REGISTRY.pop(schema_name.lower().strip(), None)
        return True
    return False


# Initial load of custom schemas
load_custom_schemas()


def get_schema_class(name: str) -> Type[BaseModel]:
    """Retrieve Pydantic schema class by name or default to generic."""
    normalized = name.lower().strip().replace("-", "_").replace(" ", "_")
    if normalized not in SCHEMA_REGISTRY:
        load_custom_schemas()
    return SCHEMA_REGISTRY.get(normalized, GenericKeyValueSchema)


def list_available_schemas() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of registered schema names and their JSON schema specs."""
    load_custom_schemas()
    result = {}
    for name, model_cls in SCHEMA_REGISTRY.items():
        result[name] = {
            "title": model_cls.__name__,
            "description": model_cls.__doc__ or "",
            "json_schema": model_cls.model_json_schema(),
            "is_custom": (CUSTOM_SCHEMAS_DIR / f"{name}.json").exists(),
        }
    return result
