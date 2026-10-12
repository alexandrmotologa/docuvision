"""High-fidelity PDF rasterization and multi-page image extraction engine."""

from __future__ import annotations

import base64
import datetime
import hashlib
import io
from pathlib import Path
from typing import Generator, List, Optional, Union

import pymupdf
from PIL import Image

from docuvision.core.config import DocuVisionSettings, settings as default_settings
from docuvision.core.models import DocumentMetadata, DocumentPage
from docuvision.rasterizer.preprocessor import ImagePreprocessor


class PDFRasterizer:
    """Renders PDF pages and scanned images into high-resolution pixel matrices.

    Maintains vector typography clarity, handles orientation correction,
    and formats images for multimodal local VLM consumption.
    """

    def __init__(
        self,
        settings: Optional[DocuVisionSettings] = None,
        preprocessor: Optional[ImagePreprocessor] = None,
    ) -> None:
        self.settings = settings or default_settings
        self.preprocessor = preprocessor or ImagePreprocessor()

    def inspect_metadata(
        self,
        source: Union[str, Path, bytes],
        filename: Optional[str] = None,
    ) -> DocumentMetadata:
        """Inspect document headers, page count, and cryptographic hash."""
        if isinstance(source, (str, Path)):
            path = Path(source)
            file_bytes = path.read_bytes()
            name = filename or path.name
            path_str = str(path.resolve())
        else:
            file_bytes = source
            name = filename or "document.pdf"
            path_str = None

        sha256 = hashlib.sha256(file_bytes).hexdigest()
        size_bytes = len(file_bytes)

        # Probe page count via PyMuPDF
        with pymupdf.open(stream=file_bytes, filetype="pdf" if name.lower().endswith(".pdf") else None) as doc:
            total_pages = max(1, len(doc))

        mime_type = "application/pdf" if name.lower().endswith(".pdf") else "image/png"

        return DocumentMetadata(
            filename=name,
            file_path=path_str,
            file_size_bytes=size_bytes,
            total_pages=total_pages,
            mime_type=mime_type,
            sha256_hash=sha256,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    def rasterize_page(
        self,
        page: pymupdf.Page,
        page_number: int,
        dpi: Optional[int] = None,
        enhance: bool = False,
    ) -> DocumentPage:
        """Render a single PyMuPDF page object into a rasterized DocumentPage."""
        target_dpi = dpi or self.settings.raster_dpi
        zoom = target_dpi / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)

        # Render pixmap with optional grayscale
        cs = pymupdf.csGRAY if self.settings.raster_grayscale else pymupdf.csRGB
        pix = page.get_pixmap(matrix=matrix, alpha=False, colorspace=cs)

        # Check and enforce max pixel bound to protect VLM context window
        raw_png = pix.tobytes("png")
        with Image.open(io.BytesIO(raw_png)) as pil_img:
            processed_img, _ = self.preprocessor.resize_max_bound(
                pil_img,
                max_dim=self.settings.raster_max_dim,
            )
            if enhance:
                processed_img = self.preprocessor.enhance(processed_img)

            buf = io.BytesIO()
            processed_img.save(buf, format="PNG", optimize=True)
            final_png = buf.getvalue()

        # Text extraction and statistical metrics
        text_content = page.get_text("text") or ""
        words = text_content.split()

        base64_data = base64.b64encode(final_png).decode("ascii")

        rect = page.rect
        return DocumentPage(
            page_number=page_number,
            width=float(rect.width),
            height=float(rect.height),
            dpi=target_dpi,
            text_content=text_content,
            tables=[],
            image_base64=base64_data,
            char_count=len(text_content),
            word_count=len(words),
        )

    def stream_pages(
        self,
        source: Union[str, Path, bytes],
        dpi: Optional[int] = None,
        enhance: bool = False,
        filename: Optional[str] = None,
    ) -> Generator[DocumentPage, None, None]:
        """Stream rasterized pages one-by-one to preserve host RAM on massive documents."""
        if isinstance(source, (str, Path)):
            path = Path(source)
            file_bytes = path.read_bytes()
            name = filename or path.name
        else:
            file_bytes = source
            name = filename or "document.pdf"

        filetype = "pdf" if name.lower().endswith(".pdf") else None
        with pymupdf.open(stream=file_bytes, filetype=filetype) as doc:
            for idx, page in enumerate(doc):
                yield self.rasterize_page(
                    page=page,
                    page_number=idx + 1,
                    dpi=dpi,
                    enhance=enhance,
                )

    def rasterize_all(
        self,
        source: Union[str, Path, bytes],
        dpi: Optional[int] = None,
        enhance: bool = False,
        filename: Optional[str] = None,
    ) -> List[DocumentPage]:
        """Rasterize all pages of a document into an in-memory list."""
        return list(
            self.stream_pages(
                source=source,
                dpi=dpi,
                enhance=enhance,
                filename=filename,
            )
        )

    def save_pages_to_disk(
        self,
        source: Union[str, Path, bytes],
        output_dir: Union[str, Path],
        dpi: Optional[int] = None,
        prefix: str = "page",
    ) -> List[Path]:
        """Render all pages and write PNG images to the target directory."""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        saved_files: List[Path] = []
        for doc_page in self.stream_pages(source=source, dpi=dpi):
            if doc_page.image_base64:
                file_dest = out_path / f"{prefix}_{doc_page.page_number:03d}.png"
                img_data = base64.b64decode(doc_page.image_base64)
                file_dest.write_bytes(img_data)
                doc_page.image_path = str(file_dest.resolve())
                saved_files.append(file_dest)

        return saved_files
