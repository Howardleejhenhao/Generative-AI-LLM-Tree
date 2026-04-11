from __future__ import annotations

from dataclasses import dataclass

from tree_ui.models import ConversationNode

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
class ContextMessage:
    role: str
    content: str


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
) -> list[ContextMessage]:
    messages: list[ContextMessage] = []
    for node in build_branch_lineage(parent):
        for message in node.messages.order_by("order_index", "created_at"):
            messages.append(ContextMessage(role=message.role, content=message.content))
    messages.append(ContextMessage(role="user", content=prompt.strip()))
    return messages
