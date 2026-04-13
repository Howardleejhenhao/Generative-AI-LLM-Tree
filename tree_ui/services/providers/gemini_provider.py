from __future__ import annotations

import json
from typing import Iterator
from urllib import error, parse, request

from tree_ui.services.context_builder import ContextMessage
from tree_ui.services.attachments import encode_attachment_as_data_url
from tree_ui.services.providers.base import (
    BaseProvider,
    GenerationResult,
    ProviderError,
    iter_sse_events,
)


def _build_contents(messages: list[ContextMessage]) -> list[dict]:
    contents = []
    for message in messages:
        if message.role == "system":
            continue
        role = "model" if message.role == "assistant" else "user"
        contents.append(
            {
                "role": role,
                "parts": _build_parts(message),
            }
        )
    return contents


def _build_parts(message: ContextMessage) -> list[dict]:
    parts: list[dict] = [{"text": message.content}]
    for attachment in message.attachments:
        data_url = encode_attachment_as_data_url(
            file_path=attachment.file_path,
            content_type=attachment.content_type,
        )
        _, encoded = data_url.split(",", 1)
        parts.append(
            {
                "inline_data": {
                    "mime_type": attachment.content_type or "application/octet-stream",
                    "data": encoded,
                }
            }
        )
    return parts


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


def _build_payload(
    *,
    messages: list[ContextMessage],
    system_instruction: str,
    temperature: float | None,
    top_p: float | None,
    max_output_tokens: int | None,
) -> dict:
    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}],
        },
        "contents": _build_contents(messages),
    }
    generation_config = {}
    if temperature is not None:
        generation_config["temperature"] = temperature
    if top_p is not None:
        generation_config["topP"] = top_p
    if max_output_tokens is not None:
        generation_config["maxOutputTokens"] = max_output_tokens
    if generation_config:
        payload["generationConfig"] = generation_config
    return payload


def _extract_stream_delta(response_data: dict) -> str:
    if "error" in response_data:
        message = response_data["error"].get("message") or "Gemini streaming request failed."
        raise ProviderError(message)

    fragments: list[str] = []
    for candidate in response_data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if isinstance(text, str) and text:
                fragments.append(text)

    return "".join(fragments)


class GeminiProvider(BaseProvider):
    provider_name = "gemini"
    endpoint_template = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model_name}:generateContent?key={api_key}"
    )
    streaming_endpoint_template = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "{model_name}:streamGenerateContent?alt=sse&key={api_key}"
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
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
    ) -> GenerationResult:
        if not self.api_key:
            raise ProviderError("Gemini API key is not configured.")

        payload = _build_payload(
            messages=messages,
            system_instruction=system_instruction,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
        )
        response_data = self._post_json(payload, model_name=model_name)
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
            raise ProviderError("Gemini API key is not configured.")

        payload = _build_payload(
            messages=messages,
            system_instruction=system_instruction,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
        )
        yield from self._post_sse(payload, model_name=model_name)

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

    def _post_sse(self, payload: dict, *, model_name: str) -> Iterator[str]:
        endpoint = self.streaming_endpoint_template.format(
            model_name=parse.quote(model_name, safe=""),
            api_key=parse.quote(self.api_key, safe=""),
        )
        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
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
            raise ProviderError(f"Gemini request failed: {exc.code} {body}") from exc
        except error.URLError as exc:
            raise ProviderError(f"Gemini connection failed: {exc.reason}") from exc

        if not emitted_delta:
            raise ProviderError("Gemini stream did not contain text output.")
