from __future__ import annotations

from dataclasses import dataclass

from tree_ui.models import ConversationNode

SYSTEM_INSTRUCTION = (
    "You are LLM-Tree, an assistant working inside a branching conversation graph. "
    "Use only the messages from the current lineage path. Do not reference sibling "
    "branches or invent hidden context."
)


def build_system_instruction(custom_system_prompt: str = "") -> str:
    normalized_prompt = custom_system_prompt.strip()
    if not normalized_prompt:
        return SYSTEM_INSTRUCTION

    return (
        f"{SYSTEM_INSTRUCTION}\n\n"
        "Additional node-specific system prompt:\n"
        f"{normalized_prompt}"
    )


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
