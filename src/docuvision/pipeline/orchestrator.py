"""End-to-end document intelligence and multimodal schema extraction pipeline."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union
from pydantic import BaseModel

from docuvision.core.config import DocuVisionSettings, settings as default_settings
from docuvision.core.models import DocumentPage, DocumentResult, Table
from docuvision.core.schemas import get_schema_class
from docuvision.rasterizer.engine import PDFRasterizer
from docuvision.table.extractor import TableExtractor
from docuvision.table.reconciler import TableReconciler
from docuvision.table.stitcher import MultiPageTableStitcher
from docuvision.privacy.redactor import PIIRedactor
from docuvision.vlm.client import VLMClient
from docuvision.vlm.parser import VLMParser
from docuvision.vlm.prompt import PromptBuilder


class DocumentPipeline:
    """Orchestrates rasterization, table parsing, multimodal VLM extraction, and math validation."""

    def __init__(
        self,
        settings: Optional[DocuVisionSettings] = None,
        rasterizer: Optional[PDFRasterizer] = None,
        table_extractor: Optional[TableExtractor] = None,
        table_stitcher: Optional[MultiPageTableStitcher] = None,
        pii_redactor: Optional[PIIRedactor] = None,
        vlm_client: Optional[VLMClient] = None,
        vlm_parser: Optional[VLMParser] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        reconciler: Optional[TableReconciler] = None,
    ) -> None:
        self.settings = settings or default_settings
        self.rasterizer = rasterizer or PDFRasterizer(settings=self.settings)
        self.table_extractor = table_extractor or TableExtractor(settings=self.settings)
        self.table_stitcher = table_stitcher or MultiPageTableStitcher()
        self.pii_redactor = pii_redactor or PIIRedactor()
        self.vlm_client = vlm_client or VLMClient(settings=self.settings)
        self.vlm_parser = vlm_parser or VLMParser()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.reconciler = reconciler or TableReconciler()

    def _build_markdown_summary(
        self,
        result_data: Dict[str, Any],
        tables: List[Table],
        schema_name: str,
        validation_passed: bool,
        validation_errors: List[str],
    ) -> str:
        """Render a unified, human-readable markdown document."""
        lines = [
            f"# Document Extraction Summary ({schema_name.upper()})",
            "",
            f"**Validation Status**: {'PASSED' if validation_passed else 'DISCREPANCIES DETECTED'}",
        ]

        if validation_errors:
            lines.append("")
            lines.append("### Discrepancy Warnings")
            for err in validation_errors:
                lines.append(f"- {err}")

        lines.append("")
        lines.append("### Key Extracted Fields")
        for key, val in result_data.items():
            if isinstance(val, (list, dict)):
                continue
            if val is not None:
                lines.append(f"- **{key}**: {val}")

        if tables:
            lines.append("")
            lines.append(f"### Detected Tables ({len(tables)})")
            for idx, tab in enumerate(tables):
                lines.append(f"#### Table {idx + 1} (Page {tab.page_number})")
                lines.append(tab.markdown)
                lines.append("")

        return "\n".join(lines)

    def _fallback_deterministic_extraction(
        self,
        pages: List[DocumentPage],
        tables: List[Table],
        schema_cls: Type[BaseModel],
    ) -> Dict[str, Any]:
        """Heuristic field extraction using page text and tables when VLM is disabled or offline."""
        data: Dict[str, Any] = {}
        all_text = "\n".join(p.text_content for p in pages)

        # Basic invoice / receipt heuristic mapping from tables
        if schema_cls.__name__ in ("InvoiceSchema", "ReceiptSchema") and tables:
            first_tab = tables[0]
            records = first_tab.to_dict_records()
            items = []
            for r in records:
                # Find description, qty, price columns
                desc = next((v for k, v in r.items() if any(w in k.lower() for w in ["item", "desc", "particular", "name"])), None)
                qty = next((v for k, v in r.items() if any(w in k.lower() for w in ["qty", "quant", "count"])), "1.0")
                price = next((v for k, v in r.items() if any(w in k.lower() for w in ["price", "rate", "cost"])), "0.0")
                total = next((v for k, v in r.items() if any(w in k.lower() for w in ["total", "amount", "net"])), "0.0")

                if desc:
                    items.append({
                        "description": desc,
                        "quantity": self.table_extractor._parse_numeric(qty) or 1.0,
                        "unit_price": self.table_extractor._parse_numeric(price) or 0.0,
                        "total_price": self.table_extractor._parse_numeric(total) or 0.0,
                    })
            if items:
                if schema_cls.__name__ == "InvoiceSchema":
                    data["line_items"] = items
                else:
                    data["items"] = [{"name": it["description"], "quantity": it["quantity"], "price": it["total_price"]} for it in items]

        # Populate generic schema fallback
        if schema_cls.__name__ == "GenericKeyValueSchema":
            data["document_title"] = pages[0].text_content.splitlines()[0][:80] if pages and pages[0].text_content else "Document"
            data["summary"] = f"Processed {len(pages)} page(s) containing {len(tables)} table(s)."

        return data

    async def process_async(
        self,
        source: Union[str, Path, bytes],
        schema_name: str = "generic",
        custom_schema_cls: Optional[Type[BaseModel]] = None,
        dpi: Optional[int] = None,
        use_vlm: bool = True,
        filename: Optional[str] = None,
        redact_pii: bool = False,
        stitch_tables: bool = True,
    ) -> DocumentResult:
        """Asynchronously execute full document processing pipeline."""
        start_time = time.perf_counter()

        working_source = source
        validation_errors: List[str] = []

        if redact_pii:
            try:
                redacted_bytes, count = self.pii_redactor.redact_pdf(source)
                working_source = redacted_bytes
            except Exception as e:
                validation_errors.append(f"PII redaction skipped: {e}")

        # Step 1: Document metadata
        metadata = self.rasterizer.inspect_metadata(source=working_source, filename=filename)

        # Step 2: Rasterization
        pages: List[DocumentPage] = []
        for page in self.rasterizer.stream_pages(source=working_source, dpi=dpi, filename=filename):
            # Step 3: Extract tables per page
            page_tables = self.table_extractor.extract_from_document(source=working_source)
            page.tables = [t for t in page_tables if t.page_number == page.page_number]
            pages.append(page)

        all_tables = [t for p in pages for t in p.tables]
        if stitch_tables and len(all_tables) > 1:
            all_tables = self.table_stitcher.stitch_tables(all_tables)

        # Resolve target schema
        target_schema_cls = custom_schema_cls or get_schema_class(schema_name)

        structured_data: Dict[str, Any] = {}
        validation_passed = True
        validation_errors: List[str] = []
        vlm_metrics: Dict[str, Any] = {}

        # Step 4: Multimodal VLM extraction
        if use_vlm and pages and pages[0].image_base64:
            table_md_hints = "\n\n".join(t.markdown for t in all_tables) if all_tables else None
            prompt = self.prompt_builder.build_user_prompt(
                schema_cls=target_schema_cls,
                page_number=1,
                total_pages=len(pages),
                ocr_hint=pages[0].text_content,
                table_markdown_hints=table_md_hints,
            )

            try:
                vlm_response = await self.vlm_client.generate(
                    prompt=prompt,
                    image_base64=pages[0].image_base64,
                )
                parsed_data, is_valid, errors = self.vlm_parser.parse_and_validate(
                    raw_text=vlm_response,
                    schema_cls=target_schema_cls,
                )
                structured_data = parsed_data
                validation_passed = is_valid
                validation_errors.extend(errors)
                vlm_metrics = {
                    "provider": self.settings.vlm_provider,
                    "model": self.settings.vlm_model,
                    "response_length_chars": len(vlm_response),
                }
            except Exception as exc:
                validation_errors.append(f"VLM extraction skipped or failed: {exc}")
                # Fallback to deterministic parser
                structured_data = self._fallback_deterministic_extraction(
                    pages=pages,
                    tables=all_tables,
                    schema_cls=target_schema_cls,
                )
        else:
            structured_data = self._fallback_deterministic_extraction(
                pages=pages,
                tables=all_tables,
                schema_cls=target_schema_cls,
            )

        # Step 5: Arithmetic reconciliation
        if self.settings.enable_line_item_math_check and structured_data:
            if target_schema_cls.__name__ == "InvoiceSchema":
                report = self.reconciler.reconcile_invoice(structured_data, all_tables)
                if not report.passed:
                    validation_passed = False
                    validation_errors.extend(report.discrepancies)
            elif target_schema_cls.__name__ == "BalanceSheetSchema":
                report = self.reconciler.reconcile_balance_sheet(structured_data)
                if not report.passed:
                    validation_passed = False
                    validation_errors.extend(report.discrepancies)

        # Step 6: Synthesize summary
        markdown_summary = self._build_markdown_summary(
            result_data=structured_data,
            tables=all_tables,
            schema_name=schema_name,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
        )

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return DocumentResult(
            metadata=metadata,
            pages=pages,
            tables=all_tables,
            structured_data=structured_data,
            schema_name=schema_name,
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            markdown_summary=markdown_summary,
            vlm_metrics=vlm_metrics,
            latency_ms=elapsed_ms,
        )

    def process(
        self,
        source: Union[str, Path, bytes],
        schema_name: str = "generic",
        custom_schema_cls: Optional[Type[BaseModel]] = None,
        dpi: Optional[int] = None,
        use_vlm: bool = True,
        filename: Optional[str] = None,
        redact_pii: bool = False,
        stitch_tables: bool = True,
    ) -> DocumentResult:
        """Synchronous wrapper for pipeline execution."""
        import asyncio

        return asyncio.run(
            self.process_async(
                source=source,
                schema_name=schema_name,
                custom_schema_cls=custom_schema_cls,
                dpi=dpi,
                use_vlm=use_vlm,
                filename=filename,
                redact_pii=redact_pii,
                stitch_tables=stitch_tables,
            )
        )
