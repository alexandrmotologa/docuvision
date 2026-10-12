"""Tests for arithmetic reconciliation engine."""

from docuvision.table.reconciler import TableReconciler


def test_reconcile_valid_invoice():
    reconciler = TableReconciler(tolerance=0.05)
    data = {
        "line_items": [
            {"description": "SSD Drive", "quantity": 2, "unit_price": 45.0, "total_price": 90.0},
            {"description": "Server", "quantity": 1, "unit_price": 350.0, "total_price": 350.0},
        ],
        "subtotal": 440.0,
        "total_amount": 484.0,
    }
    report = reconciler.reconcile_invoice(data)
    assert report.passed is True
    assert len(report.discrepancies) == 0
    assert report.computed_sum == 440.0


def test_reconcile_invalid_line_item_math():
    reconciler = TableReconciler(tolerance=0.05)
    data = {
        "line_items": [
            {
                "description": "SSD Drive",
                "quantity": 2,
                "unit_price": 45.0,
                "total_price": 120.0,
            },  # Math error: 2 * 45 != 120
        ],
        "subtotal": 120.0,
    }
    report = reconciler.reconcile_invoice(data)
    assert report.passed is False
    assert len(report.discrepancies) == 1
    assert "qty (2.0) * unit_price (45.0)" in report.discrepancies[0]


def test_reconcile_subtotal_mismatch():
    reconciler = TableReconciler(tolerance=0.05)
    data = {
        "line_items": [
            {"description": "Item A", "quantity": 1, "unit_price": 100.0, "total_price": 100.0},
            {"description": "Item B", "quantity": 1, "unit_price": 200.0, "total_price": 200.0},
        ],
        "subtotal": 350.0,  # Reported subtotal 350 != computed 300
    }
    report = reconciler.reconcile_invoice(data)
    assert report.passed is False
    assert any("Subtotal discrepancy" in d for d in report.discrepancies)


def test_reconcile_balance_sheet():
    reconciler = TableReconciler(tolerance=0.05)
    # Balanced
    valid_data = {
        "total_assets": 1000000.0,
        "total_liabilities": 400000.0,
        "total_equity": 600000.0,
        "total_liabilities_and_equity": 1000000.0,
    }
    valid_report = reconciler.reconcile_balance_sheet(valid_data)
    assert valid_report.passed is True

    # Imbalanced
    invalid_data = {
        "total_assets": 1000000.0,
        "total_liabilities": 400000.0,
        "total_equity": 500000.0,
        "total_liabilities_and_equity": 900000.0,
    }
    invalid_report = reconciler.reconcile_balance_sheet(invalid_data)
    assert invalid_report.passed is False
    assert len(invalid_report.discrepancies) >= 1
