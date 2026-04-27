import json
from django.urls import reverse
from tree_ui.models import ConversationNode, Workspace
from tree_ui.services.model_catalog import resolve_model_name
from tree_ui.services.memory_service import (
    list_workspace_memories,
    list_branch_memories,
    retrieve_memories_for_generation,
)


def _build_memory_payload(mem, *, workspace: Workspace, retrieved_ids: set[int]) -> dict:
    is_retrieved = mem.id in retrieved_ids
    branch_anchor_title = mem.branch_anchor.title if mem.branch_anchor_id else ""
    branch_anchor_url = (
        reverse("workspace_node_chat", args=[workspace.slug, mem.branch_anchor_id])
        if mem.branch_anchor_id
        else ""
    )

    retrieval_reason = ""
    if is_retrieved:
        if mem.scope == "workspace":
            retrieval_reason = "Retrieved as shared workspace memory for all branches in this workspace."
        elif branch_anchor_title:
            retrieval_reason = (
                f"Retrieved because this branch memory is anchored to {branch_anchor_title} in the current lineage."
            )
        else:
            retrieval_reason = "Retrieved from the current branch lineage."

    return {
        "id": mem.id,
        "title": mem.title or (f"Memory {mem.id}"),
        "content": mem.content,
        "scope": mem.scope,
        "memory_type": mem.memory_type,
        "is_pinned": mem.is_pinned,
        "is_retrieved": is_retrieved,
        "retrieval_reason": retrieval_reason,
        "updated_at": mem.updated_at.isoformat() if mem.updated_at else None,
        "branch_anchor_id": mem.branch_anchor_id,
        "branch_anchor_title": branch_anchor_title,
        "branch_anchor_url": branch_anchor_url,
        "source_node_id": mem.source_node_id,
        "source_node_title": mem.source_node.title if mem.source_node_id else "",
        "source_node_url": (
            reverse("workspace_node_chat", args=[workspace.slug, mem.source_node_id])
            if mem.source_node_id
            else ""
        ),
    }


def serialize_node(node: ConversationNode) -> dict:
    workspace = node.workspace
    
    # Available memories: Workspace scope + Branch scope in lineage
    ws_memories = list_workspace_memories(workspace=workspace)
    br_memories = list_branch_memories(node=node)
    
    # Retrieved memories (for current context)
    retrieved = retrieve_memories_for_generation(workspace=workspace, parent=node)
    retrieved_ids = {m.id for m in retrieved}

    all_memories = []
    for mem in list(ws_memories) + list(br_memories):
        all_memories.append(_build_memory_payload(mem, workspace=workspace, retrieved_ids=retrieved_ids))

    status_badges = []
    
    # Tool usage badge
    tool_count = node.tool_invocations.count()
    if tool_count > 0:
        status_badges.append({"label": f"Tools {tool_count}", "type": "tools"})
    
    # Memory badge should reflect node-specific branch context, not generic workspace memory.
    branch_memory_count = len(br_memories)
    if branch_memory_count > 0:
        status_badges.append({"label": f"Memory {branch_memory_count}", "type": "memory"})
        
    # Routing mode badge (only surface if it's NOT manual, or if we want to show it explicitly)
    if node.routing_mode != ConversationNode.RoutingMode.MANUAL:
        # Use a short label like "Auto"
        status_badges.append({"label": "Auto", "type": "auto"})
    
    # Edited variant badge
    if node.edited_from_id:
        status_badges.append({"label": "Edited", "type": "edited"})

    return {
        "id": node.id,
        "parent_id": node.parent_id,
        "edited_from_id": node.edited_from_id,
        "title": node.title,
        "summary": node.summary,
        "provider": node.provider,
        "model_name": resolve_model_name(provider=node.provider, model_name=node.model_name),
        "routing_mode": node.routing_mode,
        "routing_decision": node.routing_decision,
        "system_prompt": node.system_prompt,
        "temperature": node.temperature,
        "top_p": node.top_p,
        "max_output_tokens": node.max_output_tokens,
        "position": {"x": node.position_x, "y": node.position_y},
        "status_badges": status_badges,
        "memories": all_memories,
        "tool_invocations": [
            {
                "id": inv.id,
                "name": inv.tool_name,
                "tool_type": inv.tool_type,
                "source_id": inv.source_id,
                "args": json.loads(inv.invocation_payload) if inv.invocation_payload else {},
                "result": json.loads(inv.result_payload) if inv.result_payload else {},
                "success": inv.success,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
            }
            for inv in node.tool_invocations.all()
        ],
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "order_index": message.order_index,
                "attachments": [
                    {
                        "id": attachment.id,
                        "kind": attachment.kind,
                        "name": attachment.original_name,
                        "content_type": attachment.content_type,
                        "size_bytes": attachment.size_bytes,
                        "url": attachment.file.url,
                    }
                    for attachment in message.attachments.all()
                ],
            }
            for message in node.messages.all()
        ],
        "attachments": [
            {
                "id": attachment.id,
                "kind": attachment.kind,
                "name": attachment.original_name,
                "content_type": attachment.content_type,
                "size_bytes": attachment.size_bytes,
                "url": attachment.file.url,
            }
            for attachment in node.attachments.all()
        ],
    }


def serialize_timeline_event(event_type: str, timestamp, title: str, description: str, node_id=None) -> dict:
    return {
        "event_type": event_type,
        "timestamp": timestamp.isoformat() if timestamp else None,
        "title": title,
        "description": description,
        "node_id": node_id,
    }


def get_workspace_timeline(workspace: Workspace, limit: int = 20) -> list:
    from tree_ui.models import ConversationNode, ToolInvocation, ConversationMemory
    
    events = []
    
    # Recent nodes
    nodes = workspace.nodes.order_by("-created_at")[:limit]
    for node in nodes:
        event_type = "node_created"
        description = f"Model: {node.model_name}"
        if node.edited_from_id:
            event_type = "node_edited"
            description = f"Variant of {node.edited_from.title}"
            
        events.append(serialize_timeline_event(
            event_type=event_type,
            timestamp=node.created_at,
            title=node.title,
            description=description,
            node_id=node.id
        ))
        
    # Recent tool invocations
    tools = ToolInvocation.objects.filter(node__workspace=workspace).select_related("node").order_by("-created_at")[:limit]
    for tool in tools:
        events.append(serialize_timeline_event(
            event_type="tool_invocation",
            timestamp=tool.created_at,
            title=f"Tool: {tool.tool_name}",
            description=f"Used in {tool.node.title} ({'Success' if tool.success else 'Failed'})",
            node_id=tool.node_id
        ))
        
    # Recent memory events
    memories = workspace.memories.order_by("-updated_at")[:limit]
    for memory in memories:
        events.append(serialize_timeline_event(
            event_type="memory_updated",
            timestamp=memory.updated_at,
            title=f"Memory: {memory.memory_type}",
            description=memory.title or memory.content[:50],
            node_id=memory.source_node_id
        ))
        
    # Sort all by timestamp descending
    events.sort(key=lambda x: x["timestamp"], reverse=True)
    return events[:limit]


def serialize_workspace(workspace: Workspace) -> dict:
    nodes = [
        serialize_node(node)
        for node in workspace.nodes.prefetch_related("messages__attachments", "attachments", "tool_invocations").all()
    ]
    return {
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "description": workspace.description,
        },
        "nodes": nodes,
        "timeline": get_workspace_timeline(workspace),
    }
