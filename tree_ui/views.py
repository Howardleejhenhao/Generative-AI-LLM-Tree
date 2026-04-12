import json

from django.http import HttpResponseBadRequest, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from tree_ui.models import ConversationMemory, ConversationNode, NodeMessage, Workspace
from tree_ui.services.model_catalog import resolve_model_name
from tree_ui.services.graph_payload import serialize_node, serialize_workspace
from tree_ui.services.memory_drafting import (
    generate_memory_draft_for_node,
    refresh_workspace_preference_memory,
)
from tree_ui.services.memory_service import (
    create_memory,
    format_memories_for_prompt,
    list_branch_memories,
    list_workspace_memories,
    retrieve_memories_for_generation,
)
from tree_ui.services.node_editing import create_edited_variant
from tree_ui.services.node_creation import (
    append_messages_to_node_with_reply,
    create_continuation_child,
    create_node,
    resolve_message_append_inputs,
    resolve_node_creation_inputs,
    stream_assistant_reply,
)
from tree_ui.services.node_positioning import resolve_node_position_inputs
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


def _serialize_memory(memory: ConversationMemory) -> dict:
    return {
        "id": memory.id,
        "scope": memory.scope,
        "memory_type": memory.memory_type,
        "source": memory.source,
        "title": memory.title,
        "content": memory.content,
        "is_pinned": memory.is_pinned,
        "branch_anchor_id": memory.branch_anchor_id,
        "branch_anchor_title": memory.branch_anchor.title if memory.branch_anchor_id else "",
        "source_node_id": memory.source_node_id,
        "source_message_id": memory.source_message_id,
    }


def _build_memory_payload(node: ConversationNode) -> dict:
    workspace_memories = list(list_workspace_memories(workspace=node.workspace))
    branch_memories = list(list_branch_memories(node=node))
    retrieved_memories = retrieve_memories_for_generation(
        workspace=node.workspace,
        parent=node,
    )
    return {
        "workspace_memories": [_serialize_memory(item) for item in workspace_memories],
        "branch_memories": [_serialize_memory(item) for item in branch_memories],
        "retrieved_memories": [
            {
                "id": item.id,
                "scope": item.scope,
                "memory_type": item.memory_type,
                "source": item.source,
                "title": item.title,
                "content": item.content,
                "is_pinned": item.is_pinned,
                "branch_anchor_id": item.branch_anchor_id,
            }
            for item in retrieved_memories
        ],
        "retrieved_memory_text": format_memories_for_prompt(retrieved_memories),
    }


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
    edited_variants = node.edited_variants.order_by("created_at")

    return render(
        request,
        "tree_ui/node_chat.html",
        {
            "workspace": workspace,
            "workspace_list": _serialize_workspace_list(workspace),
            "node_payload": serialize_node(node),
            "node_memory_url": reverse("workspace_node_memory", args=[workspace.slug, node.id]),
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
                    "model_name": resolve_model_name(
                        provider=child.provider,
                        model_name=child.model_name,
                    ),
                    "url": reverse("workspace_node_chat", args=[workspace.slug, child.id]),
                }
                for child in child_nodes
            ],
            "edited_source": (
                {
                    "id": node.edited_from.id,
                    "title": node.edited_from.title,
                    "url": reverse("workspace_node_chat", args=[workspace.slug, node.edited_from.id]),
                }
                if node.edited_from_id
                else None
            ),
            "edited_variants": [
                {
                    "id": variant.id,
                    "title": variant.title,
                    "summary": variant.summary,
                    "provider": variant.provider,
                    "model_name": resolve_model_name(
                        provider=variant.provider,
                        model_name=variant.model_name,
                    ),
                    "url": reverse("workspace_node_chat", args=[workspace.slug, variant.id]),
                }
                for variant in edited_variants
            ],
            "can_append_in_place": not child_nodes.exists(),
        },
    )


