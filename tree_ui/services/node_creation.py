from __future__ import annotations

import time

from django.conf import settings
from django.db import transaction

from tree_ui.models import ConversationNode, NodeMessage, Workspace
from tree_ui.services.context_builder import (
    SYSTEM_INSTRUCTION,
    build_branch_lineage,
    build_generation_messages,
)
from tree_ui.services.providers import ProviderError, generate_text

DEFAULT_MODELS = {
    ConversationNode.Provider.OPENAI: "gpt-4.1-mini",
    ConversationNode.Provider.GEMINI: "gemini-2.0-flash",
}


def _build_summary(prompt: str) -> str:
    prompt = " ".join(prompt.split())
    if len(prompt) <= 92:
        return prompt
    return f"{prompt[:89]}..."


def _build_title(title: str, prompt: str) -> str:
    clean_title = title.strip()
    if clean_title:
        return clean_title

    compact_prompt = " ".join(prompt.split())
    if len(compact_prompt) <= 42:
        return compact_prompt or "Untitled node"
    return f"{compact_prompt[:39]}..."


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
) -> str:
    context_messages = build_generation_messages(parent=parent, prompt=prompt)
    try:
        result = generate_text(
            provider_name=provider,
            model_name=model_name,
            messages=context_messages,
            system_instruction=SYSTEM_INSTRUCTION,
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
    prompt: str,
    provider: str,
    model_name: str,
) -> dict:
    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        raise ValueError("Prompt is required.")

    if provider not in ConversationNode.Provider.values:
        raise ValueError("Unsupported provider.")

    resolved_model = model_name.strip() or DEFAULT_MODELS[provider]
    position_x, position_y = _calculate_position(workspace=workspace, parent=parent)

    return {
        "prompt": normalized_prompt,
        "provider": provider,
        "model_name": resolved_model,
        "title": _build_title(title, normalized_prompt),
        "summary": _build_summary(normalized_prompt),
        "position_x": position_x,
        "position_y": position_y,
    }


def iter_text_chunks(text: str, chunk_size: int = 24):
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]
        if settings.LLM_STREAM_CHUNK_DELAY_SECONDS > 0:
            time.sleep(settings.LLM_STREAM_CHUNK_DELAY_SECONDS)


def create_node_with_reply(
    *,
    workspace: Workspace,
    parent: ConversationNode | None,
    resolved_inputs: dict,
    assistant_reply: str,
) -> ConversationNode:
    with transaction.atomic():
        node = ConversationNode.objects.create(
            workspace=workspace,
            parent=parent,
            title=resolved_inputs["title"],
            summary=resolved_inputs["summary"],
            provider=resolved_inputs["provider"],
            model_name=resolved_inputs["model_name"],
            position_x=resolved_inputs["position_x"],
            position_y=resolved_inputs["position_y"],
        )
        NodeMessage.objects.bulk_create(
            [
                NodeMessage(
                    node=node,
                    role=NodeMessage.Role.USER,
                    content=resolved_inputs["prompt"],
                    order_index=0,
                ),
                NodeMessage(
                    node=node,
                    role=NodeMessage.Role.ASSISTANT,
                    content=assistant_reply,
                    order_index=1,
                ),
            ]
        )
    return ConversationNode.objects.prefetch_related("messages").get(pk=node.pk)


def create_node(
    *,
    workspace: Workspace,
    parent: ConversationNode | None,
    title: str,
    prompt: str,
    provider: str,
    model_name: str,
) -> ConversationNode:
    resolved_inputs = resolve_node_creation_inputs(
        workspace=workspace,
        parent=parent,
        title=title,
        prompt=prompt,
        provider=provider,
        model_name=model_name,
    )
    assistant_reply = generate_assistant_reply(
        parent=parent,
        provider=resolved_inputs["provider"],
        model_name=resolved_inputs["model_name"],
        prompt=resolved_inputs["prompt"],
    )
    return create_node_with_reply(
        workspace=workspace,
        parent=parent,
        resolved_inputs=resolved_inputs,
        assistant_reply=assistant_reply,
    )
