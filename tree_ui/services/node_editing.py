from __future__ import annotations

from django.db import transaction

from tree_ui.models import ConversationNode, NodeMessage


def _build_summary_from_messages(messages: list[dict]) -> str:
    primary_content = next(
        (
            item["content"].strip()
            for item in messages
            if item["role"] == NodeMessage.Role.USER and item["content"].strip()
        ),
        "",
    )
    if not primary_content:
        primary_content = next(
            (item["content"].strip() for item in messages if item["content"].strip()),
            "",
        )
    if len(primary_content) <= 92:
        return primary_content
    return f"{primary_content[:89]}..."


def _validated_messages(messages: list[dict]) -> list[dict]:
    if not messages:
        raise ValueError("Edited node must contain at least one message.")

    validated = []
    for index, message in enumerate(messages):
        role = message.get("role", "").strip()
        content = message.get("content", "").strip()
        if role not in NodeMessage.Role.values:
            raise ValueError("Edited node contains an unsupported message role.")
        if not content:
            raise ValueError("Edited node messages cannot be empty.")
        validated.append(
            {
                "role": role,
                "content": content,
                "order_index": index,
            }
        )
    return validated


def create_edited_variant(
    *,
    original_node: ConversationNode,
    title: str,
    messages: list[dict],
) -> ConversationNode:
    validated_messages = _validated_messages(messages)
    variant_count = original_node.edited_variants.count()
    resolved_title = title.strip() or f"{original_node.title} (Edited)"

    with transaction.atomic():
        node = ConversationNode.objects.create(
            workspace=original_node.workspace,
            parent=original_node.parent,
            edited_from=original_node,
            title=resolved_title,
            summary=_build_summary_from_messages(validated_messages),
            provider=original_node.provider,
            model_name=original_node.model_name,
            system_prompt=original_node.system_prompt,
            temperature=original_node.temperature,
            top_p=original_node.top_p,
            max_output_tokens=original_node.max_output_tokens,
            position_x=original_node.position_x + 60,
            position_y=original_node.position_y + 140 + (variant_count * 60),
        )
        NodeMessage.objects.bulk_create(
            [
                NodeMessage(
                    node=node,
                    role=message["role"],
                    content=message["content"],
                    order_index=message["order_index"],
                )
                for message in validated_messages
            ]
        )

    return ConversationNode.objects.prefetch_related("messages").get(pk=node.pk)
