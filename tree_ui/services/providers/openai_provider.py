from __future__ import annotations

import json
from typing import Iterator
from urllib import error, request

from tree_ui.services.context_builder import ContextMessage
from tree_ui.services.attachments import encode_attachment_as_data_url
from tree_ui.services.providers.base import (
    BaseProvider,
    GenerationResult,
    ProviderDelta,
    ProviderError,
    ToolCall,
    ToolCallDelta,
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
    return combined


def _extract_tool_calls(response_data: dict) -> list[ToolCall]:
    tool_calls: list[ToolCall] = []
    for item in response_data.get("output", []):
        if item.get("type") == "function_call":
            tool_calls.append(
                ToolCall(
                    call_id=item.get("call_id", item.get("id", "")),
                    name=item.get("name", ""),
                    arguments=_safe_parse_arguments(item.get("arguments", "{}")),
                )
            )
            continue

        # Backward-compatible parser for older mocked Chat Completions-style fixtures.
        if item.get("type") == "tool_calls":
            for tc in item.get("tool_calls", []):
                tool_calls.append(
                    ToolCall(
                        call_id=tc.get("id", ""),
                        name=tc.get("function", {}).get("name", ""),
                        arguments=_safe_parse_arguments(tc.get("function", {}).get("arguments", "{}")),
                    )
                )
    return tool_calls


def _safe_parse_arguments(raw_arguments: str | dict) -> dict:
    if isinstance(raw_arguments, dict):
        return raw_arguments
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {"raw": raw_arguments}
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _map_tools_to_openai(tools: list[dict] | None) -> list[dict]:
    mapped_tools: list[dict] = []
    for tool in tools or []:
        if tool.get("type") != "function":
            mapped_tools.append(tool)
            continue

        function_schema = tool.get("function")
        if isinstance(function_schema, dict):
            mapped_tool = {
                "type": "function",
                "name": function_schema.get("name", ""),
                "description": function_schema.get("description", ""),
                "parameters": function_schema.get("parameters", {}),
            }
            if "strict" in function_schema:
                mapped_tool["strict"] = function_schema["strict"]
            mapped_tools.append(mapped_tool)
            continue

        mapped_tools.append(tool)
    return mapped_tools


def _build_payload(
    *,
    model_name: str,
    messages: list[ContextMessage],
    system_instruction: str,
    stream: bool,
    tools: list[dict] | None,
    temperature: float | None,
    top_p: float | None,
    max_output_tokens: int | None,
) -> dict:
    payload_messages = []
    for message in messages:
        payload_messages.extend(_build_input_items(message))

    payload = {
        "model": model_name,
        "instructions": system_instruction,
        "input": payload_messages,
    }
    if stream:
        payload["stream"] = True
    if tools:
        payload["tools"] = _map_tools_to_openai(tools)
    if temperature is not None:
        payload["temperature"] = temperature
    if top_p is not None:
        payload["top_p"] = top_p
    if max_output_tokens is not None:
        payload["max_output_tokens"] = max_output_tokens
    return payload


def _build_input_items(message: ContextMessage) -> list[dict]:
    if message.role == "tool":
        return [
            {
                "type": "function_call_output",
                "call_id": message.tool_call_id or message.tool_name or "tool_call",
                "output": message.content,
            }
        ]

    items: list[dict] = []
    content_parts = _build_content_parts(message)
    if content_parts:
        items.append(
            {
                "role": message.role,
                "content": content_parts,
            }
        )

    for tool_call in message.tool_calls:
        items.append(
            {
                "type": "function_call",
                "call_id": tool_call.call_id or tool_call.name,
                "name": tool_call.name,
                "arguments": json.dumps(tool_call.arguments),
            }
        )

    return items


def _build_content_parts(message: ContextMessage) -> list[dict]:
    parts: list[dict] = []
    if message.content:
        if message.role == "assistant":
            parts.append({"type": "output_text", "text": message.content})
        else:
            parts.append({"type": "input_text", "text": message.content})
    for attachment in message.attachments:
        data_url = attachment.data_url or encode_attachment_as_data_url(
            file_path=attachment.file_path,
            content_type=attachment.content_type,
        )
        if attachment.kind == "pdf" or attachment.content_type == "application/pdf":
            parts.append(
                {
                    "type": "input_file",
                    "filename": attachment.name or "attachment.pdf",
                    "file_data": data_url,
                }
            )
            continue

        parts.append(
            {
                "type": "input_image",
                "image_url": data_url,
                "detail": "auto",
            }
        )
    return parts


def _extract_stream_delta(
    event_data: dict,
    tool_call_map: dict[str, dict[str, str]] | None = None,
) -> ProviderDelta | None:
    event_type = event_data.get("type", "")

    if event_type == "response.output_text.delta":
        return ProviderDelta(text=event_data.get("delta", ""))

    if event_type == "response.output_item.added":
        item = event_data.get("item", {})
        if item.get("type") != "function_call":
            return None
        item_id = item.get("id", "")
        call_id = item.get("call_id", item_id)
        name = item.get("name", "")
        if tool_call_map is not None and item_id:
            tool_call_map[item_id] = {"call_id": call_id, "name": name}
        return ProviderDelta(
            tool_call=ToolCallDelta(
                call_id=call_id,
                name=name,
                arguments=item.get("arguments", ""),
            )
        )

    if event_type == "response.function_call_arguments.delta":
        item_id = event_data.get("item_id", "")
        tool_call_state = (tool_call_map or {}).get(item_id, {})
        return ProviderDelta(
            tool_call=ToolCallDelta(
                call_id=event_data.get("call_id") or tool_call_state.get("call_id") or item_id,
                name=event_data.get("name") or tool_call_state.get("name", ""),
                arguments=event_data.get("delta", ""),
            )
        )

    if event_type == "response.tool_call.delta":
        delta = event_data.get("delta", {})
        return ProviderDelta(
            tool_call=ToolCallDelta(
                call_id=event_data.get("call_id", ""),
                name=delta.get("name", ""),
                arguments=delta.get("arguments", ""),
            )
        )

    if event_type in {"error", "response.failed"}:
        message = (
            event_data.get("message")
            or event_data.get("error", {}).get("message")
            or "OpenAI streaming request failed."
        )
        raise ProviderError(message)

    return None


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
        tools: list[dict] | None = None,
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
            tools=tools,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
        )
        response_data = self._post_json(payload)
        return GenerationResult(
            text=_extract_text(response_data),
            provider=self.provider_name,
            model_name=model_name,
            tool_calls=_extract_tool_calls(response_data),
        )

    def generate_stream(
        self,
        *,
        model_name: str,
        messages: list[ContextMessage],
        system_instruction: str,
        tools: list[dict] | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
    ) -> Iterator[ProviderDelta]:
        if not self.api_key:
            raise ProviderError("OpenAI API key is not configured.")

        payload = _build_payload(
            model_name=model_name,
            messages=messages,
            system_instruction=system_instruction,
            stream=True,
            tools=tools,
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

    def _post_sse(self, payload: dict) -> Iterator[ProviderDelta]:
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

        emitted_any = False
        try:
            with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                tool_call_map: dict[str, dict[str, str]] = {}
                for event in iter_sse_events(response):
                    delta = _extract_stream_delta(event["data"], tool_call_map)
                    if delta is None:
                        continue
                    emitted_any = True
                    yield delta
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise ProviderError(f"OpenAI request failed: {exc.code} {body}") from exc
        except error.URLError as exc:
            raise ProviderError(f"OpenAI connection failed: {exc.reason}") from exc

        if not emitted_any:
            raise ProviderError("OpenAI stream did not contain output.")
