"""Tests for Typer CLI commands."""

from pathlib import Path
from typer.testing import CliRunner
from docuvision.cli import app

runner = CliRunner()


def test_cli_help():
    res = runner.invoke(app, ["--help"])
    assert res.exit_code == 0
    assert "Zero-cloud multimodal document intelligence" in res.output


def test_cli_schemas():
    res = runner.invoke(app, ["schemas"])
    assert res.exit_code == 0
    assert "InvoiceSchema" in res.output
    assert "BalanceSheetSchema" in res.output


def test_cli_check():
    res = runner.invoke(app, ["check"])
    assert res.exit_code == 0
    assert "PyMuPDF" in res.output


def test_cli_rasterize(sample_invoice_pdf: Path, tmp_path: Path):
    out_dir = tmp_path / "cli_pages"
    res = runner.invoke(app, ["rasterize", str(sample_invoice_pdf), "--out-dir", str(out_dir), "--dpi", "150"])
    assert res.exit_code == 0
    assert "Rendered" in res.output
    assert out_dir.exists()


def test_cli_tables(sample_invoice_pdf: Path):
    res = runner.invoke(app, ["tables", str(sample_invoice_pdf), "--format", "markdown"])
    assert res.exit_code == 0
    assert "Description" in res.output


def test_cli_extract_no_vlm(sample_invoice_pdf: Path, tmp_path: Path):
    out_file = tmp_path / "result.json"
    res = runner.invoke(app, [
        "extract",
        str(sample_invoice_pdf),
        "--schema", "invoice",
        "--no-vlm",
        "--dpi", "150",
        "--output", str(out_file),
    ])
    assert res.exit_code == 0
    assert out_file.exists()
    assert "INV" in out_file.read_text(encoding="utf-8") or "line_items" in out_file.read_text(encoding="utf-8")
