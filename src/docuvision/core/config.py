"""Configuration management for DocuVision."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocuVisionSettings(BaseSettings):
    """Central configuration for rasterization, table parsing, and local VLM extraction."""

    model_config = SettingsConfigDict(
        env_prefix="DOCUVISION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Local VLM Provider Settings
    vlm_provider: Literal["ollama", "openai_compatible", "vllm", "direct"] = Field(
        default="ollama",
        description="Local VLM backend engine: 'ollama', 'openai_compatible', 'vllm', or 'direct'",
    )
    vlm_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for local VLM server (e.g. Ollama: http://localhost:11434, LM Studio: http://localhost:1234/v1, vLLM: http://localhost:8000/v1)",
    )
    vlm_model: str = Field(
        default="llama3.2-vision:latest",
        description="Target vision model tag or name (e.g. llama3.2-vision:latest, qwen2-vl:7b, minicpm-v:latest)",
    )
    vlm_api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for authenticated local gateways or proxies",
    )
    vlm_timeout_seconds: float = Field(
        default=120.0,
        description="Maximum request timeout in seconds for VLM inference calls",
    )
    vlm_max_tokens: int = Field(
        default=4096,
        description="Maximum token output for structured JSON responses",
    )
    vlm_temperature: float = Field(
        default=0.0,
        description="Sampling temperature for deterministic structured extraction",
    )
    vlm_retries: int = Field(
        default=3,
        description="Number of retry attempts upon transient VLM connection or JSON parse errors",
    )

    # Rasterization & Preprocessing Settings
    raster_dpi: int = Field(
        default=200,
        ge=72,
        le=600,
        description="DPI resolution for rendering PDF pages to high-fidelity raster images",
    )
    raster_max_dim: int = Field(
        default=2048,
        ge=512,
        le=8192,
        description="Maximum pixel dimension along the longest edge to prevent VLM context exhaustion",
    )
    raster_grayscale: bool = Field(
        default=False,
        description="Render raster images in grayscale to save memory on monochrome documents",
    )
    auto_rotate: bool = Field(
        default=True,
        description="Detect and apply orientation correction based on PDF metadata",
    )

    # Table Extraction Settings
    table_extraction_mode: Literal["hybrid", "deterministic", "vlm"] = Field(
        default="hybrid",
        description="Table extraction strategy: 'hybrid' (deterministic layout + VLM refinement), 'deterministic' (PyMuPDF table parser), or 'vlm'",
    )
    table_min_confidence: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for detected tables",
    )
    enable_line_item_math_check: bool = Field(
        default=True,
        description="Validate row multiplication (qty * price == total) and subtotal reconciliation",
    )

    # Server & Storage Settings
    server_host: str = Field(default="127.0.0.1", description="FastAPI Web Studio binding host")
    server_port: int = Field(default=8000, description="FastAPI Web Studio binding port")
    output_dir: Path = Field(default=Path("./outputs"), description="Directory to store extracted JSON, tables, and images")
    temp_dir: Path = Field(default=Path("./temp"), description="Temporary workspace directory")

    def get_chat_endpoint(self) -> str:
        """Resolve chat/completions endpoint based on provider."""
        base = self.vlm_base_url.rstrip("/")
        if self.vlm_provider == "ollama":
            return f"{base}/api/chat"
        elif self.vlm_provider in ("openai_compatible", "vllm"):
            if base.endswith("/v1"):
                return f"{base}/chat/completions"
            return f"{base}/v1/chat/completions"
        return f"{base}/v1/chat/completions"

    def get_models_endpoint(self) -> str:
        """Resolve model listing endpoint based on provider."""
        base = self.vlm_base_url.rstrip("/")
        if self.vlm_provider == "ollama":
            return f"{base}/api/tags"
        elif self.vlm_provider in ("openai_compatible", "vllm"):
            if base.endswith("/v1"):
                return f"{base}/models"
            return f"{base}/v1/models"
        return f"{base}/v1/models"


settings = DocuVisionSettings()
