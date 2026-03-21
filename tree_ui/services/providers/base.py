from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterator

from tree_ui.services.context_builder import ContextMessage


@dataclass(frozen=True)
class GenerationResult:
    text: str
    provider: str
    model_name: str
    used_fallback: bool = False
    fallback_reason: str = ""


class ProviderError(RuntimeError):
    pass


class BaseProvider:
    provider_name = ""

    def generate(
        self,
        *,
        model_name: str,
        messages: list[ContextMessage],
        system_instruction: str,
    ) -> GenerationResult:
        raise NotImplementedError

    def generate_stream(
        self,
        *,
        model_name: str,
        messages: list[ContextMessage],
        system_instruction: str,
    ) -> Iterator[str]:
        raise NotImplementedError


def iter_sse_events(response) -> Iterator[dict]:
    event_name = "message"
    data_lines: list[str] = []

    for raw_line in response:
        line = raw_line.decode("utf-8", errors="ignore")
        stripped = line.rstrip("\r\n")

        if stripped == "":
            if data_lines:
                data = "\n".join(data_lines).strip()
                if data == "[DONE]":
                    return
                yield {
                    "event": event_name,
                    "data": json.loads(data) if data else {},
                }
            event_name = "message"
            data_lines = []
            continue

        if stripped.startswith("event:"):
            event_name = stripped[6:].strip()
        elif stripped.startswith("data:"):
            data_lines.append(stripped[5:].strip())

    if data_lines:
        data = "\n".join(data_lines).strip()
        if data != "[DONE]":
            yield {
                "event": event_name,
                "data": json.loads(data) if data else {},
            }
