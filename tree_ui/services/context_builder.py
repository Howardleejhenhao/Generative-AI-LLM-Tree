from __future__ import annotations

from dataclasses import dataclass, field

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
) -> list[ContextMessage]:
    def build_context_attachments(items) -> tuple[ContextAttachment, ...]:
        attachments: list[ContextAttachment] = []
        for item in items:
            if item.kind == NodeAttachment.Kind.PDF:
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
        for message in node.messages.order_by("order_index", "created_at"):
            message_attachments = build_context_attachments(message.attachments.all())
            messages.append(
                ContextMessage(
                    role=message.role,
                    content=message.content,
                    attachments=message_attachments,
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
