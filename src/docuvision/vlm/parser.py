"""JSON extraction, syntax repair, and Pydantic validation for VLM responses."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple, Type

from pydantic import BaseModel, ValidationError


class VLMParser:
    """Robust parser that strips markdown fences, repairs malformed JSON, and validates models."""

    @staticmethod
    def extract_json_substring(raw: str) -> str:
        """Locate and isolate the outermost JSON object within raw text."""
        cleaned = raw.strip()

        # Strip markdown fences if present
        fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
        if fenced_match:
            cleaned = fenced_match.group(1).strip()

        # Locate first open brace and last close brace
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start != -1 and end != -1 and end > start:
            return cleaned[start : end + 1]

        return cleaned

    @classmethod
    def repair_json(cls, bad_json: str) -> str:
        """Apply targeted regex repairs for common VLM JSON generation quirks."""
        s = bad_json

        # Remove trailing commas right before closing braces or brackets: [1, 2, ] -> [1, 2]
        s = re.sub(r",\s*([\]}])", r"\1", s)

        # Replace single-quoted property names with double-quoted: {'key': ...} -> {"key": ...}
        s = re.sub(r"(?<=[{,\s])'([a-zA-Z0-9_]+)'\s*:", r'"\1":', s)

        # Replace single-quoted string values: : 'value' -> : "value"
        s = re.sub(r":\s*'([^']*)'", r': "\1"', s)

        # Fix Python booleans and None: True -> true, False -> false, None -> null
        s = re.sub(r"\bTrue\b", "true", s)
        s = re.sub(r"\bFalse\b", "false", s)
        s = re.sub(r"\bNone\b", "null", s)

        return s

    def parse_raw(self, raw_text: str) -> Dict[str, Any]:
        """Parse raw model string into a Python dictionary, attempting auto-repair if required."""
        target = self.extract_json_substring(raw_text)

        # Direct parse attempt
        try:
            return json.loads(target)
        except json.JSONDecodeError:
            pass

        # Repaired parse attempt
        repaired = self.repair_json(target)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as err:
            raise ValueError(
                f"Failed to parse VLM response into valid JSON: {err}. Raw output was: {raw_text[:200]}"
            ) from err

    def parse_and_validate(
        self,
        raw_text: str,
        schema_cls: Type[BaseModel],
    ) -> Tuple[Dict[str, Any], bool, List[str]]:
        """Parse raw response and validate against the target Pydantic schema class.

        Returns:
            Tuple of (data_dict, is_valid, list_of_error_strings).
        """
        try:
            parsed = self.parse_raw(raw_text)
        except Exception as err:
            return {}, False, [str(err)]

        try:
            validated = schema_cls.model_validate(parsed)
            return validated.model_dump(), True, []
        except ValidationError as val_err:
            errors = [f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in val_err.errors()]
            # Return raw parsed dictionary as best-effort fallback alongside error list
            return parsed, False, errors
