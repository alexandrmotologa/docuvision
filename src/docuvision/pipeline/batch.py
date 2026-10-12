"""Concurrent batch document processing and aggregated summary reporting."""

from __future__ import annotations

import asyncio
import csv
import json
import time
from pathlib import Path
from typing import Callable, List, Optional, Set

from pydantic import BaseModel, Field

from docuvision.core.config import DocuVisionSettings
from docuvision.core.config import settings as default_settings
from docuvision.core.models import DocumentResult
from docuvision.pipeline.excel_exporter import ExcelExporter
from docuvision.pipeline.orchestrator import DocumentPipeline


class BatchItemSummary(BaseModel):
    """Aggregated metrics for a single document within a batch run."""

    filename: str
    total_pages: int
    file_size_kb: float
    sha256_hash: str
    schema_name: str
    validation_passed: bool
    discrepancy_count: int
    latency_ms: float
    total_amount: Optional[float] = None
    document_date: Optional[str] = None


class BatchResult(BaseModel):
    """Global summary of an executed batch processing run."""

    total_files: int
    successful_files: int
    failed_files: int
    total_pages: int
    total_latency_ms: float
    items: List[BatchItemSummary] = Field(default_factory=list)
    output_directory: str


class BatchProcessor:
    """Processes directories of documents concurrently with aggregated reporting."""

    SUPPORTED_EXTENSIONS: Set[str] = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

    def __init__(
        self,
        settings: Optional[DocuVisionSettings] = None,
        pipeline: Optional[DocumentPipeline] = None,
        excel_exporter: Optional[ExcelExporter] = None,
    ) -> None:
        self.settings = settings or default_settings
        self.pipeline = pipeline or DocumentPipeline(settings=self.settings)
        self.excel_exporter = excel_exporter or ExcelExporter()

    def discover_files(self, input_dir: Path, recursive: bool = False) -> List[Path]:
        """Scan directory for supported document files."""
        pattern = "**/*" if recursive else "*"
        all_candidates = [
            p
            for p in input_dir.glob(pattern)
            if p.is_file() and p.suffix.lower() in self.SUPPORTED_EXTENSIONS
        ]
        return sorted(all_candidates, key=lambda x: x.name)

    async def process_batch_async(
        self,
        input_dir: Path,
        output_dir: Path,
        schema_name: str = "generic",
        dpi: Optional[int] = None,
        use_vlm: bool = True,
        concurrency: int = 4,
        export_formats: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        index_search: bool = True,
    ) -> BatchResult:
        """Run concurrent document extraction across a folder of documents."""
        start_time = time.perf_counter()
        files = self.discover_files(input_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        formats = set(export_formats or ["json"])
        semaphore = asyncio.Semaphore(concurrency)

        completed_count = 0
        total_files = len(files)
        items: List[BatchItemSummary] = []
        successful_count = 0
        failed_count = 0
        total_pages_count = 0

        async def _process_single(file_path: Path) -> Optional[BatchItemSummary]:
            nonlocal completed_count, successful_count, failed_count, total_pages_count
            async with semaphore:
                try:
                    result: DocumentResult = await self.pipeline.process_async(
                        source=file_path,
                        schema_name=schema_name,
                        dpi=dpi,
                        use_vlm=use_vlm,
                        filename=file_path.name,
                    )

                    # Export individual outputs
                    stem = file_path.stem
                    if "json" in formats or "all" in formats:
                        (output_dir / f"{stem}.json").write_text(
                            json.dumps(result.structured_data, indent=2, ensure_ascii=False),
                            encoding="utf-8",
                        )

                    if "markdown" in formats or "all" in formats:
                        (output_dir / f"{stem}.md").write_text(
                            result.markdown_summary,
                            encoding="utf-8",
                        )

                    if "excel" in formats or "all" in formats:
                        self.excel_exporter.export_to_file(
                            result=result,
                            destination=output_dir / f"{stem}.xlsx",
                        )

                    if index_search:
                        try:
                            from docuvision.search.index import DocumentSearchIndex

                            DocumentSearchIndex().index_document(result)
                        except Exception:
                            pass

                    total_amount = result.structured_data.get("total_amount") or result.structured_data.get(
                        "total"
                    )
                    doc_date = (
                        result.structured_data.get("invoice_date")
                        or result.structured_data.get("transaction_date")
                        or result.structured_data.get("as_of_date")
                    )

                    summary = BatchItemSummary(
                        filename=file_path.name,
                        total_pages=result.metadata.total_pages,
                        file_size_kb=round(result.metadata.file_size_bytes / 1024, 2),
                        sha256_hash=result.metadata.sha256_hash[:16],
                        schema_name=schema_name,
                        validation_passed=result.validation_passed,
                        discrepancy_count=len(result.validation_errors),
                        latency_ms=result.latency_ms,
                        total_amount=float(total_amount) if total_amount is not None else None,
                        document_date=str(doc_date) if doc_date else None,
                    )
                    successful_count += 1
                    total_pages_count += result.metadata.total_pages
                    return summary
                except Exception:
                    failed_count += 1
                    return None
                finally:
                    completed_count += 1
                    if progress_callback:
                        progress_callback(completed_count, total_files, file_path.name)

        tasks = [_process_single(f) for f in files]
        results = await asyncio.gather(*tasks)
        items = [r for r in results if r is not None]

        # Generate aggregated batch_summary.csv
        csv_file = output_dir / "batch_summary.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Filename",
                    "Pages",
                    "Size_KB",
                    "SHA256_Prefix",
                    "Schema",
                    "Validation_Passed",
                    "Discrepancies",
                    "Latency_ms",
                    "Total_Amount",
                    "Document_Date",
                ]
            )
            for it in items:
                writer.writerow(
                    [
                        it.filename,
                        it.total_pages,
                        it.file_size_kb,
                        it.sha256_hash,
                        it.schema_name,
                        it.validation_passed,
                        it.discrepancy_count,
                        it.latency_ms,
                        it.total_amount if it.total_amount is not None else "",
                        it.document_date or "",
                    ]
                )

        # Generate aggregated batch_summary.json
        json_file = output_dir / "batch_summary.json"
        json_file.write_text(
            json.dumps([it.model_dump() for it in items], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        total_latency = round((time.perf_counter() - start_time) * 1000, 2)
        return BatchResult(
            total_files=total_files,
            successful_files=successful_count,
            failed_files=failed_count,
            total_pages=total_pages_count,
            total_latency_ms=total_latency,
            items=items,
            output_directory=str(output_dir.resolve()),
        )
