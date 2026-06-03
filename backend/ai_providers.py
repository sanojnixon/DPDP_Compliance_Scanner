"""
ai_providers.py - swappable multimodal AI provider adapters.

The DPDP pipeline calls this module through the abstract provider interface so
providers can be swapped without touching routes or compliance logic.
"""

import base64
import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv


load_dotenv()


class AIProviderError(Exception):
    """Raised when an AI provider cannot complete a request."""


class VisionAIProvider(ABC):
    name = "unknown"
    model_env_key = ""

    @property
    @abstractmethod
    def configured(self) -> bool:
        """Return whether the provider has enough credentials to run."""

    @abstractmethod
    def analyze(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        max_tokens: int = 1800,
    ) -> str:
        """Return the raw model response text."""


class OpenAICompatibleVisionProvider(VisionAIProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def _build_payload(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        max_tokens: int,
    ) -> Dict[str, Any]:
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a DPDP banking privacy compliance analyst. "
                        "Return only strict JSON. Do not include markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                        },
                    ],
                },
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

    def _extract_content(self, body: Dict[str, Any]) -> str:
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(
                f"{self.name} returned an unexpected response shape."
            ) from exc

        if isinstance(content, list):
            text_parts: List[str] = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
            ]
            return "\n".join(part for part in text_parts if part).strip()
        return str(content).strip()

    def analyze(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        max_tokens: int = 1800,
    ) -> str:
        if not self.configured:
            raise AIProviderError(f"{self.name} is not fully configured.")

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(
                self._build_payload(
                    image_bytes=image_bytes,
                    mime_type=mime_type,
                    prompt=prompt,
                    max_tokens=max_tokens,
                )
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        # Bypass SSL verification — Windows Python often fails on standard CA certs
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds, context=ctx) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise AIProviderError(f"{self.name} returned HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise AIProviderError(f"{self.name} request failed: {exc}") from exc

        return self._extract_content(body)


class GenericVisionProvider(OpenAICompatibleVisionProvider):
    """
    Generic OpenAI-compatible vision provider.
    """

    name = "generic"
    model_env_key = "AI_MODEL"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        super().__init__(
            api_key=api_key or os.getenv("AI_API_KEY", ""),
            model=model or os.getenv("AI_VISION_MODEL") or os.getenv("AI_MODEL", "generic-vision-model"),
            base_url=base_url or os.getenv(
                "AI_BASE_URL",
                "https://api.openai.com/v1",
            ),
            timeout_seconds=float(os.getenv("AI_TIMEOUT_SECONDS", timeout_seconds or 45)),
        )


def get_vision_provider() -> VisionAIProvider:
    return GenericVisionProvider()


def get_provider_diagnostics() -> Dict[str, Any]:
    try:
        provider = get_vision_provider()
        return {
            "provider": provider.name,
            "configured": provider.configured,
            "model": getattr(provider, "model", ""),
            "base_url": getattr(provider, "base_url", ""),
        }
    except Exception as exc:
        return {
            "provider": "unknown",
            "configured": False,
            "model": "",
            "base_url": "",
            "error": str(exc),
        }
