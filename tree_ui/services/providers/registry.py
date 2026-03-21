from __future__ import annotations

from typing import Iterator

from django.conf import settings

from tree_ui.models import ConversationNode
from tree_ui.services.context_builder import ContextMessage
from tree_ui.services.providers.base import GenerationResult, ProviderError
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
) -> GenerationResult:
    provider = _get_provider(provider_name)
    return provider.generate(
        model_name=model_name,
        messages=messages,
        system_instruction=system_instruction,
    )


def stream_text(
    *,
    provider_name: str,
    model_name: str,
    messages: list[ContextMessage],
    system_instruction: str,
) -> Iterator[str]:
    provider = _get_provider(provider_name)
    return provider.generate_stream(
        model_name=model_name,
        messages=messages,
        system_instruction=system_instruction,
    )
