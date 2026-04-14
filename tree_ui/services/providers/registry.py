from __future__ import annotations

from typing import Iterator

from django.conf import settings

from tree_ui.models import ConversationNode
from tree_ui.services.context_builder import ContextMessage
from tree_ui.services.model_catalog import resolve_model_name
from tree_ui.services.providers.base import GenerationResult, ProviderDelta, ProviderError
from tree_ui.services.providers.gemini_provider import GeminiProvider
from tree_ui.services.providers.openai_provider import OpenAIProvider


def _get_provider(provider_name: str):
    if provider_name == ConversationNode.Provider.OPENAI:
        return OpenAIProvider(
            api_key=settings.OPENAI_API_KEY,
            timeout_seconds=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )

    if provider_name == ConversationNode.Provider.GEMINI:
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            timeout_seconds=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )

    raise ProviderError(f"Unsupported provider: {provider_name}")


def generate_text(
    *,
    provider_name: str,
    model_name: str,
    messages: list[ContextMessage],
    system_instruction: str,
    tools: list[dict] | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    max_output_tokens: int | None = None,
) -> GenerationResult:
    provider = _get_provider(provider_name)
    resolved_model_name = resolve_model_name(provider=provider_name, model_name=model_name)
    return provider.generate(
        model_name=resolved_model_name,
        messages=messages,
        system_instruction=system_instruction,
        tools=tools,
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_output_tokens,
    )


def stream_text(
    *,
    provider_name: str,
    model_name: str,
    messages: list[ContextMessage],
    system_instruction: str,
    tools: list[dict] | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    max_output_tokens: int | None = None,
) -> Iterator[ProviderDelta]:
    provider = _get_provider(provider_name)
    resolved_model_name = resolve_model_name(provider=provider_name, model_name=model_name)
    return provider.generate_stream(
        model_name=resolved_model_name,
        messages=messages,
        system_instruction=system_instruction,
        tools=tools,
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_output_tokens,
    )
