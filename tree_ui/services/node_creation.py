from __future__ import annotations

import time
from typing import Any

from django.conf import settings
from django.db import transaction

from tree_ui.models import ConversationNode, NodeAttachment, NodeMessage, Workspace
from tree_ui.services.context_builder import (
    build_system_instruction,
    build_branch_lineage,
    build_generation_messages,
)
from tree_ui.services.memory_drafting import refresh_workspace_preference_memory
from tree_ui.services.model_catalog import resolve_model_name
from tree_ui.services.memory_service import format_memories_for_prompt, retrieve_memories_for_generation
from tree_ui.services.providers import ProviderError, generate_text, stream_text
from tree_ui.services.router import route_model


def _build_summary(prompt: str) -> str:
    prompt = " ".join(prompt.split())
    if len(prompt) <= 92:
        return prompt
    return f"{prompt[:89]}..."


def _build_node_title(title: str) -> str:
    clean_title = title.strip()
    if clean_title:
        return clean_title
    return "Untitled conversation"


def _normalize_system_prompt(system_prompt: Any) -> str:
    if system_prompt is None:
        return ""
    if not isinstance(system_prompt, str):
        raise ValueError("System prompt must be a string.")
    return system_prompt.strip()


def _normalize_optional_float(
    *,
    value: Any,
    field_label: str,
    minimum: float,
    maximum: float,
) -> float | None:
    if value in (None, ""):
        return None

    try:
        normalized_value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_label} must be a number.") from exc

    if normalized_value < minimum or normalized_value > maximum:
        raise ValueError(f"{field_label} must be between {minimum} and {maximum}.")

    return round(normalized_value, 4)


def _normalize_max_output_tokens(value: Any) -> int | None:
    if value in (None, ""):
        return None

    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("Max output tokens must be an integer.")
        normalized_value = int(value)
    else:
        if isinstance(value, str) and "." in value:
            raise ValueError("Max output tokens must be an integer.")
        try:
            normalized_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Max output tokens must be an integer.") from exc

    if normalized_value <= 0:
        raise ValueError("Max output tokens must be greater than 0.")

    return normalized_value


def _build_fallback_assistant_message(
    *,
    parent: ConversationNode | None,
    provider: str,
    model_name: str,
    prompt: str,
    reason: str,
) -> str:
    lineage = build_branch_lineage(parent)
    lineage_titles = " -> ".join(node.title for node in lineage) or "root"
    return (
        f"[Fallback {provider} response via {model_name}] "
        f"Branch context follows: {lineage_titles}. "
        f"Latest prompt: {prompt.strip()} "
        f"(Reason: {reason})"
    )


def generate_assistant_reply(
    *,
    parent: ConversationNode | None,
    provider: str,
    model_name: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float | None = None,
    top_p: float | None = None,
    max_output_tokens: int | None = None,
    prompt_attachments: list[NodeAttachment] | None = None,
) -> str:
    context_messages = build_generation_messages(
        parent=parent,
        prompt=prompt,
        prompt_attachments=prompt_attachments,
    )
    memory_text = ""
    if parent is not None:
        memory_text = format_memories_for_prompt(
            retrieve_memories_for_generation(
                workspace=parent.workspace,
                parent=parent,
            )
        )
    try:
        result = generate_text(
            provider_name=provider,
            model_name=model_name,
            messages=context_messages,
            system_instruction=build_system_instruction(
                system_prompt,
                retrieved_memory_text=memory_text,
            ),
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
        )
        return result.text
    except ProviderError as exc:
        return _build_fallback_assistant_message(
            parent=parent,
            provider=provider,
            model_name=model_name,
            prompt=prompt,
            reason=str(exc),
        )


def _calculate_position(
    *,
    workspace: Workspace,
    parent: ConversationNode | None,
) -> tuple[int, int]:
    if parent is None:
        root_count = workspace.nodes.filter(parent__isnull=True).count()
        return 80, 120 + (root_count * 190)

    sibling_count = parent.children.count()
    return parent.position_x + 340, parent.position_y + (sibling_count * 180)


