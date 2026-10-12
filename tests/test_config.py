"""Tests for configuration settings and endpoint resolvers."""

from docuvision.core.config import DocuVisionSettings


def test_default_settings():
    s = DocuVisionSettings()
    assert s.vlm_provider == "ollama"
    assert "11434" in s.vlm_base_url
    assert s.raster_dpi == 200
    assert s.table_extraction_mode == "hybrid"


def test_ollama_endpoints():
    s = DocuVisionSettings(vlm_provider="ollama", vlm_base_url="http://localhost:11434")
    assert s.get_chat_endpoint() == "http://localhost:11434/api/chat"
    assert s.get_models_endpoint() == "http://localhost:11434/api/tags"


def test_openai_compatible_endpoints():
    s = DocuVisionSettings(vlm_provider="openai_compatible", vlm_base_url="http://localhost:1234/v1")
    assert s.get_chat_endpoint() == "http://localhost:1234/v1/chat/completions"
    assert s.get_models_endpoint() == "http://localhost:1234/v1/models"


def test_vllm_endpoints():
    s = DocuVisionSettings(vlm_provider="vllm", vlm_base_url="http://localhost:8000")
    assert s.get_chat_endpoint() == "http://localhost:8000/v1/chat/completions"
    assert s.get_models_endpoint() == "http://localhost:8000/v1/models"
