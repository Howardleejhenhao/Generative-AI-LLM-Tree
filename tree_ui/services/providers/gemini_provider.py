from __future__ import annotations

import json
from urllib import error, parse, request

from tree_ui.services.context_builder import ContextMessage
from tree_ui.services.providers.base import BaseProvider, GenerationResult, ProviderError


def _build_contents(messages: list[ContextMessage]) -> list[dict]:
    contents = []
    for message in messages:
        if message.role == "system":
            continue
        role = "model" if message.role == "assistant" else "user"
        contents.append(
            {
                "role": role,
                "parts": [{"text": message.content}],
            }
        )
    return contents


def _extract_text(response_data: dict) -> str:
    fragments: list[str] = []
    for candidate in response_data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                fragments.append(text.strip())
    combined = "\n".join(fragments).strip()
    if not combined:
        raise ProviderError("Gemini response did not contain text output.")
    return combined


class GeminiProvider(BaseProvider):
    provider_name = "gemini"
    endpoint_template = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model_name}:generateContent?key={api_key}"
    )

    def __init__(self, *, api_key: str, timeout_seconds: int):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def generate(
        self,
        *,
        model_name: str,
        messages: list[ContextMessage],
        system_instruction: str,
    ) -> GenerationResult:
        if not self.api_key:
            raise ProviderError("Gemini API key is not configured.")

        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}],
            },
            "contents": _build_contents(messages),
        }
        response_data = self._post_json(payload, model_name=model_name)
        return GenerationResult(
            text=_extract_text(response_data),
            provider=self.provider_name,
            model_name=model_name,
        )

    def _post_json(self, payload: dict, *, model_name: str) -> dict:
        endpoint = self.endpoint_template.format(
            model_name=parse.quote(model_name, safe=""),
            api_key=parse.quote(self.api_key, safe=""),
        )
        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise ProviderError(f"Gemini request failed: {exc.code} {body}") from exc
        except error.URLError as exc:
            raise ProviderError(f"Gemini connection failed: {exc.reason}") from exc
