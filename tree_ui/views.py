import json

from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from tree_ui.models import ConversationNode, Workspace
from tree_ui.services.graph_payload import serialize_node, serialize_workspace
from tree_ui.services.node_creation import create_node
from tree_ui.services.workspace_service import get_or_create_default_workspace


def workspace_graph(request):
    workspace = get_or_create_default_workspace()
    graph_payload = serialize_workspace(workspace)
    return render(
        request,
        "tree_ui/index.html",
        {
            "graph_payload": graph_payload,
        },
    )


@require_POST
def create_workspace_node(request, slug: str):
    workspace = get_object_or_404(Workspace, slug=slug)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    parent = None
    parent_id = payload.get("parent_id")
    if parent_id not in (None, ""):
        parent = get_object_or_404(
            ConversationNode.objects.select_related("workspace"),
            pk=parent_id,
            workspace=workspace,
        )

    try:
        node = create_node(
            workspace=workspace,
            parent=parent,
            title=payload.get("title", ""),
            prompt=payload.get("prompt", ""),
            provider=payload.get("provider", ConversationNode.Provider.OPENAI),
            model_name=payload.get("model_name", ""),
        )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    return JsonResponse({"node": serialize_node(node)}, status=201)