def workspace_node_memory(request, slug: str, node_id: int):
    workspace = get_object_or_404(Workspace, slug=slug)
    node = get_object_or_404(
        ConversationNode.objects.select_related("workspace", "parent", "edited_from").prefetch_related(
            "messages",
            "children",
        ),
        pk=node_id,
        workspace=workspace,
    )

    return render(
        request,
        "tree_ui/node_memory.html",
        {
            "workspace": workspace,
            "workspace_list": _serialize_workspace_list(workspace),
            "node_payload": serialize_node(node),
            "memory_payload": _build_memory_payload(node),
            "memory_type_choices": [
                {"value": value, "label": label}
                for value, label in ConversationMemory.MemoryType.choices
            ],
            "memory_scope_choices": [
                {"value": ConversationMemory.Scope.BRANCH, "label": "Branch"}
            ],
            "node_chat_url": reverse("workspace_node_chat", args=[workspace.slug, node.id]),
            "workspace_memory_refresh_url": reverse(
                "refresh_workspace_memory",
                args=[workspace.slug, node.id],
            ),
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


def _parse_json_payload(request) -> dict:
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON payload.") from exc


def _require_delete_confirmation(payload: dict) -> None:
    if payload.get("confirm") is not True:
        raise ValueError("Deletion requires explicit confirmation.")


def _collect_subtree_node_ids(*, workspace: Workspace, root_node_id: int) -> list[int]:
    rows = workspace.nodes.values_list("id", "parent_id")
    child_map: dict[int | None, list[int]] = {}
    for node_id, parent_id in rows:
        child_map.setdefault(parent_id, []).append(node_id)

    subtree_ids: list[int] = []
    stack = [root_node_id]
    while stack:
        current_id = stack.pop()
        subtree_ids.append(current_id)
        stack.extend(child_map.get(current_id, []))

    return subtree_ids


@require_POST
def create_workspace_view(request):
    try:
        payload = _parse_json_payload(request)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

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
def delete_workspace_view(request, slug: str):
    workspace = get_object_or_404(Workspace, slug=slug)

    try:
        payload = _parse_json_payload(request)
        _require_delete_confirmation(payload)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    next_workspace = list_workspaces().exclude(pk=workspace.pk).first()
    deleted_workspace_name = workspace.name
    deleted_workspace_slug = workspace.slug
    workspace.delete()

    return JsonResponse(
        {
            "deleted_workspace": {
                "name": deleted_workspace_name,
                "slug": deleted_workspace_slug,
            },
            "redirect_url": (
                reverse("workspace_graph", args=[next_workspace.slug])
                if next_workspace
                else reverse("workspace_home")
            ),
        }
    )


@require_POST
def create_workspace_node(request, slug: str):
    try:
        workspace, parent, payload = _parse_node_request(request, slug)
        resolved_inputs = resolve_node_creation_inputs(
            workspace=workspace,
            parent=parent,
            title=payload.get("title", ""),
            provider=payload.get("provider", ConversationNode.Provider.OPENAI),
            model_name=payload.get("model_name", ""),
            system_prompt=payload.get("system_prompt", ""),
            temperature=payload.get("temperature"),
            top_p=payload.get("top_p"),
            max_output_tokens=payload.get("max_output_tokens"),
        )
        node = create_node(
            workspace=workspace,
            parent=parent,
            title=resolved_inputs["title"],
            provider=resolved_inputs["provider"],
            model_name=resolved_inputs["model_name"],
            system_prompt=resolved_inputs["system_prompt"],
            temperature=resolved_inputs["temperature"],
            top_p=resolved_inputs["top_p"],
            max_output_tokens=resolved_inputs["max_output_tokens"],
        )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    return JsonResponse(
        {
            "node": serialize_node(node),
            "node_chat_url": reverse("workspace_node_chat", args=[workspace.slug, node.id]),
        },
        status=201,
    )


@require_POST
def create_workspace_memory_view(request, slug: str):
    workspace = get_object_or_404(Workspace, slug=slug)

    try:
        payload = _parse_json_payload(request)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    context_node = None
    context_node_id = payload.get("context_node_id")
    if context_node_id not in (None, ""):
        context_node = get_object_or_404(
            ConversationNode.objects.select_related("workspace"),
            pk=context_node_id,
            workspace=workspace,
        )

    source_node = None
    source_node_id = payload.get("source_node_id")
    if source_node_id not in (None, ""):
        source_node = get_object_or_404(
            ConversationNode.objects.select_related("workspace"),
            pk=source_node_id,
            workspace=workspace,
        )

    source_message = None
    source_message_id = payload.get("source_message_id")
    if source_message_id not in (None, ""):
        source_message = get_object_or_404(
            NodeMessage.objects.select_related("node", "node__workspace"),
            pk=source_message_id,
            node__workspace=workspace,
        )
        if source_node is None:
            source_node = source_message.node

    branch_anchor = None
    branch_anchor_id = payload.get("branch_anchor_id")
    if branch_anchor_id not in (None, ""):
        branch_anchor = get_object_or_404(
            ConversationNode.objects.select_related("workspace"),
            pk=branch_anchor_id,
            workspace=workspace,
        )
    elif payload.get("scope") == ConversationMemory.Scope.BRANCH:
        branch_anchor = context_node or source_node

    requested_scope = payload.get("scope", ConversationMemory.Scope.WORKSPACE)
    if requested_scope == ConversationMemory.Scope.WORKSPACE:
        return HttpResponseBadRequest("Workspace memory is managed automatically by the model.")

    try:
        memory = create_memory(
            workspace=workspace,
            scope=requested_scope,
            memory_type=payload.get("memory_type", ConversationMemory.MemoryType.FACT),
            title=payload.get("title", ""),
            content=payload.get("content") if payload.get("content") not in (None, "") else (
                source_message.content if source_message is not None else ""
            ),
            source=(
                ConversationMemory.Source.PINNED
                if source_message is not None
                else payload.get("source", ConversationMemory.Source.MANUAL)
            ),
            branch_anchor=branch_anchor,
            source_node=source_node,
            source_message=source_message,
            is_pinned=payload.get("is_pinned", False) or source_message is not None,
        )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    response_node = context_node or source_node or branch_anchor
    response_payload = _build_memory_payload(response_node) if response_node is not None else {
        "workspace_memories": [_serialize_memory(item) for item in list_workspace_memories(workspace=workspace)],
        "branch_memories": [],
        "retrieved_memories": [],
        "retrieved_memory_text": "",
    }

    return JsonResponse(
        {
            "memory": _serialize_memory(memory),
            "memory_payload": response_payload,
        },
        status=201,
    )


@require_POST
def generate_node_memory_draft_view(request, slug: str, node_id: int):
    workspace = get_object_or_404(Workspace, slug=slug)
    node = get_object_or_404(
        ConversationNode.objects.prefetch_related("messages"),
        pk=node_id,
        workspace=workspace,
    )

    draft = generate_memory_draft_for_node(node)
    return JsonResponse({"draft": draft})


@require_POST
def refresh_workspace_memory_view(request, slug: str, node_id: int):
    workspace = get_object_or_404(Workspace, slug=slug)
    node = get_object_or_404(
        ConversationNode.objects.prefetch_related("messages"),
        pk=node_id,
        workspace=workspace,
    )

    memory = refresh_workspace_preference_memory(node)
    return JsonResponse(
        {
            "memory": _serialize_memory(memory),
            "memory_payload": _build_memory_payload(node),
        }
    )


@require_POST
def delete_workspace_node(request, slug: str, node_id: int):
    workspace = get_object_or_404(Workspace, slug=slug)
    node = get_object_or_404(ConversationNode, pk=node_id, workspace=workspace)

    try:
        payload = _parse_json_payload(request)
        _require_delete_confirmation(payload)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    deleted_node_title = node.title
    deleted_node_ids = _collect_subtree_node_ids(workspace=workspace, root_node_id=node.id)
    node.delete()

    return JsonResponse(
        {
            "deleted_node": {
                "id": node_id,
                "title": deleted_node_title,
            },
            "deleted_node_ids": deleted_node_ids,
            "deleted_count": len(deleted_node_ids),
        }
    )


@require_POST
def create_edited_node_variant(request, slug: str, node_id: int):
    workspace = get_object_or_404(Workspace, slug=slug)
    original_node = get_object_or_404(
        ConversationNode.objects.prefetch_related("messages"),
        pk=node_id,
        workspace=workspace,
    )
    try:
        payload = _parse_json_payload(request)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    try:
        node = create_edited_variant(
            original_node=original_node,
            title=payload.get("title", ""),
            messages=payload.get("messages", []),
        )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    return JsonResponse(
        {
            "node": serialize_node(node),
            "node_chat_url": reverse("workspace_node_chat", args=[workspace.slug, node.id]),
        },
        status=201,
    )


@require_POST
def update_node_position(request, slug: str, node_id: int):
    workspace = get_object_or_404(Workspace, slug=slug)
    node = get_object_or_404(ConversationNode, pk=node_id, workspace=workspace)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    try:
        position_x, position_y = resolve_node_position_inputs(
            position_x=payload.get("position_x"),
            position_y=payload.get("position_y"),
        )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    node.position_x = position_x
    node.position_y = position_y
    node.save(update_fields=["position_x", "position_y", "updated_at"])

    return JsonResponse({"node": serialize_node(node)})


@require_POST
def stream_workspace_node(request, slug: str):
    return HttpResponseBadRequest("Graph-level prompt creation is disabled. Open a node chat view to talk.")


@require_POST
def stream_node_message(request, slug: str, node_id: int):
    workspace = get_object_or_404(Workspace, slug=slug)
    node = get_object_or_404(
        ConversationNode.objects.prefetch_related("messages"),
        pk=node_id,
        workspace=workspace,
    )

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON payload.")

    try:
        resolved_inputs = resolve_message_append_inputs(prompt=payload.get("prompt", ""))
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    target_node = node
    created_new_branch = False
    if node.children.exists():
        target_node = create_continuation_child(
            source_node=node,
            title=resolved_inputs["summary"],
        )
        created_new_branch = True

    def event_stream():
        try:
            assistant_chunks: list[str] = []
            yield _sse_event(
                "preview",
                {
                    "node_id": target_node.id,
                    "title": target_node.title,
                    "provider": target_node.provider,
                    "model_name": resolve_model_name(
                        provider=target_node.provider,
                        model_name=target_node.model_name,
                    ),
                    "summary": resolved_inputs["summary"],
                    "prompt": resolved_inputs["prompt"],
                    "created_new_branch": created_new_branch,
                    "source_node_id": node.id,
                    "node_chat_url": reverse("workspace_node_chat", args=[workspace.slug, target_node.id]),
                },
            )
            for chunk in stream_assistant_reply(
                parent=target_node,
                provider=target_node.provider,
                model_name=target_node.model_name,
                prompt=resolved_inputs["prompt"],
                system_prompt=target_node.system_prompt,
                temperature=target_node.temperature,
                top_p=target_node.top_p,
                max_output_tokens=target_node.max_output_tokens,
            ):
                assistant_chunks.append(chunk)
                yield _sse_event("delta", {"delta": chunk})
            updated_node = append_messages_to_node_with_reply(
                node=target_node,
                prompt=resolved_inputs["prompt"],
                assistant_reply="".join(assistant_chunks),
            )
            yield _sse_event(
                "node",
                {
                    "node": serialize_node(updated_node),
                    "created_new_branch": created_new_branch,
                    "source_node_id": node.id,
                    "node_chat_url": reverse("workspace_node_chat", args=[workspace.slug, updated_node.id]),
                },
            )
            yield _sse_event("done", {})
        except Exception as exc:
            yield _sse_event("error", {"message": str(exc)})

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
