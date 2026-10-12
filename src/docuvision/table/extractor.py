"""Deterministic and layout-aware table extraction engine using vector analysis."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Union

import pymupdf

from docuvision.core.config import DocuVisionSettings, settings as default_settings
from docuvision.core.models import BoundingBox, Table, TableCell


class TableExtractor:
    """Extracts tabular structures from document pages using vector lines and text grids."""

    def __init__(self, settings: Optional[DocuVisionSettings] = None) -> None:
        self.settings = settings or default_settings

    @staticmethod
    def _parse_numeric(text: str) -> Optional[float]:
        """Attempt to parse a currency or numeric string into a float."""
        if not text:
            return None
        # Remove currency symbols and formatting commas
        cleaned = re.sub(r"[^\d.-]", "", text.replace(",", ""))
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None

    def extract_from_page(
        self,
        page: pymupdf.Page,
        page_number: int,
    ) -> List[Table]:
        """Extract all tables present on a given PyMuPDF page."""
        width = float(page.rect.width)
        height = float(page.rect.height)
        tables: List[Table] = []

        try:
            tab_finder = page.find_tables()
        except Exception:
            return []

        for idx, tab in enumerate(tab_finder):
            raw_matrix = tab.extract()
            if not raw_matrix or len(raw_matrix) == 0:
                continue

            # Clean and sanitize cells
            clean_matrix: List[List[str]] = []
            for row in raw_matrix:
                clean_row = [str(c or "").strip() for c in row]
                # Filter out completely blank ghost rows
                if any(c != "" for c in clean_row):
                    clean_matrix.append(clean_row)

            if not clean_matrix:
                continue

            # Normalize column count across all rows
            max_cols = max(len(r) for r in clean_matrix)
            uniform_matrix = [r + [""] * (max_cols - len(r)) for r in clean_matrix]

            headers = [h if h else f"Column_{i+1}" for i, h in enumerate(uniform_matrix[0])]

            # Calculate normalized bounding box
            x0, y0, x1, y1 = tab.bbox
            norm_box = BoundingBox(
                ymin=max(0.0, min(1.0, y0 / height)),
                xmin=max(0.0, min(1.0, x0 / width)),
                ymax=max(0.0, min(1.0, y1 / height)),
                xmax=max(0.0, min(1.0, x1 / width)),
                page=page_number,
                label=f"table_p{page_number}_{idx}",
                confidence=1.0,
            )

            cells: List[TableCell] = []
            for r_idx, row in enumerate(uniform_matrix):
                for c_idx, val in enumerate(row):
                    is_header = r_idx == 0
                    num_val = self._parse_numeric(val)
                    cells.append(
                        TableCell(
                            row_idx=r_idx,
                            col_idx=c_idx,
                            text=val,
                            is_header=is_header,
                            numeric_value=num_val,
                        )
                    )

            table_obj = Table(
                table_id=f"table_p{page_number}_{idx}",
                page_number=page_number,
                rows=len(uniform_matrix),
                cols=max_cols,
                headers=headers,
                cells=cells,
                matrix=uniform_matrix,
                bbox=norm_box,
                confidence=1.0,
            )
            table_obj.markdown = table_obj.compute_markdown()
            table_obj.csv = table_obj.compute_csv()
            tables.append(table_obj)

        return tables

    def extract_from_document(
        self,
        source: Union[str, Path, bytes],
    ) -> List[Table]:
        """Extract all tables across every page of a multi-page PDF document."""
        if isinstance(source, (str, Path)):
            file_bytes = Path(source).read_bytes()
        else:
            file_bytes = source

        all_tables: List[Table] = []
        with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
            for page_idx, page in enumerate(doc):
                page_num = page_idx + 1
                page_tables = self.extract_from_page(page, page_number=page_num)
                all_tables.extend(page_tables)

        return all_tables
