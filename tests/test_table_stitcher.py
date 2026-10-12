"""Tests for multi-page table stitcher."""

from docuvision.core.models import Table, TableCell
from docuvision.table.stitcher import MultiPageTableStitcher


def test_stitch_compatible_tables():
    stitcher = MultiPageTableStitcher()

    # Table on Page 1
    t1 = Table(
        table_id="table_p1_0",
        page_number=1,
        rows=3,
        cols=2,
        headers=["Item", "Cost"],
        matrix=[["Item", "Cost"], ["Widget A", "10.00"], ["Widget B", "20.00"]],
        cells=[
            TableCell(row_idx=0, col_idx=0, text="Item"),
            TableCell(row_idx=0, col_idx=1, text="Cost"),
            TableCell(row_idx=1, col_idx=0, text="Widget A"),
            TableCell(row_idx=1, col_idx=1, text="10.00"),
            TableCell(row_idx=2, col_idx=0, text="Widget B"),
            TableCell(row_idx=2, col_idx=1, text="20.00"),
        ],
    )

    # Table on Page 2 with repeated header
    t2 = Table(
        table_id="table_p2_0",
        page_number=2,
        rows=3,
        cols=2,
        headers=["Item", "Cost"],
        matrix=[["Item", "Cost"], ["Widget C", "30.00"], ["Widget D", "40.00"]],
        cells=[
            TableCell(row_idx=0, col_idx=0, text="Item"),
            TableCell(row_idx=0, col_idx=1, text="Cost"),
            TableCell(row_idx=1, col_idx=0, text="Widget C"),
            TableCell(row_idx=1, col_idx=1, text="30.00"),
            TableCell(row_idx=2, col_idx=0, text="Widget D"),
            TableCell(row_idx=2, col_idx=1, text="40.00"),
        ],
    )

    stitched = stitcher.stitch_tables([t1, t2])
    assert len(stitched) == 1
    united = stitched[0]
    # Header row + 2 rows from p1 + 2 rows from p2 = 5 total rows
    assert united.rows == 5
    assert united.cols == 2
    assert united.headers == ["Item", "Cost"]
    assert united.matrix[1] == ["Widget A", "10.00"]
    assert united.matrix[3] == ["Widget C", "30.00"]
    assert united.matrix[4] == ["Widget D", "40.00"]


def test_stitch_incompatible_tables():
    stitcher = MultiPageTableStitcher()

    t1 = Table(
        table_id="table_p1_0",
        page_number=1,
        rows=2,
        cols=2,
        headers=["Item", "Cost"],
        matrix=[["Item", "Cost"], ["Widget A", "10.00"]],
    )

    t2 = Table(
        table_id="table_p2_0",
        page_number=2,
        rows=2,
        cols=3,
        headers=["Department", "Manager", "Budget"],
        matrix=[["Department", "Manager", "Budget"], ["Engineering", "Alice", "100k"]],
    )

    stitched = stitcher.stitch_tables([t1, t2])
    assert len(stitched) == 2
