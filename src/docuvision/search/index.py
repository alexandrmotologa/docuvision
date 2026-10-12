"""SQLite FTS5 full-text search indexer for document archives and batch outputs."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from docuvision.core.models import DocumentResult


class SearchHit(BaseModel):
    """Search match returned by DocumentSearchIndex."""

    doc_id: str
    filename: str
    file_path: Optional[str] = None
    file_hash: str
    schema_name: str
    snippet: str
    rank: float = 0.0
    created_at: str
    structured_data_preview: dict[str, Any] = Field(default_factory=dict)


class DocumentSearchIndex:
    """Persistent SQLite-backed Full-Text Search (FTS5) index for DocuVision."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            config_dir = Path.home() / ".docuvision"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = config_dir / "search_index.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create relational and FTS5 virtual tables with tokenization."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT,
                    file_hash TEXT UNIQUE NOT NULL,
                    schema_name TEXT NOT NULL,
                    content_text TEXT,
                    json_payload TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
            cursor.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    doc_id UNINDEXED,
                    filename,
                    content_text,
                    json_payload,
                    tokenize = 'porter unicode61'
                );
                """
            )
            conn.commit()

    def index_document(self, result: DocumentResult) -> str:
        """Index a DocumentResult artifact into SQLite and FTS5.

        Returns:
            The unique document identifier (doc_id).
        """
        doc_id = result.metadata.sha256_hash[:16]

        # Aggregate raw page text, table markdown, and structured data strings
        text_parts: list[str] = []
        for page in result.pages:
            if page.text_content:
                text_parts.append(page.text_content)
        for tbl in result.tables:
            if tbl.markdown:
                text_parts.append(tbl.markdown)
            for cell in tbl.cells:
                if cell.text:
                    text_parts.append(cell.text)

        content_text = " \n".join(text_parts)
        json_payload = json.dumps(result.structured_data, ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Upsert into documents table
            cursor.execute(
                """
                INSERT INTO documents (
                    doc_id, filename, file_path, file_hash, schema_name,
                    content_text, json_payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_hash) DO UPDATE SET
                    filename = excluded.filename,
                    file_path = excluded.file_path,
                    schema_name = excluded.schema_name,
                    content_text = excluded.content_text,
                    json_payload = excluded.json_payload,
                    created_at = excluded.created_at;
                """,
                (
                    doc_id,
                    result.metadata.filename,
                    result.metadata.file_path or "",
                    result.metadata.sha256_hash,
                    result.schema_name,
                    content_text,
                    json_payload,
                    result.metadata.created_at,
                ),
            )

            # Re-index in FTS5
            cursor.execute("DELETE FROM documents_fts WHERE doc_id = ?", (doc_id,))
            cursor.execute(
                """
                INSERT INTO documents_fts (doc_id, filename, content_text, json_payload)
                VALUES (?, ?, ?, ?);
                """,
                (doc_id, result.metadata.filename, content_text, json_payload),
            )
            conn.commit()

        return doc_id

    def search(self, query: str, limit: int = 20) -> list[SearchHit]:
        """Perform full-text search against the index.

        Supports standard search terms as well as FTS5 phrase queries.
        Falls back to wildcard phrase matching if query syntax is irregular.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # Sanitize query for FTS5 to prevent syntax errors
        safe_query = self._sanitize_fts_query(clean_query)

        hits: list[SearchHit] = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT
                        d.doc_id,
                        d.filename,
                        d.file_path,
                        d.file_hash,
                        d.schema_name,
                        d.created_at,
                        d.json_payload,
                        snippet(documents_fts, 2, '[MATCH]', '[/MATCH]', '...', 16) AS snippet_text,
                        bm25(documents_fts) AS rank
                    FROM documents_fts
                    JOIN documents d ON documents_fts.doc_id = d.doc_id
                    WHERE documents_fts MATCH ?
                    ORDER BY rank ASC
                    LIMIT ?;
                    """,
                    (safe_query, limit),
                )
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                # Fallback to simple LIKE query if FTS expression fails
                pattern = f"%{clean_query}%"
                cursor.execute(
                    """
                    SELECT
                        doc_id, filename, file_path, file_hash, schema_name,
                        created_at, json_payload,
                        substr(content_text, 1, 120) AS snippet_text,
                        0.0 AS rank
                    FROM documents
                    WHERE filename LIKE ? OR content_text LIKE ? OR json_payload LIKE ?
                    LIMIT ?;
                    """,
                    (pattern, pattern, pattern, limit),
                )
                rows = cursor.fetchall()

            for row in rows:
                json_data = {}
                try:
                    if row["json_payload"]:
                        json_data = json.loads(row["json_payload"])
                except Exception:
                    json_data = {}

                # Trim structured preview
                preview = {k: v for i, (k, v) in enumerate(json_data.items()) if i < 4}

                snippet = row["snippet_text"] or ""
                hits.append(
                    SearchHit(
                        doc_id=row["doc_id"],
                        filename=row["filename"],
                        file_path=row["file_path"] if row["file_path"] else None,
                        file_hash=row["file_hash"],
                        schema_name=row["schema_name"],
                        snippet=snippet.strip(),
                        rank=float(row["rank"]) if "rank" in row.keys() else 0.0,
                        created_at=row["created_at"],
                        structured_data_preview=preview,
                    )
                )

        return hits

    def _sanitize_fts_query(self, query: str) -> str:
        """Sanitize query string to avoid broken FTS5 syntax."""
        # Remove characters that can break FTS5 expressions unless part of quotes
        tokens = re.findall(r"\"[^\"]+\"|\w+", query)
        if not tokens:
            return f'"{query}"'
        # Combine words with OR or phrase quotes
        return " OR ".join(tokens)

    def index_directory(self, dir_path: Path) -> int:
        """Scan a directory for DocumentResult JSON files and index them."""
        target_dir = Path(dir_path)
        if not target_dir.exists():
            return 0

        indexed_count = 0
        for file in target_dir.glob("*.json"):
            if file.name.endswith("batch_summary.json"):
                continue
            try:
                content = file.read_text(encoding="utf-8")
                doc = DocumentResult.model_validate_json(content)
                self.index_document(doc)
                indexed_count += 1
            except Exception:
                continue

        return indexed_count

    def count(self) -> int:
        """Return total indexed documents."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM documents;")
            return int(cursor.fetchone()[0])

    def delete_by_hash(self, file_hash: str) -> bool:
        """Remove document from index by hash."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT doc_id FROM documents WHERE file_hash = ?;", (file_hash,))
            row = cursor.fetchone()
            if not row:
                return False
            doc_id = row[0]
            cursor.execute("DELETE FROM documents WHERE doc_id = ?;", (doc_id,))
            cursor.execute("DELETE FROM documents_fts WHERE doc_id = ?;", (doc_id,))
            conn.commit()
            return True

    def clear(self) -> None:
        """Empty all index tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM documents;")
            cursor.execute("DELETE FROM documents_fts;")
            conn.commit()
