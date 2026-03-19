from django.shortcuts import render

from tree_ui.models import ConversationNode, Workspace
from tree_ui.services.demo_graph import build_demo_workspace_payload


def _serialize_workspace(workspace: Workspace) -> dict:
    nodes = []
    for node in workspace.nodes.prefetch_related("messages").all():
        nodes.append(
            {
                "id": node.id,
                "parent_id": node.parent_id,
                "edited_from_id": node.edited_from_id,
                "title": node.title,
                "summary": node.summary,
                "provider": node.provider,
                "model_name": node.model_name,
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
        )

    return {
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "description": workspace.description,
        },
        "nodes": nodes,
    }


def workspace_graph(request):
    workspace = Workspace.objects.prefetch_related("nodes__messages").first()
    graph_payload = (
        _serialize_workspace(workspace)
        if workspace is not None
        else build_demo_workspace_payload()
    )
    return render(
        request,
        "tree_ui/index.html",
        {
            "graph_payload": graph_payload,
        },
    )
