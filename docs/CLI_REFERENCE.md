# DocuVision CLI Reference Manual

DocuVision provides a command-line interface powered by Typer and Rich. It supports single-file extraction, concurrent directory processing, table extraction, full-text search, and local health diagnostics.

## Global Options

```bash
docuvision --help
```

Global configuration can be customized through environment variables or a `.env` file:

| Environment Variable | Default | Description |
| -------------------- | ------- | ----------- |
| `DOCUVISION_VLM_BASE_URL` | `http://localhost:11434/v1` | Base URL for the OpenAI-compatible local VLM endpoint |
| `DOCUVISION_VLM_MODEL` | `llama3.2-vision:latest` | Target model identifier |
| `DOCUVISION_VLM_PROVIDER` | `ollama` | Provider backend (`ollama`, `vllm`, `openai`) |
| `DOCUVISION_RASTER_DPI` | `200` | Default rasterization resolution |
| `DOCUVISION_TIMEOUT_SECONDS` | `120` | HTTP request timeout for VLM inference |

---

## Commands

### 1. `extract`

Processes a single document (PDF or image) and extracts structured data according to a schema.

```bash
docuvision extract <FILE_PATH> [OPTIONS]
```

#### Arguments
- `FILE_PATH`: Path to the PDF or image file (PNG, JPG, TIFF, WebP).

#### Options
- `-s, --schema`: Target schema name (`invoice`, `receipt`, `balance_sheet`, `lab_report`, `generic`, or any registered custom schema). Default: `generic`.
- `-o, --output`: Destination path to save extraction output.
- `-f, --format`: Output format (`json`, `markdown`, `excel`, or `both`). Default: `json`.
- `--dpi`: Rasterization resolution (DPI). Default: `200`.
- `--vlm / --no-vlm`: Toggle local Vision-Language Model execution. Default: `--vlm`.
- `--redact-pii`: Enable automated redaction of sensitive numbers (credit cards, tax IDs, emails, phone numbers). Default: `False`.

#### Examples

```bash
# Extract an invoice using local VLM and print JSON to stdout
docuvision extract invoice.pdf --schema invoice

# Extract without VLM (deterministic vector tables and heuristic fallback)
docuvision extract invoice.pdf --schema invoice --no-vlm

# Generate a styled multi-sheet Excel workbook with PII masking
docuvision extract statement.pdf --schema balance_sheet --format excel -o statement.xlsx --redact-pii
```

---

### 2. `batch`

Executes concurrent extraction over an entire directory of documents, writing individual reports, a consolidated JSON summary, and an aggregated CSV.

```bash
docuvision batch <INPUT_DIR> [OPTIONS]
```

#### Arguments
- `INPUT_DIR`: Directory containing document files to process.

#### Options
- `-o, --output-dir`: Output directory for generated artifacts. Default: `./outputs/batch`.
- `-s, --schema`: Target extraction schema. Default: `generic`.
- `-w, --workers`: Concurrency limit (number of simultaneous documents processed). Default: `4`.
- `-f, --format`: Export formats (`json`, `markdown`, `excel`, `all`). Default: `all`.
- `--dpi`: Rendering resolution. Default: `200`.
- `--vlm / --no-vlm`: Toggle VLM usage. Default: `--vlm`.
- `--index / --no-index`: Automatically index processed outputs into the local SQLite FTS5 search engine. Default: `--index`.

#### Examples

```bash
# Process a folder of invoices using 4 workers and write to ./batch_reports
docuvision batch ./invoices --schema invoice --output-dir ./batch_reports --workers 4

# Fast deterministic batch run without VLM
docuvision batch ./scans --schema generic --no-vlm --output-dir ./scans_out
```

---

### 3. `search`

Queries the persistent SQLite FTS5 search index across all processed documents, OCR text, and extracted JSON schemas.

```bash
docuvision search <QUERY> [OPTIONS]
```

#### Arguments
- `QUERY`: Keywords or phrase query to search for.

#### Options
- `-n, --limit`: Maximum number of search hits to return. Default: `10`.
- `-d, --index-dir`: Index all JSON results in a specified folder before executing search.
- `--clear`: Clear all records from the SQLite search index.

#### Examples

```bash
# Search for a vendor or company name
docuvision search "Acme Corp"

# Search for line items or amounts
docuvision search "Software Licensing"

# Index a batch folder and search in one step
docuvision search "Consulting" --index-dir ./batch_reports
```

---

### 4. `tables`

Inspects and extracts tabular structures from a document without running the full VLM pipeline.

```bash
docuvision tables <FILE_PATH> [OPTIONS]
```

#### Options
- `-f, --format`: Table output format (`markdown`, `csv`, or `json`). Default: `markdown`.
- `-o, --output`: Optional file path to save tables.

#### Example

```bash
docuvision tables report.pdf --format csv -o tables.csv
```

---

### 5. `rasterize`

Renders document pages into standalone PNG images using PyMuPDF.

```bash
docuvision rasterize <FILE_PATH> [OPTIONS]
```

#### Options
- `-d, --out-dir`: Destination folder for page images. Default: `./outputs/pages`.
- `--dpi`: Resolution in dots per inch. Default: `200`.

#### Example

```bash
docuvision rasterize presentation.pdf --dpi 300 -d ./rendered_pages
```

---

### 6. `schemas`

Lists all built-in and user-defined schemas registered in the system.

```bash
docuvision schemas
```

---

### 7. `check`

Runs diagnostics on local runtimes, checking PyMuPDF versions, VLM network reachability, and model latency.

```bash
docuvision check
```

---

### 8. `serve`

Starts the interactive FastAPI Web Studio.

```bash
docuvision serve [OPTIONS]
```

#### Options
- `-h, --host`: Network interface to bind to. Default: `127.0.0.1`.
- `-p, --port`: Port number. Default: `8000`.
- `--reload`: Enable code reload during development. Default: `False`.

#### Example

```bash
docuvision serve --host 0.0.0.0 --port 8000
```
