"""DocuVision - Zero-cloud multimodal document intelligence pipeline.

Converts multi-page PDFs, scans, receipts, and balance sheets into validated JSON
and Markdown tables using local Vision-Language Models.
"""

__version__ = "0.1.0"

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
]
