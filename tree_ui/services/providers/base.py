from __future__ import annotations

from dataclasses import dataclass

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
