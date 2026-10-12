"""Arithmetic cross-validation and line-item reconciliation for extracted documents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from docuvision.core.models import Table


class ReconciliationReport(BaseModel):
    """Result of cross-validating extracted line items against aggregate schema figures."""

    passed: bool = Field(default=True, description="True if no arithmetic discrepancy was detected")
    discrepancies: List[str] = Field(
        default_factory=list, description="Specific arithmetic deviation warnings"
    )
    computed_sum: float = Field(default=0.0, description="Sum calculated from item rows")
    reported_total: Optional[float] = Field(
        default=None, description="Reported total or subtotal from document"
    )
    margin_error: float = Field(
        default=0.0, description="Absolute difference between computed and reported amounts"
    )


class TableReconciler:
    """Verifies internal arithmetic consistency in financial tables, invoices, and receipts."""

    def __init__(self, tolerance: float = 0.05) -> None:
        self.tolerance = tolerance

    def reconcile_invoice(
        self,
        structured_data: Dict[str, Any],
        tables: Optional[List[Table]] = None,
    ) -> ReconciliationReport:
        """Validate line items arithmetic in invoice JSON structures."""
        discrepancies: List[str] = []
        line_items = structured_data.get("line_items", [])

        computed_sum = 0.0
        for idx, item in enumerate(line_items):
            if not isinstance(item, dict):
                continue

            desc = item.get("description", f"Item #{idx + 1}")
            qty = float(item.get("quantity") or 1.0)
            unit_price = float(item.get("unit_price") or 0.0)
            total_price = float(item.get("total_price") or 0.0)

            computed_item_total = round(qty * unit_price, 2)
            if total_price > 0 and abs(computed_item_total - total_price) > self.tolerance:
                discrepancies.append(
                    f"Line '{desc}': qty ({qty}) * unit_price ({unit_price}) = {computed_item_total}, but line total reported is {total_price}"
                )

            computed_sum += total_price if total_price > 0 else computed_item_total

        computed_sum = round(computed_sum, 2)

        # Compare with subtotal or total_amount if available
        reported_subtotal = structured_data.get("subtotal")
        reported_total = structured_data.get("total_amount")

        target_total = reported_subtotal if reported_subtotal is not None else reported_total

        margin_error = 0.0
        if target_total is not None and len(line_items) > 0:
            target_val = round(float(target_total), 2)
            margin_error = round(abs(computed_sum - target_val), 2)
            if margin_error > self.tolerance:
                discrepancies.append(
                    f"Subtotal discrepancy: calculated item sum is {computed_sum}, but reported document amount is {target_val} (diff: {margin_error})"
                )

        passed = len(discrepancies) == 0
        return ReconciliationReport(
            passed=passed,
            discrepancies=discrepancies,
            computed_sum=computed_sum,
            reported_total=float(target_total) if target_total is not None else None,
            margin_error=margin_error,
        )

    def reconcile_balance_sheet(
        self,
        structured_data: Dict[str, Any],
    ) -> ReconciliationReport:
        """Validate accounting equation: Total Assets == Total Liabilities + Total Equity."""
        discrepancies: List[str] = []

        total_assets = structured_data.get("total_assets")
        total_liabilities = structured_data.get("total_liabilities")
        total_equity = structured_data.get("total_equity")
        total_liab_equity = structured_data.get("total_liabilities_and_equity")

        computed_sum = 0.0
        margin_error = 0.0

        if total_liabilities is not None and total_equity is not None:
            computed_sum = round(float(total_liabilities) + float(total_equity), 2)
            if total_liab_equity is not None:
                reported_liab_eq = round(float(total_liab_equity), 2)
                if abs(computed_sum - reported_liab_eq) > self.tolerance:
                    discrepancies.append(
                        f"Liabilities + Equity mismatch: {total_liabilities} + {total_equity} = {computed_sum}, but reported total is {reported_liab_eq}"
                    )

            if total_assets is not None:
                assets_val = round(float(total_assets), 2)
                margin_error = round(abs(assets_val - computed_sum), 2)
                if margin_error > self.tolerance:
                    discrepancies.append(
                        f"Balance Sheet imbalance: Total Assets ({assets_val}) does not match Total Liabilities + Equity ({computed_sum})"
                    )

        passed = len(discrepancies) == 0
        return ReconciliationReport(
            passed=passed,
            discrepancies=discrepancies,
            computed_sum=computed_sum,
            reported_total=float(total_assets) if total_assets is not None else None,
            margin_error=margin_error,
        )
