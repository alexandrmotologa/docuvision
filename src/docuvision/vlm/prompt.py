"""Prompt construction for multimodal vision-language model document extraction."""

from __future__ import annotations

import json
from typing import Optional, Type

from pydantic import BaseModel


class PromptBuilder:
    """Constructs structured multimodal prompts with JSON Schema constraints."""

    SYSTEM_PROMPT = (
        "You are DocuVision, an expert zero-cloud multimodal document extraction engine. "
        "Your task is to accurately extract structured information from document page images "
        "and return ONLY valid, well-formed JSON matching the specified JSON Schema. "
        "Never invent, hallucinate, or estimate numbers, dates, or values. "
        "If a field cannot be found or is illegible, set its value to null. "
        "Respond with raw JSON only. Do not include markdown formatting or commentary."
    )

    def build_user_prompt(
        self,
        schema_cls: Type[BaseModel],
        page_number: int,
        total_pages: int,
        ocr_hint: Optional[str] = None,
        table_markdown_hints: Optional[str] = None,
        custom_instructions: Optional[str] = None,
    ) -> str:
        """Compose context-rich prompt guiding the vision model."""
        json_schema = schema_cls.model_json_schema()
        schema_str = json.dumps(json_schema, indent=2)

        parts = [
            f"Extract structured document information from Page {page_number} of {total_pages}.",
            "",
            "TARGET JSON SCHEMA:",
            schema_str,
            "",
            "EXTRACTION RULES:",
            "1. Output ONLY a valid JSON object matching the JSON Schema above.",
            "2. Transcribe numbers, dates, and amounts exactly as they appear in the image.",
            "3. If a field is not present in the document, output null.",
            "4. For currency amounts, provide numeric floats without currency symbols (e.g. 129.99, not '$129.99').",
        ]

        if ocr_hint and ocr_hint.strip():
            # Include snippet of OCR text to disambiguate blurred characters
            trimmed_ocr = ocr_hint.strip()[:1500]
            parts.extend(
                [
                    "",
                    "DETECTED TEXT HINTS FROM DOCUMENT:",
                    trimmed_ocr,
                ]
            )

        if table_markdown_hints and table_markdown_hints.strip():
            parts.extend(
                [
                    "",
                    "PRE-DETECTED TABLE STRUCTURES:",
                    table_markdown_hints.strip(),
                ]
            )

        if custom_instructions and custom_instructions.strip():
            parts.extend(
                [
                    "",
                    "ADDITIONAL USER DIRECTIVES:",
                    custom_instructions.strip(),
                ]
            )

        parts.extend(
            [
                "",
                "OUTPUT (Valid JSON only):",
            ]
        )

        return "\n".join(parts)
