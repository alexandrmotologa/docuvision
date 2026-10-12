"""Multi-page table continuity detection and stitching engine."""

from __future__ import annotations

import difflib
from typing import List
from docuvision.core.models import Table, TableCell


class MultiPageTableStitcher:
    """Detects and unifies continuous tables that span across multiple PDF pages."""

    def __init__(self, header_similarity_threshold: float = 0.80) -> None:
        self.header_similarity_threshold = header_similarity_threshold

    @staticmethod
    def _normalize_header(header: str) -> str:
        """Strip punctuation and whitespace for fuzzy comparison."""
        return "".join(c.lower() for c in header if c.isalnum())

    def _are_headers_compatible(self, h1: List[str], h2: List[str]) -> bool:
        """Check if two header lists have matching column counts and similar labels."""
        if len(h1) != len(h2) or len(h1) == 0:
            return False

        norm1 = [self._normalize_header(h) for h in h1]
        norm2 = [self._normalize_header(h) for h in h2]

        matches = sum(
            1 for a, b in zip(norm1, norm2)
            if a == b or difflib.SequenceMatcher(None, a, b).ratio() >= self.header_similarity_threshold
        )
        return (matches / float(len(h1))) >= self.header_similarity_threshold

    def stitch_tables(self, tables: List[Table]) -> List[Table]:
        """Group and stitch sequential tables from adjacent pages into unified tables."""
        if len(tables) <= 1:
            return list(tables)

        stitched: List[Table] = []
        i = 0
        while i < len(tables):
            current = tables[i]
            unified_matrix = [list(r) for r in current.matrix]
            unified_cells = list(current.cells)
            total_rows = current.rows

            j = i + 1
            while j < len(tables):
                nxt = tables[j]
                # Must be on consecutive pages
                if nxt.page_number != current.page_number + (j - i):
                    break

                if self._are_headers_compatible(current.headers, nxt.headers):
                    # Table continues on next page: append data rows, skipping repeated header
                    subsequent_rows = nxt.matrix[1:] if len(nxt.matrix) > 1 else []
                    for r_offset, row in enumerate(subsequent_rows):
                        unified_matrix.append(list(row))
                        new_row_idx = total_rows + r_offset
                        for c_idx, val in enumerate(row):
                            unified_cells.append(
                                TableCell(
                                    row_idx=new_row_idx,
                                    col_idx=c_idx,
                                    text=val,
                                    is_header=False,
                                )
                            )
                    total_rows += len(subsequent_rows)
                    j += 1
                else:
                    break

            if j > i + 1:
                # Tables were stitched
                stitched_table = Table(
                    table_id=f"{current.table_id}_stitched_to_p{tables[j-1].page_number}",
                    page_number=current.page_number,
                    rows=len(unified_matrix),
                    cols=current.cols,
                    headers=current.headers,
                    cells=unified_cells,
                    matrix=unified_matrix,
                    bbox=current.bbox,
                    confidence=min(current.confidence, min(t.confidence for t in tables[i:j])),
                )
                stitched_table.markdown = stitched_table.compute_markdown()
                stitched_table.csv = stitched_table.compute_csv()
                stitched.append(stitched_table)
                i = j
            else:
                stitched.append(current)
                i += 1

        return stitched
