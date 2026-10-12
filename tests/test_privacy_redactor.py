"""Tests for privacy and PII redaction engine."""

from PIL import Image
import pymupdf

from docuvision.core.models import BoundingBox
from docuvision.privacy.redactor import PIIRedactor


def test_detect_pii():
    redactor = PIIRedactor()
    sample_text = (
        "Customer John Doe, card 4532-1234-5678-9012, SSN 123-45-6789, "
        "email john.doe@example.com and phone +1-555-123-4567."
    )
    matches = redactor.detect_pii(sample_text)
    categories = {m["category"] for m in matches}
    assert "credit_card" in categories
    assert "ssn" in categories
    assert "email" in categories
    assert "phone" in categories


def test_redact_pdf_stream():
    redactor = PIIRedactor()

    # Create synthetic PDF with sensitive numbers
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 100), "Confidential Customer Information", fontsize=14)
    page.insert_text((50, 130), "Card: 4532 1234 5678 9012", fontsize=11)
    page.insert_text((50, 150), "SSN: 999-88-7777", fontsize=11)
    page.insert_text((50, 170), "Public Note: Clean record.", fontsize=11)
    raw_pdf = doc.tobytes()
    doc.close()

    redacted_pdf, count = redactor.redact_pdf(raw_pdf)
    assert count >= 2

    # Open redacted PDF and assert confidential text is erased
    check_doc = pymupdf.open(stream=redacted_pdf, filetype="pdf")
    redacted_text = check_doc[0].get_text("text")
    assert "4532 1234" not in redacted_text
    assert "999-88-7777" not in redacted_text
    assert "Public Note" in redacted_text
    check_doc.close()


def test_redact_image():
    redactor = PIIRedactor()
    img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_png = buf.getvalue()

    box = BoundingBox(ymin=0.25, xmin=0.25, ymax=0.75, xmax=0.75)
    redacted_bytes = redactor.redact_image(raw_png, [box])

    with Image.open(io.BytesIO(redacted_bytes)) as r_img:
        # Center pixel (100, 100) should now be black (0, 0, 0)
        pixel = r_img.getpixel((100, 100))
        assert pixel == (0, 0, 0)
