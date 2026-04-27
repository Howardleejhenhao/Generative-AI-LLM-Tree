from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tree_ui.models import ConversationMemory, ConversationNode, NodeMessage, Workspace
from tree_ui.services.context_builder import build_branch_lineage


@dataclass(frozen=True)
class RetrievedMemory:
    id: int
    scope: str
    memory_type: str
    source: str
    title: str
    content: str
    branch_anchor_id: int | None
    source_node_id: int | None
    source_message_id: int | None
    is_pinned: bool


def _normalize_string(value: Any, *, field_name: str, required: bool = False) -> str:
    if value is None:
        if required:
            raise ValueError(f"{field_name} is required.")
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    normalized = value.strip()
    if required and not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def _resolve_branch_anchor(
    *,
    workspace: Workspace,
    branch_anchor: ConversationNode | None,
    scope: str,
) -> ConversationNode | None:
    if scope == ConversationMemory.Scope.WORKSPACE:
        if branch_anchor is not None:
            raise ValueError("Workspace memories cannot have a branch anchor.")
        return None

    if branch_anchor is None:
        raise ValueError("Branch memories require a branch anchor node.")
    if branch_anchor.workspace_id != workspace.id:
        raise ValueError("Branch anchor must belong to the same workspace.")
    return branch_anchor


def _validate_source_links(
    *,
    workspace: Workspace,
    source_node: ConversationNode | None,
    source_message: NodeMessage | None,
) -> None:
    if source_node is not None and source_node.workspace_id != workspace.id:
        raise ValueError("Source node must belong to the same workspace.")

    if source_message is not None and source_message.node.workspace_id != workspace.id:
        raise ValueError("Source message must belong to the same workspace.")

    if source_node is not None and source_message is not None and source_message.node_id != source_node.id:
        raise ValueError("Source message must belong to the selected source node.")


def create_memory(
    *,
    workspace: Workspace,
    scope: str,
    memory_type: str,
    content: Any,
    title: Any = "",
    source: str = ConversationMemory.Source.MANUAL,
    branch_anchor: ConversationNode | None = None,
    source_node: ConversationNode | None = None,
    source_message: NodeMessage | None = None,
    is_pinned: bool = False,
) -> ConversationMemory:
    if scope not in ConversationMemory.Scope.values:
        raise ValueError("Unsupported memory scope.")
    if memory_type not in ConversationMemory.MemoryType.values:
        raise ValueError("Unsupported memory type.")
    if source not in ConversationMemory.Source.values:
        raise ValueError("Unsupported memory source.")

    normalized_title = _normalize_string(title, field_name="Title")
    normalized_content = _normalize_string(content, field_name="Content", required=True)
    resolved_branch_anchor = _resolve_branch_anchor(
        workspace=workspace,
        branch_anchor=branch_anchor,
        scope=scope,
    )
    _validate_source_links(
        workspace=workspace,
        source_node=source_node,
        source_message=source_message,
    )

    return ConversationMemory.objects.create(
        workspace=workspace,
        scope=scope,
        memory_type=memory_type,
        source=source,
        branch_anchor=resolved_branch_anchor,
        source_node=source_node,
        source_message=source_message,
        title=normalized_title,
        content=normalized_content,
        is_pinned=bool(is_pinned),
    )


def list_workspace_memories(*, workspace: Workspace):
    return ConversationMemory.objects.filter(
        workspace=workspace,
        scope=ConversationMemory.Scope.WORKSPACE,
    ).select_related("branch_anchor", "source_node", "source_message")


def get_workspace_memory(*, workspace: Workspace) -> ConversationMemory | None:
    workspace_memories = list_workspace_memories(workspace=workspace)
    canonical_memory = workspace_memories.filter(
        source=ConversationMemory.Source.EXTRACTED,
        memory_type=ConversationMemory.MemoryType.SUMMARY,
        title="Workspace memory",
    ).first()
    if canonical_memory is not None:
        return canonical_memory
    return workspace_memories.first()


def list_branch_memories(*, node: ConversationNode):
    lineage_ids = [item.id for item in build_branch_lineage(node)]
    return ConversationMemory.objects.filter(
        workspace=node.workspace,
        scope=ConversationMemory.Scope.BRANCH,
        branch_anchor_id__in=lineage_ids,
    ).select_related("branch_anchor", "source_node", "source_message")


def _serialize_retrieved_memory(item: ConversationMemory) -> RetrievedMemory:
    return RetrievedMemory(
        id=item.id,
        scope=item.scope,
        memory_type=item.memory_type,
        source=item.source,
        title=item.title,
        content=item.content,
        branch_anchor_id=item.branch_anchor_id,
        source_node_id=item.source_node_id,
        source_message_id=item.source_message_id,
        is_pinned=item.is_pinned,
    )


def retrieve_memories_for_generation(
    *,
    workspace: Workspace,
    parent: ConversationNode | None,
    limit: int = 8,
) -> list[RetrievedMemory]:
    canonical_workspace_memory = get_workspace_memory(workspace=workspace)
    workspace_memories = list(list_workspace_memories(workspace=workspace))
    ordered_workspace_memories: list[ConversationMemory] = []

    if canonical_workspace_memory is not None:
        ordered_workspace_memories.append(canonical_workspace_memory)

    ordered_workspace_memories.extend(
        memory
        for memory in workspace_memories
        if canonical_workspace_memory is None or memory.id != canonical_workspace_memory.id
    )

    ordered_branch_memories: list[ConversationMemory] = []
    if parent is not None:
        lineage = build_branch_lineage(parent)
        depth_by_node_id = {node.id: index for index, node in enumerate(lineage)}
        ordered_branch_memories = sorted(
            list(list_branch_memories(node=parent)),
            key=lambda memory: (
                memory.is_pinned,
                depth_by_node_id.get(memory.branch_anchor_id, -1),
                memory.updated_at,
                memory.created_at,
            ),
            reverse=True,
        )

    combined = ordered_workspace_memories + ordered_branch_memories
    return [_serialize_retrieved_memory(item) for item in combined[:limit]]


def format_memories_for_prompt(memories: list[RetrievedMemory]) -> str:
    if not memories:
        return ""

    lines = ["Retrieved long-term memory:",]
    for memory in memories:
        label = f"[{memory.scope}/{memory.memory_type}]"
        title = f" {memory.title}:" if memory.title else ""
        lines.append(f"- {label}{title} {memory.content}".rstrip())
    return "\n".join(lines)
