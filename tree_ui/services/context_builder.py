from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from tree_ui.models import ConversationNode, NodeAttachment
from tree_ui.services.attachments import render_pdf_attachment_as_data_urls

SYSTEM_INSTRUCTION = (
    "You are LLM-Tree, an assistant working inside a branching conversation graph. "
    "Use only the messages from the current lineage path. Do not reference sibling "
    "branches or invent hidden context."
)


def build_system_instruction(
    custom_system_prompt: str = "",
    *,
    retrieved_memory_text: str = "",
) -> str:
    normalized_prompt = custom_system_prompt.strip()
    normalized_memory = retrieved_memory_text.strip()

    sections = [SYSTEM_INSTRUCTION]

    if normalized_memory:
        sections.extend(
            [
                "",
                "Long-term memory retrieved separately from the current branch transcript:",
                normalized_memory,
            ]
        )

    if not normalized_prompt:
        return "\n".join(sections)

    sections.extend(
        [
            "",
            "Additional node-specific system prompt:",
            normalized_prompt,
        ]
    )
    return "\n".join(sections)


@dataclass(frozen=True)
class ContextAttachment:
    kind: str
    name: str
    content_type: str
    file_path: str
    data_url: str = ""


@dataclass(frozen=True)
class ContextMessage:
    role: str
    content: str
    attachments: tuple[ContextAttachment, ...] = field(default_factory=tuple)
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_calls: tuple[Any, ...] = field(default_factory=tuple)


def _safe_load_tool_invocation_payload(raw_payload: str) -> dict:
    if not raw_payload:
        return {}
    try:
        return json.loads(raw_payload)
    except json.JSONDecodeError:
        return {
            "error": "Invalid persisted tool arguments JSON",
            "raw": raw_payload,
        }


def build_branch_lineage(parent: ConversationNode | None) -> list[ConversationNode]:
    lineage = []
    current = parent
    while current is not None:
        lineage.append(current)
        current = current.parent
    lineage.reverse()
    return lineage


def build_generation_messages(
    *,
    parent: ConversationNode | None,
    prompt: str,
    prompt_attachments: list[NodeAttachment] | None = None,
    render_pdf_attachments: bool = True,
) -> list[ContextMessage]:
    def build_context_attachments(items) -> tuple[ContextAttachment, ...]:
        attachments: list[ContextAttachment] = []
        for item in items:
            if item.kind == NodeAttachment.Kind.PDF and render_pdf_attachments:
                for index, data_url in enumerate(
                    render_pdf_attachment_as_data_urls(
                        file_path=item.file.path,
                        max_pages=settings.PDF_RENDER_MAX_PAGES,
                    ),
                    start=1,
                ):
                    attachments.append(
                        ContextAttachment(
                            kind=NodeAttachment.Kind.IMAGE,
                            name=f"{item.original_name} page {index}",
                            content_type="image/png",
                            file_path="",
                            data_url=data_url,
                        )
                    )
                continue

            attachments.append(
                ContextAttachment(
                    kind=item.kind,
                    name=item.original_name,
                    content_type=item.content_type,
                    file_path=item.file.path,
                )
            )
        return tuple(attachments)

    messages: list[ContextMessage] = []
    for node in build_branch_lineage(parent):
        # We need to interleave messages and tool invocations.
        # Since they are on the same node, we can assume they follow some order.
        # For now, let's put all messages first, then all tool invocations for that node,
        # UNLESS we can find a better way to order them.
        # Actually, in this project, Assistant message is usually the end of a node.
        # If there are tool invocations, they were triggered by the assistant message.
        # So it should be: User message -> Assistant message (with tool calls) -> Tool Result messages.
        
        node_messages = list(node.messages.all())
        
        for message in node_messages:
            message_attachments = build_context_attachments(message.attachments.all())
            messages.append(
                ContextMessage(
                    role=message.role,
                    content=message.content,
                    attachments=message_attachments,
                )
            )
        
        # Now append tool invocations for this node
        # In a multi-turn node, the tool invocations happened AFTER the user prompt.
        # If there's an assistant message, did it happen before or after tools?
        # In the previous implementation, the assistant message was a placeholder.
        # We want to move towards assistant having tool_calls.
        for inv in node.tool_invocations.all():
            # Tool call (assistant role)
            # Note: We don't have the original tool_call_id from provider persisted in ToolInvocation yet.
            # We might need to add it, but for now we can use a synthetic one or blank.
            synthetic_id = f"call_{inv.id}"
            
            # Find the assistant message that might have triggered this?
            # For now, let's just append them.
            from tree_ui.services.providers.base import ToolCall
            messages.append(
                ContextMessage(
                    role="assistant",
                    content="",
                    tool_calls=(
                        ToolCall(
                            call_id=synthetic_id,
                            name=inv.tool_name,
                            arguments=_safe_load_tool_invocation_payload(inv.invocation_payload),
                        ),
                    )
                )
            )
            # Tool result (tool role)
            messages.append(
                ContextMessage(
                    role="tool",
                    content=inv.result_payload,
                    tool_call_id=synthetic_id,
                    tool_name=inv.tool_name
                )
            )

    prompt_attachment_payload = build_context_attachments(prompt_attachments or [])
    messages.append(
        ContextMessage(
            role="user",
            content=prompt.strip(),
            attachments=prompt_attachment_payload,
        )
    )
    return messages
