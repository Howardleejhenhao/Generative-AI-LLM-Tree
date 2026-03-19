import json

from django.http import HttpResponseBadRequest, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from tree_ui.models import ConversationNode, Workspace
from tree_ui.services.graph_payload import serialize_node, serialize_workspace
from tree_ui.services.node_creation import (
    create_node,
    create_node_with_reply,
    generate_assistant_reply,
    iter_text_chunks,
    resolve_node_creation_inputs,
)
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
