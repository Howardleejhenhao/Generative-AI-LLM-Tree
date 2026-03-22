from __future__ import annotations

import json
from typing import Iterator
from urllib import error, request

from tree_ui.services.context_builder import ContextMessage
from tree_ui.services.providers.base import (
    BaseProvider,
    GenerationResult,
    ProviderError,
    iter_sse_events,
)


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


def _build_payload(
    *,
    model_name: str,
    messages: list[ContextMessage],
    system_instruction: str,
    stream: bool,
    temperature: float | None,
    top_p: float | None,
    max_output_tokens: int | None,
) -> dict:
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
    if stream:
        payload["stream"] = True
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if max_output_tokens is not None:
        payload["max_output_tokens"] = max_output_tokens
    return payload


def _extract_stream_delta(event_data: dict) -> str:
    event_type = event_data.get("type", "")

    if event_type == "response.output_text.delta":
        return event_data.get("delta", "")

    if event_type in {"error", "response.failed"}:
        message = (
            event_data.get("message")
            or event_data.get("error", {}).get("message")
            or "OpenAI streaming request failed."
        )
        raise ProviderError(message)

    return ""


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
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
    ) -> GenerationResult:
        if not self.api_key:
            raise ProviderError("OpenAI API key is not configured.")

        payload = _build_payload(
            model_name=model_name,
            messages=messages,
            system_instruction=system_instruction,
            stream=False,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
        )
        response_data = self._post_json(payload)
        return GenerationResult(
            text=_extract_text(response_data),
            provider=self.provider_name,
            model_name=model_name,
        )

    def generate_stream(
        self,
        *,
        model_name: str,
        messages: list[ContextMessage],
        system_instruction: str,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
    ) -> Iterator[str]:
        if not self.api_key:
            raise ProviderError("OpenAI API key is not configured.")

        payload = _build_payload(
            model_name=model_name,
            messages=messages,
            system_instruction=system_instruction,
            stream=True,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
        )
        yield from self._post_sse(payload)

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

    def _post_sse(self, payload: dict) -> Iterator[str]:
        http_request = request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )

        emitted_delta = False
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                for event in iter_sse_events(response):
                    delta = _extract_stream_delta(event["data"])
                    if not delta:
                        continue
                    emitted_delta = True
                    yield delta
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise ProviderError(f"OpenAI request failed: {exc.code} {body}") from exc
        except error.URLError as exc:
            raise ProviderError(f"OpenAI connection failed: {exc.reason}") from exc

        if not emitted_delta:
            raise ProviderError("OpenAI stream did not contain text output.")
