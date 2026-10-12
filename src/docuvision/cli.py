"""Command line interface for DocuVision built with Typer and Rich."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.syntax import Syntax
from rich.table import Table as RichTable

from docuvision import __version__
from docuvision.core.config import settings
from docuvision.core.schemas import list_available_schemas
from docuvision.pipeline.batch import BatchProcessor
from docuvision.pipeline.excel_exporter import ExcelExporter
from docuvision.pipeline.orchestrator import DocumentPipeline
from docuvision.rasterizer.engine import PDFRasterizer
from docuvision.table.extractor import TableExtractor
from docuvision.vlm.client import VLMClient

app = typer.Typer(
    name="docuvision",
    help="Zero-cloud multimodal document intelligence and structured schema extraction pipeline.",
    add_completion=False,
)
console = Console(legacy_windows=False)


@app.command()
def extract(
    file_path: Path = typer.Argument(..., exists=True, readable=True, help="Path to PDF or scan image"),
    schema: str = typer.Option(
        "generic",
        "--schema",
        "-s",
        help="Target schema: invoice, receipt, balance_sheet, lab_report, generic, or custom",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Optional path to save extraction output"
    ),
    output_format: str = typer.Option(
        "json", "--format", "-f", help="Output format: json, markdown, excel, or both"
    ),
    dpi: int = typer.Option(200, "--dpi", help="Rasterization resolution DPI"),
    use_vlm: bool = typer.Option(
        True, "--vlm/--no-vlm", help="Enable or disable local Vision-Language Model"
    ),
    redact_pii: bool = typer.Option(
        False, "--redact-pii", help="Detect and redact sensitive credit card and PII numbers"
    ),
) -> None:
    """Extract structured data and tables from a document using local VLMs."""
    console.print(
        f"[bold blue]DocuVision[/bold blue] processing [green]{file_path.name}[/green] with schema '[cyan]{schema}[/cyan]'..."
    )

    pipeline = DocumentPipeline(settings=settings)
    with console.status("[bold green]Executing multimodal extraction pipeline..."):
        result = pipeline.process(
            source=file_path,
            schema_name=schema,
            dpi=dpi,
            use_vlm=use_vlm,
            filename=file_path.name,
            redact_pii=redact_pii,
        )

    # Display Metadata Summary
    meta_table = RichTable(title="Document Telemetry", border_style="blue")
    meta_table.add_column("Property", style="bold")
    meta_table.add_column("Value")
    meta_table.add_row("Pages", str(result.metadata.total_pages))
    meta_table.add_row("Size", f"{result.metadata.file_size_bytes / 1024:.1f} KB")
    meta_table.add_row("SHA-256", result.metadata.sha256_hash[:16] + "...")
    meta_table.add_row("Latency", f"{result.latency_ms} ms")
    meta_table.add_row("Tables Detected", str(len(result.tables)))
    meta_table.add_row(
        "Validation", "[green]PASSED[/green]" if result.validation_passed else "[yellow]WARNINGS[/yellow]"
    )
    if redact_pii:
        meta_table.add_row("PII Redaction", "[magenta]ACTIVE[/magenta]")
    console.print(meta_table)

    if result.validation_errors:
        console.print(
            Panel(
                "\n".join(f"[yellow]-[/yellow] {e}" for e in result.validation_errors),
                title="[yellow]Validation & Math Warnings[/yellow]",
                border_style="yellow",
            )
        )

    # Format JSON
    json_str = json.dumps(result.structured_data, indent=2, ensure_ascii=False)
    if output_format in ("json", "both"):
        console.print(
            Panel(
                Syntax(json_str, "json", theme="monokai", line_numbers=True),
                title=f"Structured JSON ({schema})",
                border_style="green",
            )
        )

    if output_format in ("markdown", "both") and result.markdown_summary:
        console.print(
            Panel(
                result.markdown_summary,
                title="Markdown Summary",
                border_style="cyan",
            )
        )

    # Handle Excel export
    if output_format == "excel" or (output and output.suffix.lower() == ".xlsx"):
        dest_excel = output or file_path.with_suffix(".xlsx")
        exporter = ExcelExporter()
        exporter.export_to_file(result, dest_excel)
        console.print(
            f"[bold green]OK[/bold green] Excel workbook generated at [underline]{dest_excel}[/underline]"
        )
    elif output:
        output.parent.mkdir(parents=True, exist_ok=True)
        if output_format == "markdown":
            output.write_text(result.markdown_summary, encoding="utf-8")
        else:
            output.write_text(json_str, encoding="utf-8")
        console.print(f"[bold green]OK[/bold green] Output saved to [underline]{output}[/underline]")

    # Auto-index into local search engine
    try:
        from docuvision.search.index import DocumentSearchIndex

        DocumentSearchIndex().index_document(result)
    except Exception:
        pass


@app.command()
def batch(
    input_dir: Path = typer.Argument(
        ..., exists=True, file_okay=False, dir_okay=True, help="Directory containing documents"
    ),
    schema: str = typer.Option("generic", "--schema", "-s", help="Target extraction schema"),
    output_dir: Path = typer.Option(
        Path("./outputs/batch"), "--output-dir", "-o", help="Directory for batch outputs"
    ),
    workers: int = typer.Option(4, "--workers", "-w", help="Concurrent worker count"),
    output_format: str = typer.Option(
        "all", "--format", "-f", help="Formats to export: json, markdown, excel, all"
    ),
    dpi: int = typer.Option(200, "--dpi", help="Rasterization resolution DPI"),
    use_vlm: bool = typer.Option(True, "--vlm/--no-vlm", help="Enable or disable local VLM"),
    index: bool = typer.Option(
        True, "--index/--no-index", help="Index processed documents into local FTS5 search engine"
    ),
) -> None:
    """Process a directory of documents concurrently with aggregated summary reporting."""
    processor = BatchProcessor(settings=settings)
    files = processor.discover_files(input_dir)

    if not files:
        console.print(f"[yellow]No supported documents found in [underline]{input_dir}[/underline][/yellow]")
        return

    console.print(
        f"[bold blue]DocuVision Batch[/bold blue]: Found [cyan]{len(files)}[/cyan] documents in [underline]{input_dir}[/underline]"
    )

    formats = [output_format] if output_format != "all" else ["json", "markdown", "excel"]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing documents...", total=len(files))

        def on_progress(done: int, total: int, current_name: str) -> None:
            progress.update(task, advance=1, description=f"Extracting [cyan]{current_name}[/cyan]")

        batch_result = asyncio.run(
            processor.process_batch_async(
                input_dir=input_dir,
                output_dir=output_dir,
                schema_name=schema,
                dpi=dpi,
                use_vlm=use_vlm,
                concurrency=workers,
                export_formats=formats,
                progress_callback=on_progress,
                index_search=index,
            )
        )

    # Batch summary table
    table = RichTable(title="Batch Execution Summary", border_style="green")
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Total Files", str(batch_result.total_files))
    table.add_row("Successful", f"[green]{batch_result.successful_files}[/green]")
    table.add_row(
        "Failed", f"[red]{batch_result.failed_files}[/red]" if batch_result.failed_files > 0 else "0"
    )
    table.add_row("Total Pages", str(batch_result.total_pages))
    table.add_row("Total Elapsed", f"{batch_result.total_latency_ms:.1f} ms")
    table.add_row("Reports Saved To", batch_result.output_directory)
    console.print(table)


@app.command()
def tables(
    file_path: Path = typer.Argument(..., exists=True, readable=True, help="Path to PDF document"),
    output_format: str = typer.Option("markdown", "--format", "-f", help="Format: markdown, csv, or json"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Optional output file path"),
) -> None:
    """Detect and extract all tables from a document."""
    extractor = TableExtractor(settings=settings)
    with console.status("[bold green]Detecting and parsing table structures..."):
        detected_tables = extractor.extract_from_document(source=file_path)

    if not detected_tables:
        console.print("[yellow]No tabular regions detected in document.[/yellow]")
        return

    console.print(f"[bold green]OK[/bold green] Found [cyan]{len(detected_tables)}[/cyan] table(s).")

    all_content: list[str] = []
    for idx, tab in enumerate(detected_tables):
        console.print(f"\n[bold]Table {idx + 1}[/bold] (Page {tab.page_number} - {tab.rows}x{tab.cols})")
        if output_format == "csv":
            console.print(tab.csv)
            all_content.append(tab.csv)
        elif output_format == "json":
            records_json = json.dumps(tab.to_dict_records(), indent=2)
            console.print(records_json)
            all_content.append(records_json)
        else:
            console.print(tab.markdown)
            all_content.append(tab.markdown)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n\n".join(all_content), encoding="utf-8")
        console.print(f"\n[bold green]OK[/bold green] Tables written to [underline]{output}[/underline]")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query string or keywords"),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results to return"),
    index_dir: Optional[Path] = typer.Option(
        None, "--index-dir", "-d", help="Index all JSON documents in directory before searching"
    ),
    clear: bool = typer.Option(False, "--clear", help="Clear the search index"),
) -> None:
    """Full-text search across indexed documents, OCR text, and structured schemas."""
    from docuvision.search.index import DocumentSearchIndex

    search_index = DocumentSearchIndex()
    if clear:
        search_index.clear()
        console.print("[bold yellow]Search index cleared successfully.[/bold yellow]")
        if not query or query == "*":
            return

    if index_dir:
        count = search_index.index_directory(index_dir)
        console.print(
            f"[bold green]OK[/bold green] Indexed [cyan]{count}[/cyan] document(s) from {index_dir}"
        )

    total_indexed = search_index.count()
    if total_indexed == 0:
        console.print(
            "[yellow]The search index is empty.[/yellow] Run batch extractions or specify --index-dir to index results."
        )
        return

    hits = search_index.search(query, limit=limit)
    if not hits:
        console.print(
            f"[yellow]No matching documents found for query:[/yellow] '{query}' (searched {total_indexed} documents)"
        )
        return

    table = RichTable(
        title=f"Search Results for '{query}' ({len(hits)} match(es) in {total_indexed} docs)",
        border_style="cyan",
    )
    table.add_column("Doc ID", style="dim")
    table.add_column("Filename", style="bold green")
    table.add_column("Schema", style="cyan")
    table.add_column("Matched Snippet", style="white")
    table.add_column("Top Extracted Data", style="dim")

    for hit in hits:
        preview_str = ", ".join(f"{k}: {v}" for k, v in hit.structured_data_preview.items())
        snip = hit.snippet.replace("[MATCH]", "[bold yellow]").replace("[/MATCH]", "[/bold yellow]")
        table.add_row(
            hit.doc_id,
            hit.filename,
            hit.schema_name,
            snip,
            preview_str[:60] + "..." if len(preview_str) > 60 else preview_str,
        )

    console.print(table)


@app.command()
def rasterize(
    file_path: Path = typer.Argument(..., exists=True, readable=True, help="Path to PDF document"),
    out_dir: Path = typer.Option(
        Path("./outputs/pages"), "--out-dir", "-d", help="Directory to save page images"
    ),
    dpi: int = typer.Option(200, "--dpi", help="Render resolution DPI"),
) -> None:
    """Render PDF pages into high-resolution PNG images."""
    rasterizer = PDFRasterizer(settings=settings)
    with console.status(f"[bold green]Rasterizing pages at {dpi} DPI..."):
        saved = rasterizer.save_pages_to_disk(
            source=file_path,
            output_dir=out_dir,
            dpi=dpi,
            prefix=file_path.stem,
        )

    console.print(
        f"[bold green]OK[/bold green] Rendered [cyan]{len(saved)}[/cyan] page(s) into [underline]{out_dir}[/underline]:"
    )
    for p in saved:
        console.print(f"  - {p.name}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Binding host"),
    port: int = typer.Option(8000, "--port", "-p", help="Binding port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
) -> None:
    """Launch the interactive DocuVision Web Studio."""
    console.print(
        Panel(
            f"[bold blue]DocuVision Web Studio v{__version__}[/bold blue]\n"
            f"Server running at: [bold green]http://{host}:{port}[/bold green]\n"
            f"Zero-Cloud Document Intelligence Dashboard",
            border_style="blue",
        )
    )
    uvicorn.run("docuvision.web.app:app", host=host, port=port, reload=reload)


@app.command()
def check() -> None:
    """Perform diagnostic health check on local dependencies and model runtimes."""
    import pymupdf

    table = RichTable(title="DocuVision Diagnostics", border_style="blue")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    table.add_row("DocuVision", "[green]OK[/green]", f"v{__version__}")
    table.add_row("PyMuPDF", "[green]OK[/green]", f"v{pymupdf.__version__}")

    client = VLMClient(settings=settings)
    health = asyncio.run(client.check_health())

    if health.get("status") == "online":
        table.add_row(
            f"VLM ({health.get('provider')})",
            "[green]ONLINE[/green]",
            f"Model: {health.get('current_model')} (Latency: {health.get('latency_ms')}ms)",
        )
    else:
        table.add_row(
            f"VLM ({health.get('provider')})",
            "[yellow]OFFLINE[/yellow]",
            f"Endpoint: {health.get('base_url')} ({health.get('error', 'Unreachable')})",
        )

    console.print(table)


@app.command()
def schemas() -> None:
    """List available document extraction schemas and descriptions."""
    catalog = list_available_schemas()
    table = RichTable(title="Registered Extraction Schemas", border_style="cyan")
    table.add_column("Schema Key", style="bold green")
    table.add_column("Class Name", style="bold")
    table.add_column("Type")
    table.add_column("Description")

    for key, info in catalog.items():
        is_custom = info.get("is_custom", False)
        type_str = "[magenta]Custom[/magenta]" if is_custom else "[blue]Built-in[/blue]"
        table.add_row(key, info.get("title", ""), type_str, info.get("description", ""))

    console.print(table)


if __name__ == "__main__":
    app()
