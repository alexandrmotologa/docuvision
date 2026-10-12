"""Local Vision-Language Model client for Ollama, vLLM, and OpenAI-compatible endpoints."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from docuvision.core.config import DocuVisionSettings
from docuvision.core.config import settings as default_settings


class VLMClient:
    """Asynchronous client interacting with locally hosted multimodal models."""

    def __init__(self, settings: Optional[DocuVisionSettings] = None) -> None:
        self.settings = settings or default_settings

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.vlm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.vlm_api_key}"
        return headers

    async def check_health(self) -> Dict[str, Any]:
        """Probe local model server status and fetch list of active models."""
        endpoint = self.settings.get_models_endpoint()
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(endpoint, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    models: List[str] = []
                    if self.settings.vlm_provider == "ollama":
                        models = [m.get("name", "") for m in data.get("models", [])]
                    else:
                        models = [m.get("id", "") for m in data.get("data", [])]

                    return {
                        "status": "online",
                        "provider": self.settings.vlm_provider,
                        "base_url": self.settings.vlm_base_url,
                        "current_model": self.settings.vlm_model,
                        "available_models": models,
                        "latency_ms": round(res.elapsed.total_seconds() * 1000, 2),
                    }
                return {
                    "status": "degraded",
                    "provider": self.settings.vlm_provider,
                    "status_code": res.status_code,
                    "error": res.text[:200],
                }
        except Exception as exc:
            return {
                "status": "offline",
                "provider": self.settings.vlm_provider,
                "base_url": self.settings.vlm_base_url,
                "error": str(exc),
            }

    async def generate(
        self,
        prompt: str,
        image_base64: str,
    ) -> str:
        """Submit image and extraction prompt to the local vision model."""
        endpoint = self.settings.get_chat_endpoint()
        headers = self._get_headers()

        # Build payload according to provider convention
        if self.settings.vlm_provider == "ollama":
            payload = {
                "model": self.settings.vlm_model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [image_base64],
                    }
                ],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": self.settings.vlm_temperature,
                    "num_predict": self.settings.vlm_max_tokens,
                },
            }
        else:
            # OpenAI compatible / vLLM schema
            payload = {
                "model": self.settings.vlm_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                            },
                        ],
                    }
                ],
                "response_format": {"type": "json_object"},
                "temperature": self.settings.vlm_temperature,
                "max_tokens": self.settings.vlm_max_tokens,
            }

        last_error: Optional[Exception] = None
        for attempt in range(1, self.settings.vlm_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.vlm_timeout_seconds) as client:
                    resp = await client.post(endpoint, json=payload, headers=headers)
                    if resp.status_code != 200:
                        raise RuntimeError(f"VLM Server error (HTTP {resp.status_code}): {resp.text[:300]}")

                    data = resp.json()
                    if self.settings.vlm_provider == "ollama":
                        return data.get("message", {}).get("content", "")
                    else:
                        choices = data.get("choices", [])
                        if choices:
                            return choices[0].get("message", {}).get("content", "")
                        return ""
            except Exception as err:
                last_error = err
                if attempt < self.settings.vlm_retries:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                else:
                    break

        raise RuntimeError(f"VLM call failed after {self.settings.vlm_retries} attempts: {last_error}")

    def generate_sync(self, prompt: str, image_base64: str) -> str:
        """Synchronous wrapper for execution in non-async contexts."""
        return asyncio.run(self.generate(prompt=prompt, image_base64=image_base64))
