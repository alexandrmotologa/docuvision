"""FastAPI web studio application for visual document exploration and schema testing."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pymupdf
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from docuvision import __version__
from docuvision.core.config import settings
from docuvision.core.models import DocumentResult
from docuvision.core.schemas import list_available_schemas
from docuvision.pipeline.orchestrator import DocumentPipeline
from docuvision.rasterizer.engine import PDFRasterizer
from docuvision.table.extractor import TableExtractor
from docuvision.vlm.client import VLMClient

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="DocuVision Studio",
    description="Zero-cloud multimodal document intelligence and structured schema extraction pipeline",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=FileResponse)
async def serve_studio_ui() -> FileResponse:
    """Serve the interactive Web Studio single-page application."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Studio frontend bundle not found")
    return FileResponse(index_file)


@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    """Return backend health telemetry and runtime versions."""
    return {
        "status": "healthy",
        "version": __version__,
        "pymupdf_version": pymupdf.__version__,
        "vlm_provider": settings.vlm_provider,
        "vlm_model": settings.vlm_model,
        "raster_dpi_default": settings.raster_dpi,
    }


@app.get("/api/schemas")
async def get_schemas() -> Dict[str, Any]:
    """Retrieve catalog of available extraction schemas and their JSON schemas."""
    return list_available_schemas()


@app.get("/api/sample/{sample_name}")
async def get_sample_document(sample_name: str) -> FileResponse:
    """Retrieve an authentic built-in sample document for rapid evaluation."""
    examples_dir = Path(__file__).resolve().parents[3] / "examples"
    target = examples_dir / f"sample_{sample_name}.pdf"
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Sample document 'sample_{sample_name}.pdf' not found")
    return FileResponse(target, media_type="application/pdf", filename=target.name)


@app.get("/api/vlm/status")
async def probe_vlm() -> Dict[str, Any]:
    """Check connectivity to the local vision model runtime."""
    client = VLMClient(settings=settings)
    return await client.check_health()


@app.post("/api/rasterize")
async def rasterize_document(
    file: UploadFile = File(...),
    dpi: int = Query(default=200, ge=72, le=600),
) -> Dict[str, Any]:
    """Render document pages into raster images and return base64 payloads."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    rasterizer = PDFRasterizer(settings=settings)
    pages = rasterizer.rasterize_all(source=content, dpi=dpi, filename=file.filename)

    return {
        "filename": file.filename,
        "total_pages": len(pages),
        "pages": [
            {
                "page_number": p.page_number,
                "width": p.width,
                "height": p.height,
                "dpi": p.dpi,
                "char_count": p.char_count,
                "word_count": p.word_count,
                "image_base64": p.image_base64,
            }
            for p in pages
        ],
    }


@app.post("/api/tables")
async def extract_tables(
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """Extract all tabular regions and convert to Markdown, CSV, and matrix records."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    extractor = TableExtractor(settings=settings)
    tables = extractor.extract_from_document(source=content)

    return {
        "filename": file.filename,
        "table_count": len(tables),
        "tables": [t.model_dump() for t in tables],
    }


@app.post("/api/extract", response_model=DocumentResult)
async def extract_document(
    file: UploadFile = File(...),
    schema_name: str = Query(default="generic"),
    use_vlm: bool = Query(default=True),
    dpi: int = Query(default=200, ge=72, le=600),
) -> DocumentResult:
    """Execute end-to-end multimodal extraction, returning structured JSON and tables."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    pipeline = DocumentPipeline(settings=settings)
    result = await pipeline.process_async(
        source=content,
        schema_name=schema_name,
        dpi=dpi,
        use_vlm=use_vlm,
        filename=file.filename,
    )
    return result