def resolve_node_creation_inputs(
    *,
    workspace: Workspace,
    parent: ConversationNode | None,
    title: str,
    provider: str,
    model_name: str,
    routing_mode: str = ConversationNode.RoutingMode.MANUAL,
    system_prompt: Any,
    temperature: Any,
    top_p: Any,
    max_output_tokens: Any,
    prompt: str = "",
    has_attachments: bool = False,
) -> dict:
    if routing_mode == ConversationNode.RoutingMode.MANUAL:
        if provider not in ConversationNode.Provider.values:
            raise ValueError("Unsupported provider.")
        resolved_provider = provider
        resolved_model = resolve_model_name(provider=provider, model_name=model_name)
        routing_decision = ""
    else:
        # Routing with available signals.
        routing_result = route_model(
            routing_mode=routing_mode,
            provider=provider,
            has_attachments=has_attachments,
            prompt_length=len(prompt),
        )
        resolved_provider = routing_result.provider
        resolved_model = routing_result.model
        routing_decision = routing_result.decision

    position_x, position_y = _calculate_position(workspace=workspace, parent=parent)

    return {
        "provider": resolved_provider,
        "model_name": resolved_model,
        "routing_mode": routing_mode,
        "routing_decision": routing_decision,
        "title": _build_node_title(title),
        "summary": "Open this node to start the conversation.",
        "system_prompt": _normalize_system_prompt(system_prompt),
        "temperature": _normalize_optional_float(
            value=temperature,
            field_label="Temperature",
            minimum=0.0,
            maximum=2.0,
        ),
        "top_p": _normalize_optional_float(
            value=top_p,
            field_label="Top p",
            minimum=0.0,
            maximum=1.0,
        ),
        "max_output_tokens": _normalize_max_output_tokens(max_output_tokens),
        "position_x": position_x,
        "position_y": position_y,
    }


def resolve_message_append_inputs(*, prompt: str, has_attachments: bool = False) -> dict:
    normalized_prompt = prompt.strip()
    if not normalized_prompt and not has_attachments:
        raise ValueError("Prompt is required.")

    if normalized_prompt:
        summary = _build_summary(normalized_prompt)
    elif has_attachments:
        summary = "Image attachment"
    else:
        summary = "Untitled message"

    return {
        "prompt": normalized_prompt,
        "summary": summary,
    }


def iter_text_chunks(text: str, chunk_size: int = 24):
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]
        if settings.LLM_STREAM_CHUNK_DELAY_SECONDS > 0:
            time.sleep(settings.LLM_STREAM_CHUNK_DELAY_SECONDS)


def stream_assistant_reply(
    *,
    parent: ConversationNode | None,
    provider: str,
    model_name: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float | None = None,
    top_p: float | None = None,
    max_output_tokens: int | None = None,
    prompt_attachments: list[NodeAttachment] | None = None,
):
    context_messages = build_generation_messages(
        parent=parent,
        prompt=prompt,
        prompt_attachments=prompt_attachments,
    )
    emitted_chunk = False
    memory_text = ""
    if parent is not None:
        memory_text = format_memories_for_prompt(
            retrieve_memories_for_generation(
                workspace=parent.workspace,
                parent=parent,
            )
        )

    try:
        for chunk in stream_text(
            provider_name=provider,
            model_name=model_name,
            messages=context_messages,
            system_instruction=build_system_instruction(
                system_prompt,
                retrieved_memory_text=memory_text,
            ),
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
        ):
            emitted_chunk = True
            yield chunk
    except ProviderError as exc:
        if emitted_chunk:
            raise

        fallback_message = _build_fallback_assistant_message(
            parent=parent,
            provider=provider,
            model_name=model_name,
            prompt=prompt,
            reason=str(exc),
        )
        yield from iter_text_chunks(fallback_message)


