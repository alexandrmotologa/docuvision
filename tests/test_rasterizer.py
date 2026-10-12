"""Tests for PDF rasterization and image preprocessor."""

from pathlib import Path
from PIL import Image
from docuvision.rasterizer.engine import PDFRasterizer
from docuvision.rasterizer.preprocessor import ImagePreprocessor


def test_inspect_metadata(sample_invoice_pdf: Path):
    rasterizer = PDFRasterizer()
    meta = rasterizer.inspect_metadata(source=sample_invoice_pdf)

    assert meta.filename == "sample_invoice.pdf"
    assert meta.total_pages == 1
    assert meta.file_size_bytes > 0
    assert len(meta.sha256_hash) == 64
    assert meta.mime_type == "application/pdf"


def test_rasterize_single_page(sample_invoice_pdf: Path):
    rasterizer = PDFRasterizer()
    pages = rasterizer.rasterize_all(source=sample_invoice_pdf, dpi=150)

    assert len(pages) == 1
    page = pages[0]
    assert page.page_number == 1
    assert page.dpi == 150
    assert page.image_base64 is not None
    assert len(page.image_base64) > 1000
    assert "INVOICE" in page.text_content
    assert page.char_count > 50


def test_rasterize_multipage(multipage_pdf: Path):
    rasterizer = PDFRasterizer()
    pages = rasterizer.rasterize_all(source=multipage_pdf, dpi=150)

    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2
    assert "Quarterly Financial" in pages[0].text_content
    assert "Operating Expenses" in pages[1].text_content


def test_save_pages_to_disk(sample_invoice_pdf: Path, tmp_path: Path):
    rasterizer = PDFRasterizer()
    out_dir = tmp_path / "rendered_pages"
    saved = rasterizer.save_pages_to_disk(sample_invoice_pdf, output_dir=out_dir, dpi=150)

    assert len(saved) == 1
    assert saved[0].exists()
    assert saved[0].suffix == ".png"
    # Ensure it is a valid PNG image
    with Image.open(saved[0]) as img:
        assert img.format == "PNG"
        assert img.width > 500


def test_image_preprocessor():
    proc = ImagePreprocessor(contrast_factor=1.2, sharpness_factor=1.2)
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    enhanced = proc.enhance(img)
    assert enhanced.size == (100, 100)

    resized, scale = proc.resize_max_bound(img, max_dim=50)
    assert resized.size == (50, 50)
    assert scale == 0.5
