from __future__ import annotations

import json
from urllib import error, request

from tree_ui.services.context_builder import ContextMessage
from tree_ui.services.providers.base import BaseProvider, GenerationResult, ProviderError


def _extract_text(response_data: dict) -> str:
    direct_text = response_data.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    fragments: list[str] = []
    for item in response_data.get("output", []):
        if item.get("type") != "message":
            continue
        for content_item in item.get("content", []):
            text = content_item.get("text")
            if isinstance(text, str) and text.strip():
                fragments.append(text.strip())

    combined = "\n".join(fragments).strip()
    if not combined:
        raise ProviderError("OpenAI response did not contain text output.")
    return combined


class OpenAIProvider(BaseProvider):
    provider_name = "openai"
    endpoint = "https://api.openai.com/v1/responses"

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
            raise ProviderError("OpenAI API key is not configured.")

        payload = {
            "model": model_name,
            "instructions": system_instruction,
            "input": [
                {
                    "role": message.role,
                    "content": message.content,
                }
                for message in messages
            ],
        }
        response_data = self._post_json(payload)
        return GenerationResult(
            text=_extract_text(response_data),
            provider=self.provider_name,
            model_name=model_name,
        )

    def _post_json(self, payload: dict) -> dict:
        http_request = request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise ProviderError(f"OpenAI request failed: {exc.code} {body}") from exc
        except error.URLError as exc:
            raise ProviderError(f"OpenAI connection failed: {exc.reason}") from exc
