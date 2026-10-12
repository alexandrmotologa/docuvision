"""Data transfer objects and core domain models for DocuVision."""

from __future__ import annotations

import csv
import io
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Bounding box representing a rectangular region on a document page.

    Normalized coordinates run from 0.0 (top/left) to 1.0 (bottom/right).
    """

    ymin: float = Field(..., ge=0.0, le=1.0, description="Top edge (normalized 0.0 - 1.0)")
    xmin: float = Field(..., ge=0.0, le=1.0, description="Left edge (normalized 0.0 - 1.0)")
    ymax: float = Field(..., ge=0.0, le=1.0, description="Bottom edge (normalized 0.0 - 1.0)")
    xmax: float = Field(..., ge=0.0, le=1.0, description="Right edge (normalized 0.0 - 1.0)")
    page: int = Field(default=1, ge=1, description="Page index (1-indexed)")
    label: Optional[str] = Field(default=None, description="Semantic label (e.g. 'table', 'total_amount')")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Detection confidence")

    def to_pixels(self, width: float, height: float) -> tuple[float, float, float, float]:
        """Convert normalized coordinates to absolute pixels (x0, y0, x1, y1)."""
        return (
            self.xmin * width,
            self.ymin * height,
            self.xmax * width,
            self.ymax * height,
        )

    def area(self) -> float:
        """Calculate normalized box area."""
        return max(0.0, self.xmax - self.xmin) * max(0.0, self.ymax - self.ymin)

    def intersection_over_union(self, other: "BoundingBox") -> float:
        """Compute IoU overlap between two bounding boxes on the same page."""
        if self.page != other.page:
            return 0.0

        ixmin = max(self.xmin, other.xmin)
        iymin = max(self.ymin, other.ymin)
        ixmax = min(self.xmax, other.xmax)
        iymax = min(self.ymax, other.ymax)

        iw = max(0.0, ixmax - ixmin)
        ih = max(0.0, iymax - iymin)
        inter_area = iw * ih

        union_area = self.area() + other.area() - inter_area
        if union_area <= 0:
            return 0.0
        return inter_area / union_area


class TableCell(BaseModel):
    """Individual cell inside a detected table."""

    row_idx: int = Field(..., ge=0, description="Zero-based row index")
    col_idx: int = Field(..., ge=0, description="Zero-based column index")
    row_span: int = Field(default=1, ge=1, description="Number of rows spanned")
    col_span: int = Field(default=1, ge=1, description="Number of columns spanned")
    text: str = Field(default="", description="Sanitized text content")
    bbox: Optional[BoundingBox] = Field(default=None, description="Cell bounding box")
    is_header: bool = Field(default=False, description="Flag indicating header cell")
    numeric_value: Optional[float] = Field(default=None, description="Parsed numeric value if scalar")


class Table(BaseModel):
    """Structured table representation with markdown, CSV, and matrix exporters."""

    table_id: str = Field(..., description="Unique table identifier (e.g. 'table_p1_0')")
    page_number: int = Field(..., ge=1, description="Page number where the table originates")
    rows: int = Field(default=0, ge=0, description="Number of rows")
    cols: int = Field(default=0, ge=0, description="Number of columns")
    headers: List[str] = Field(default_factory=list, description="Header column names")
    cells: List[TableCell] = Field(default_factory=list, description="Flat list of cells")
    matrix: List[List[str]] = Field(default_factory=list, description="2D string grid representation")
    markdown: str = Field(default="", description="Rendered Markdown table")
    csv: str = Field(default="", description="Rendered CSV string")
    bbox: Optional[BoundingBox] = Field(default=None, description="Table boundary box")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")

    def to_dict_records(self) -> List[dict[str, str]]:
        """Convert matrix rows into dictionaries using headers as keys."""
        if not self.matrix or len(self.matrix) < 2:
            return []

        header_row = [h.strip() or f"col_{i}" for i, h in enumerate(self.matrix[0])]
        records: List[dict[str, str]] = []
        for row in self.matrix[1:]:
            record = {}
            for col_idx, key in enumerate(header_row):
                val = row[col_idx] if col_idx < len(row) else ""
                record[key] = val
            records.append(record)
        return records

    def compute_markdown(self) -> str:
        """Format 2D matrix into a standard Markdown table."""
        if not self.matrix:
            return ""

        headers = self.matrix[0]
        sanitized_headers = [h.replace("|", "\\|").strip() or " " for h in headers]
        header_line = "| " + " | ".join(sanitized_headers) + " |"
        sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"

        body_lines = []
        for row in self.matrix[1:]:
            padded_row = list(row) + [""] * (len(headers) - len(row))
            clean_cells = [c.replace("|", "\\|").strip() for c in padded_row[: len(headers)]]
            body_lines.append("| " + " | ".join(clean_cells) + " |")

        return "\n".join([header_line, sep_line] + body_lines)

    def compute_csv(self) -> str:
        """Format 2D matrix into CSV text."""
        if not self.matrix:
            return ""
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerows(self.matrix)
        return out.getvalue()


class ExtractedField(BaseModel):
    """Key-value field extracted from document text or visual regions."""

    name: str = Field(..., description="Field identifier in target schema")
    value: Any = Field(default=None, description="Extracted and parsed value")
    raw_text: Optional[str] = Field(default=None, description="Original unparsed string")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")
    bbox: Optional[BoundingBox] = Field(default=None, description="Location coordinates")
    page_number: int = Field(default=1, ge=1, description="Page number")


class DocumentPage(BaseModel):
    """Rasterized and parsed page of a document."""

    page_number: int = Field(..., ge=1, description="1-indexed page number")
    width: float = Field(..., ge=0.0, description="Page width in points")
    height: float = Field(..., ge=0.0, description="Page height in points")
    dpi: int = Field(default=200, description="Rasterization resolution")
    text_content: str = Field(default="", description="Extracted raw text")
    tables: List[Table] = Field(default_factory=list, description="Detected tables on this page")
    image_base64: Optional[str] = Field(
        default=None, description="Base64-encoded PNG image for VLM consumption"
    )
    image_path: Optional[str] = Field(default=None, description="Optional path to cached page image")
    char_count: int = Field(default=0, ge=0, description="Character count")
    word_count: int = Field(default=0, ge=0, description="Word count")


class DocumentMetadata(BaseModel):
    """File metadata, cryptographic hash, and document statistics."""

    filename: str = Field(..., description="Original filename")
    file_path: Optional[str] = Field(default=None, description="Disk path if local")
    file_size_bytes: int = Field(..., ge=0, description="Size in bytes")
    total_pages: int = Field(..., ge=1, description="Total number of pages")
    mime_type: str = Field(default="application/pdf", description="MIME format")
    sha256_hash: str = Field(..., description="SHA-256 content checksum")
    created_at: str = Field(..., description="ISO 8601 timestamp")


class DocumentResult(BaseModel):
    """Complete extraction artifact containing pages, tables, schema JSON, and metrics."""

    metadata: DocumentMetadata
    pages: List[DocumentPage] = Field(default_factory=list)
    tables: List[Table] = Field(default_factory=list)
    structured_data: dict[str, Any] = Field(default_factory=dict, description="Validated schema JSON payload")
    schema_name: str = Field(default="generic", description="Target extraction schema applied")
    validation_passed: bool = Field(default=True, description="Schema and arithmetic validation status")
    validation_errors: List[str] = Field(
        default_factory=list, description="List of schema or math discrepancy warnings"
    )
    markdown_summary: str = Field(default="", description="Human-readable markdown summary")
    vlm_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Inference token count and provider stats"
    )
    latency_ms: float = Field(
        default=0.0, ge=0.0, description="Total pipeline processing latency in milliseconds"
    )
