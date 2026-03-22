from tree_ui.models import ConversationNode, Workspace
from tree_ui.services.model_catalog import resolve_model_name


def serialize_node(node: ConversationNode) -> dict:
    return {
        "id": node.id,
        "parent_id": node.parent_id,
        "edited_from_id": node.edited_from_id,
        "title": node.title,
        "summary": node.summary,
        "provider": node.provider,
        "model_name": resolve_model_name(provider=node.provider, model_name=node.model_name),
        "system_prompt": node.system_prompt,
        "temperature": node.temperature,
        "top_p": node.top_p,
        "max_output_tokens": node.max_output_tokens,
        "position": {"x": node.position_x, "y": node.position_y},
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
                "order_index": message.order_index,
            }
            for message in node.messages.all()
        ],
    }


def serialize_workspace(workspace: Workspace) -> dict:
    nodes = [
        serialize_node(node)
        for node in workspace.nodes.prefetch_related("messages").all()
    ]
    return {
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "description": workspace.description,
        },
        "nodes": nodes,
    }