def create_node(
    *,
    workspace: Workspace,
    parent: ConversationNode | None,
    title: str,
    provider: str,
    model_name: str,
    routing_mode: str = ConversationNode.RoutingMode.MANUAL,
    system_prompt: Any = "",
    temperature: Any = None,
    top_p: Any = None,
    max_output_tokens: Any = None,
    prompt: str = "",
    has_attachments: bool = False,
) -> ConversationNode:
    resolved_inputs = resolve_node_creation_inputs(
        workspace=workspace,
        parent=parent,
        title=title,
        provider=provider,
        model_name=model_name,
        routing_mode=routing_mode,
        system_prompt=system_prompt,
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_output_tokens,
        prompt=prompt,
        has_attachments=has_attachments,
    )
    return ConversationNode.objects.create(
        workspace=workspace,
        parent=parent,
        title=resolved_inputs["title"],
        summary=resolved_inputs["summary"],
        provider=resolved_inputs["provider"],
        model_name=resolved_inputs["model_name"],
        routing_mode=resolved_inputs["routing_mode"],
        routing_decision=resolved_inputs["routing_decision"],
        system_prompt=resolved_inputs["system_prompt"],
        temperature=resolved_inputs["temperature"],
        top_p=resolved_inputs["top_p"],
        max_output_tokens=resolved_inputs["max_output_tokens"],
        position_x=resolved_inputs["position_x"],
        position_y=resolved_inputs["position_y"],
    )


def create_continuation_child(
    *,
    source_node: ConversationNode,
    title: str,
    prompt: str = "",
    has_attachments: bool = False,
) -> ConversationNode:
    return create_node(
        workspace=source_node.workspace,
        parent=source_node,
        title=title,
        provider=source_node.provider,
        model_name=source_node.model_name,
        routing_mode=source_node.routing_mode,
        system_prompt=source_node.system_prompt,
        temperature=source_node.temperature,
        top_p=source_node.top_p,
        max_output_tokens=source_node.max_output_tokens,
        prompt=prompt,
        has_attachments=has_attachments,
    )


def append_messages_to_node_with_reply(
    *,
    node: ConversationNode,
    prompt: str,
    assistant_reply: str,
    prompt_attachments: list[NodeAttachment] | None = None,
) -> ConversationNode:
    resolved_inputs = resolve_message_append_inputs(
        prompt=prompt,
        has_attachments=bool(prompt_attachments),
    )
    starting_order = node.messages.count()

    with transaction.atomic():
        user_message = NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.USER,
            content=resolved_inputs["prompt"],
            order_index=starting_order,
        )
        NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.ASSISTANT,
            content=assistant_reply,
            order_index=starting_order + 1,
        )
        if prompt_attachments:
            NodeAttachment.objects.filter(
                pk__in=[attachment.pk for attachment in prompt_attachments],
            ).update(source_message=user_message)
        node.summary = resolved_inputs["summary"]
        node.save(update_fields=["summary", "updated_at"])

    updated_node = ConversationNode.objects.prefetch_related("messages__attachments", "attachments").get(pk=node.pk)

    try:
        refresh_workspace_preference_memory(updated_node)
    except Exception:
        # Memory refresh is best-effort and must not break the main chat flow.
        pass

    return updated_node


def append_messages_to_node(
    *,
    node: ConversationNode,
    prompt: str,
    prompt_attachments: list[NodeAttachment] | None = None,
) -> ConversationNode:
    resolved_inputs = resolve_message_append_inputs(
        prompt=prompt,
        has_attachments=bool(prompt_attachments),
    )
    assistant_reply = generate_assistant_reply(
        parent=node,
        provider=node.provider,
        model_name=node.model_name,
        prompt=resolved_inputs["prompt"],
        system_prompt=node.system_prompt,
        temperature=node.temperature,
        top_p=node.top_p,
        max_output_tokens=node.max_output_tokens,
        prompt_attachments=prompt_attachments,
    )
    return append_messages_to_node_with_reply(
        node=node,
        prompt=resolved_inputs["prompt"],
        assistant_reply=assistant_reply,
        prompt_attachments=prompt_attachments,
    )
