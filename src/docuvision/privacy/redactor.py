"""Privacy preservation and PII (Personally Identifiable Information) redaction engine."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pymupdf
from PIL import Image, ImageDraw

from docuvision.core.models import BoundingBox


class PIIRedactor:
    """Detects and redacts sensitive PII fields and bounding boxes from PDFs and images."""

    DEFAULT_PATTERNS: Dict[str, str] = {
        "credit_card": r"\b(?:\d{4}[ -]?){3}\d{4}\b",
        "ssn": r"\b\d{3}[ -]?\d{2}[ -]?\d{4}\b",
        "iban": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}([A-Z0-9]?){0,16}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b",
        "phone": r"\b(?:\+?\d{1,3}[ -]?)?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}\b",
    }

    def __init__(self, patterns: Optional[Dict[str, str]] = None) -> None:
        self.patterns = patterns or self.DEFAULT_PATTERNS

    def detect_pii(self, text: str) -> List[Dict[str, Any]]:
        """Scan text and identify all PII occurrences."""
        matches: List[Dict[str, Any]] = []
        for cat_name, pattern in self.patterns.items():
            for m in re.finditer(pattern, text):
                raw_val = m.group(0)
                # Obfuscate preview for audit log
                if len(raw_val) > 4:
                    masked = raw_val[:2] + ("*" * (len(raw_val) - 4)) + raw_val[-2:]
                else:
                    masked = "****"

                matches.append(
                    {
                        "category": cat_name,
                        "raw_match": raw_val,
                        "masked_preview": masked,
                        "start": m.start(),
                        "end": m.end(),
                    }
                )
        return matches

    def redact_pdf(
        self,
        source: Union[str, Path, bytes],
        custom_terms: Optional[List[str]] = None,
        redact_categories: Optional[List[str]] = None,
    ) -> tuple[bytes, int]:
        """Apply cryptographic redactions to a PDF, wiping text and vectors permanently.

        Returns:
            Tuple of (redacted_pdf_bytes, total_redactions_applied).
        """
        if isinstance(source, (str, Path)):
            doc = pymupdf.open(str(source))
        else:
            doc = pymupdf.open(stream=source, filetype="pdf")

        active_patterns: Dict[str, str] = {}
        target_cats = redact_categories or list(self.patterns.keys())
        for cat in target_cats:
            if cat in self.patterns:
                active_patterns[cat] = self.patterns[cat]

        total_redactions = 0

        for page in doc:
            page_text = page.get_text("text") or ""
            terms_to_redact: List[str] = list(custom_terms or [])

            # Detect PII terms in page text
            for pattern in active_patterns.values():
                for m in re.finditer(pattern, page_text):
                    terms_to_redact.append(m.group(0))

            # Apply redaction annotations
            for term in set(terms_to_redact):
                if not term.strip():
                    continue
                rects = page.search_for(term)
                for rect in rects:
                    page.add_redact_annot(rect, fill=(0, 0, 0))  # Blackout rectangle
                    total_redactions += 1

            page.apply_redactions()

        out_buf = io.BytesIO()
        doc.save(out_buf)
        doc.close()
        return out_buf.getvalue(), total_redactions

    def redact_image(
        self,
        image_bytes: bytes,
        bounding_boxes: List[BoundingBox],
    ) -> bytes:
        """Draw blackout rectangles over pixel coordinates on image scans."""
        with Image.open(io.BytesIO(image_bytes)) as img:
            draw = ImageDraw.Draw(img)
            w, h = img.size

            for box in bounding_boxes:
                x0, y0, x1, y1 = box.to_pixels(w, h)
                draw.rectangle([x0, y0, x1, y1], fill="black")

            out_buf = io.BytesIO()
            img.save(out_buf, format="PNG")
            return out_buf.getvalue()
