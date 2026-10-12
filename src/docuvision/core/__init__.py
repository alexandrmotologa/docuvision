"""Core models, configurations, and document schemas for DocuVision."""

from docuvision.core.config import DocuVisionSettings, settings
from docuvision.core.models import (
    BoundingBox,
    DocumentMetadata,
    DocumentPage,
    DocumentResult,
    ExtractedField,
    Table,
    TableCell,
)
from docuvision.core.schemas import (
    SCHEMA_REGISTRY,
    BalanceSheetSchema,
    GenericKeyValueSchema,
    InvoiceSchema,
    LabReportSchema,
    ReceiptSchema,
    get_schema_class,
    list_available_schemas,
)

__all__ = [
    "DocuVisionSettings",
    "settings",
    "BoundingBox",
    "DocumentMetadata",
    "DocumentPage",
    "DocumentResult",
    "ExtractedField",
    "Table",
    "TableCell",
    "InvoiceSchema",
    "ReceiptSchema",
    "BalanceSheetSchema",
    "LabReportSchema",
    "GenericKeyValueSchema",
    "SCHEMA_REGISTRY",
    "get_schema_class",
    "list_available_schemas",
]
