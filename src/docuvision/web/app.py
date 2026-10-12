"""FastAPI web studio application for visual document exploration and schema testing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymupdf
from fastapi import Body, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from docuvision import __version__
from docuvision.core.config import DocuVisionSettings, settings
from docuvision.core.models import DocumentResult
from docuvision.core.schemas import delete_custom_schema, list_available_schemas, save_custom_schema
from docuvision.pipeline.excel_exporter import ExcelExporter
from docuvision.pipeline.orchestrator import DocumentPipeline
from docuvision.privacy.redactor import PIIRedactor
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


@app.post("/api/schemas/custom")
async def create_custom_schema_endpoint(
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """Register and save a new user-defined document schema."""
    name = payload.get("name", "").strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Schema 'name' is required")
    fields = payload.get("fields", [])
    if not fields or not isinstance(fields, list):
        raise HTTPException(status_code=400, detail="Schema must specify at least one field in 'fields'")
    description = payload.get("description", "")

    file_path = save_custom_schema(name, fields, description=description)
    return {
        "status": "created",
        "name": name,
        "path": str(file_path),
        "fields_count": len(fields),
    }


@app.delete("/api/schemas/custom/{schema_name}")
async def delete_custom_schema_endpoint(schema_name: str) -> Dict[str, Any]:
    """Remove a previously registered custom schema."""
    success = delete_custom_schema(schema_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Custom schema '{schema_name}' not found")
    return {"status": "deleted", "name": schema_name}


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
    redact_pii: bool = Query(default=False),
    model: Optional[str] = Query(default=None),
    temperature: Optional[float] = Query(default=None),
) -> DocumentResult:
    """Execute end-to-end multimodal extraction, returning structured JSON and tables."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # If runtime overrides were provided, clone settings
    if model or temperature is not None:
        custom_settings = DocuVisionSettings(**settings.model_dump())
        if model:
            custom_settings.vlm_model = model
        if temperature is not None:
            custom_settings.vlm_temperature = temperature
        pipeline = DocumentPipeline(settings=custom_settings)
    else:
        pipeline = DocumentPipeline(settings=settings)

    result = await pipeline.process_async(
        source=content,
        schema_name=schema_name,
        dpi=dpi,
        use_vlm=use_vlm,
        filename=file.filename,
        redact_pii=redact_pii,
    )
    return result


@app.post("/api/export/excel")
async def export_excel_endpoint(
    payload: Dict[str, Any] = Body(...),
) -> Response:
    """Receive DocumentResult JSON payload and return downloadable multi-sheet Excel file."""
    try:
        doc_result = DocumentResult.model_validate(payload)
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Invalid DocumentResult payload: {err}")

    exporter = ExcelExporter()
    excel_bytes = exporter.export_to_bytes(doc_result)
    stem = Path(doc_result.metadata.filename).stem or "docuvision_report"

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{stem}_intelligence.xlsx"'},
    )
