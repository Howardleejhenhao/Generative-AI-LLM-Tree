import json

from django.http import HttpResponseBadRequest, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from tree_ui.models import ConversationNode, Workspace
from tree_ui.services.graph_payload import serialize_node, serialize_workspace
from tree_ui.services.node_editing import create_edited_variant
from tree_ui.services.node_creation import (
    create_node,
    create_node_with_reply,
    generate_assistant_reply,
    iter_text_chunks,
    resolve_node_creation_inputs,
)
from tree_ui.services.workspace_service import (
    create_workspace,
    get_or_create_default_workspace,
    list_workspaces,
)


def _serialize_workspace_list(current_workspace: Workspace) -> list[dict]:
    return [
        {
            "name": item.name,
            "slug": item.slug,
            "description": item.description,
            "is_current": item.pk == current_workspace.pk,
        }
        for item in list_workspaces()
    ]


def _build_lineage(node: ConversationNode) -> list[ConversationNode]:
    lineage = []
    current = node

    while current is not None:
        lineage.append(current)
        current = current.parent

    return list(reversed(lineage))


def workspace_home(request):
    workspace = list_workspaces().first() or get_or_create_default_workspace()
    return HttpResponseRedirect(reverse("workspace_graph", args=[workspace.slug]))


def workspace_graph(request, slug: str):
    workspace = get_object_or_404(Workspace, slug=slug)
    graph_payload = serialize_workspace(workspace)
    return render(
        request,
        "tree_ui/index.html",
        {
            "graph_payload": graph_payload,
            "workspace_list": _serialize_workspace_list(workspace),
        },
    )


def workspace_node_chat(request, slug: str, node_id: int):
    workspace = get_object_or_404(Workspace, slug=slug)
    node = get_object_or_404(
        ConversationNode.objects.select_related("workspace", "parent", "edited_from").prefetch_related(
            "messages",
            "children",
        ),
        pk=node_id,
        workspace=workspace,
    )
    lineage = _build_lineage(node)
    child_nodes = node.children.order_by("created_at")

    return render(
        request,
        "tree_ui/node_chat.html",
        {
            "workspace": workspace,
            "workspace_list": _serialize_workspace_list(workspace),
            "node_payload": serialize_node(node),
            "lineage_items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "url": reverse("workspace_node_chat", args=[workspace.slug, item.id]),
                    "is_current": item.id == node.id,
                }
                for item in lineage
            ],
            "child_nodes": [
                {
                    "id": child.id,
                    "title": child.title,
                    "summary": child.summary,
                    "provider": child.provider,
                    "model_name": child.model_name,
                    "url": reverse("workspace_node_chat", args=[workspace.slug, child.id]),
                }
                for child in child_nodes
            ],
        },
    )


def _parse_node_request(request, slug: str) -> tuple[Workspace, ConversationNode | None, dict]:
    workspace = get_object_or_404(Workspace, slug=slug)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON payload.") from exc

    parent = None
    parent_id = payload.get("parent_id")
    if parent_id not in (None, ""):
        parent = get_object_or_404(
            ConversationNode.objects.select_related("workspace"),
            pk=parent_id,
            workspace=workspace,
        )
    return workspace, parent, payload


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@require_POST
def create_workspace_view(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    try:
        workspace = create_workspace(
            name=payload.get("name", ""),
            description=payload.get("description", ""),
        )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    return JsonResponse(
        {
            "workspace": {
                "id": workspace.id,
                "name": workspace.name,
                "slug": workspace.slug,
                "description": workspace.description,
            },
            "redirect_url": reverse("workspace_graph", args=[workspace.slug]),
        },
        status=201,
    )


@require_POST
def create_workspace_node(request, slug: str):
    try:
        workspace, parent, payload = _parse_node_request(request, slug)
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


@require_POST
def create_edited_node_variant(request, slug: str, node_id: int):
    workspace = get_object_or_404(Workspace, slug=slug)
    original_node = get_object_or_404(
        ConversationNode.objects.prefetch_related("messages"),
        pk=node_id,
        workspace=workspace,
    )
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    try:
        node = create_edited_variant(
            original_node=original_node,
            title=payload.get("title", ""),
            messages=payload.get("messages", []),
        )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    return JsonResponse({"node": serialize_node(node)}, status=201)


@require_POST
def stream_workspace_node(request, slug: str):
    try:
        workspace, parent, payload = _parse_node_request(request, slug)
        resolved_inputs = resolve_node_creation_inputs(
            workspace=workspace,
            parent=parent,
            title=payload.get("title", ""),
            prompt=payload.get("prompt", ""),
            provider=payload.get("provider", ConversationNode.Provider.OPENAI),
            model_name=payload.get("model_name", ""),
        )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    def event_stream():
        try:
            assistant_reply = generate_assistant_reply(
                parent=parent,
                provider=resolved_inputs["provider"],
                model_name=resolved_inputs["model_name"],
                prompt=resolved_inputs["prompt"],
            )
            yield _sse_event(
                "preview",
                {
                    "title": resolved_inputs["title"],
                    "provider": resolved_inputs["provider"],
                    "model_name": resolved_inputs["model_name"],
                    "summary": resolved_inputs["summary"],
                    "parent_id": parent.id if parent else None,
                    "prompt": resolved_inputs["prompt"],
                },
            )
            for chunk in iter_text_chunks(assistant_reply):
                yield _sse_event("delta", {"delta": chunk})
            node = create_node_with_reply(
                workspace=workspace,
                parent=parent,
                resolved_inputs=resolved_inputs,
                assistant_reply=assistant_reply,
            )
            yield _sse_event("node", {"node": serialize_node(node)})
            yield _sse_event("done", {})
        except Exception as exc:
            yield _sse_event("error", {"message": str(exc)})

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
