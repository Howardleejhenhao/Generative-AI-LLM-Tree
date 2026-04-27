import json
import sys
from pathlib import Path

from django.http import HttpResponseBadRequest, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from tree_ui.models import ConversationMemory, ConversationNode, Workspace, MCPSource
from tree_ui.forms import MCPSourceForm
from tree_ui.services.attachments import create_node_attachments
from tree_ui.services.model_catalog import resolve_model_name
from tree_ui.services.mcp.dispatcher import default_dispatcher
from tree_ui.services.mcp.source_status import (
    clear_diagnostics_result,
    diagnose_source,
    save_diagnostics_result,
)
from tree_ui.services.router import route_model
from tree_ui.services.graph_payload import serialize_node, serialize_workspace
from tree_ui.services.memory_drafting import ensure_workspace_memory
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


def _serialize_workspace_memory(memory: ConversationMemory | None, *, workspace: Workspace) -> dict | None:
    if memory is None:
        return None

    return {
        "id": memory.id,
        "title": memory.title,
        "content": memory.content,
        "updated_at": memory.updated_at,
        "source_node_id": memory.source_node_id,
        "source_node_title": memory.source_node.title if memory.source_node_id else "",
        "source_node_url": (
            reverse("workspace_node_chat", args=[workspace.slug, memory.source_node_id])
            if memory.source_node_id
            else ""
        ),
    }


def workspace_home(request):
    workspace = list_workspaces().first() or get_or_create_default_workspace()
    return HttpResponseRedirect(reverse("workspace_graph", args=[workspace.slug]))


def workspace_graph(request, slug: str):
    workspace = get_object_or_404(Workspace, slug=slug)
    graph_payload = serialize_workspace(workspace)
    workspace_memory = ensure_workspace_memory(workspace)
    return render(
        request,
        "tree_ui/index.html",
        {
            "graph_payload": graph_payload,
            "workspace_list": _serialize_workspace_list(workspace),
            "workspace_memory": _serialize_workspace_memory(workspace_memory, workspace=workspace),
        },
    )


def workspace_node_chat(request, slug: str, node_id: int):
    workspace = get_object_or_404(Workspace, slug=slug)
    node = get_object_or_404(
        ConversationNode.objects.select_related("workspace", "parent", "edited_from").prefetch_related(
            "messages__attachments",
            "children",
            "attachments",
            "tool_invocations",
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
            "workspace_memory_url": f"{reverse('workspace_graph', args=[workspace.slug])}#workspace-memory-panel",
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
    get_object_or_404(ConversationNode, pk=node_id, workspace=workspace)
    return HttpResponseRedirect(f"{reverse('workspace_graph', args=[workspace.slug])}#workspace-memory-panel")

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
            routing_mode=payload.get("routing_mode", ConversationNode.RoutingMode.MANUAL),
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
            routing_mode=resolved_inputs["routing_mode"],
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
    return HttpResponseBadRequest("Manual long-term memory editing has been removed. Workspace memory is automatic and read only.")


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
def update_node_title(request, slug: str, node_id: int):
    workspace = get_object_or_404(Workspace, slug=slug)
    node = get_object_or_404(ConversationNode, pk=node_id, workspace=workspace)

    try:
        payload = _parse_json_payload(request)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    raw_title = payload.get("title", "")
    if not isinstance(raw_title, str):
        return HttpResponseBadRequest("Title must be a string.")

    normalized_title = raw_title.strip() or "Untitled conversation"
    if len(normalized_title) > 160:
        return HttpResponseBadRequest("Title must be 160 characters or fewer.")

    node.title = normalized_title
    node.save(update_fields=["title", "updated_at"])
    return JsonResponse({"node": serialize_node(node)})


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
        ConversationNode.objects.prefetch_related("messages__attachments", "attachments", "tool_invocations"),
        pk=node_id,
        workspace=workspace,
    )

    if request.content_type and request.content_type.startswith("multipart/form-data"):
        payload = {"prompt": request.POST.get("prompt", "")}
        uploaded_images = request.FILES.getlist("images")
    else:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Invalid JSON payload.")
        uploaded_images = []

    try:
        resolved_inputs = resolve_message_append_inputs(
            prompt=payload.get("prompt", ""),
            has_attachments=bool(uploaded_images),
        )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    target_node = node
    created_new_branch = False
    if node.children.exists():
        target_node = create_continuation_child(
            source_node=node,
            title=resolved_inputs["summary"],
            prompt=resolved_inputs["prompt"],
            has_attachments=bool(uploaded_images),
        )
        created_new_branch = True
    else:
        # If the node already exists but its routing mode is not manual,
        # and it has no messages yet (first turn), we should re-route now that we have signals.
        if node.routing_mode != ConversationNode.RoutingMode.MANUAL and node.messages.count() == 0:
            routing_result = route_model(
                routing_mode=node.routing_mode,
                provider=node.provider,
                has_attachments=bool(uploaded_images),
                prompt_length=len(resolved_inputs["prompt"]),
            )
            node.provider = routing_result.provider
            node.model_name = routing_result.model
            node.routing_decision = routing_result.decision
            node.save(update_fields=["provider", "model_name", "routing_decision", "updated_at"])

    try:
        prompt_attachments = create_node_attachments(node=target_node, files=uploaded_images)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

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
                    "attachment_count": len(prompt_attachments),
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
                prompt_attachments=prompt_attachments,
            ):
                if chunk.text:
                    assistant_chunks.append(chunk.text)
                    yield _sse_event("delta", {"delta": chunk.text})
                if chunk.tool_call:
                    yield _sse_event("tool_call", chunk.tool_call)
                if chunk.tool_result:
                    yield _sse_event("tool_result", chunk.tool_result)
            updated_node = append_messages_to_node_with_reply(
                node=target_node,
                prompt=resolved_inputs["prompt"],
                assistant_reply="".join(assistant_chunks),
                prompt_attachments=prompt_attachments,
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

@require_POST
def compare_nodes(request, slug: str):
    workspace = get_object_or_404(Workspace, slug=slug)
    try:
        payload = _parse_json_payload(request)
        node_id_a = payload.get("node_id_a")
        node_id_b = payload.get("node_id_b")
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    if not node_id_a or not node_id_b:
        return HttpResponseBadRequest("node_id_a and node_id_b are required.")

    node_a = get_object_or_404(
        ConversationNode.objects.prefetch_related("messages__attachments", "attachments", "tool_invocations"),
        pk=node_id_a,
        workspace=workspace,
    )
    node_b = get_object_or_404(
        ConversationNode.objects.prefetch_related("messages__attachments", "attachments", "tool_invocations"),
        pk=node_id_b,
        workspace=workspace,
    )

    data_a = serialize_node(node_a)
    data_b = serialize_node(node_b)

    def get_lineage_info(node):
        lineage = _build_lineage(node)
        return {
            "depth": len(lineage),
            "titles": [n.title for n in lineage],
            "total_tool_count": sum(n.tool_invocations.count() for n in lineage),
        }

    data_a["lineage"] = get_lineage_info(node_a)
    data_b["lineage"] = get_lineage_info(node_b)

    return JsonResponse({
        "node_a": data_a,
        "node_b": data_b,
    })


def mcp_source_list(request):
    workspace = list_workspaces().first() or get_or_create_default_workspace()
    sources = MCPSource.objects.all().order_by("created_at")
    source_rows = []

    def build_support_summary(source: MCPSource) -> dict:
        if source.source_type == MCPSource.SourceType.INTERNAL:
            return {
                "label": "Built-in",
                "detail": "Internal registry tools ship with the app and do not require external MCP transport setup.",
            }
        if source.source_type == MCPSource.SourceType.MOCK:
            return {
                "label": "Demo only",
                "detail": "Mock sources are useful for testing orchestration and UI flows, but they are not external MCP servers.",
            }

        transport = source.config.get("transport_kind", "stub")
        if transport == "stdio":
            return {
                "label": "Supported (stdio)",
                "detail": "This is the current production-ready MCP path in LLM-Tree.",
            }
        if transport == "sse":
            return {
                "label": "Planned (sse)",
                "detail": "SSE transport is recognized in configuration, but the client implementation is not complete yet.",
            }
        if transport == "stub":
            return {
                "label": "Demo only (stub)",
                "detail": "Stub transport simulates a remote MCP source for demos and testing only.",
            }
        return {
            "label": f"Unknown ({transport})",
            "detail": "This transport is not part of the supported MCP surface.",
        }

    for source in sources:
        diag = None
        if source.last_checked_at:
            diag = {
                "ok": source.last_check_ok,
                "label": source.last_check_label,
                "message": source.last_check_message,
                "tool_count": source.last_check_tool_count,
                "tool_names": source.last_check_tools_summary.split(", ") if source.last_check_tools_summary else [],
                "checked_at": source.last_checked_at,
            }
        source_rows.append(
            {
                "source": source,
                "diagnostic": diag,
                "support": build_support_summary(source),
            }
        )
    return render(
        request,
        "tree_ui/mcp_source_list.html",
        {
            "source_rows": source_rows,
            "workspace": workspace,
            "workspace_list": _serialize_workspace_list(workspace),
        },
    )

@require_POST
def mcp_source_install_demo(request):
    project_root = Path(__file__).resolve().parent.parent
    demo_server_path = project_root / "tree_ui" / "services" / "mcp" / "test_mcp_server.py"

    source, _ = MCPSource.objects.update_or_create(
        source_id="demo-stdio",
        defaults={
            "name": "Bundled Demo Stdio Server",
            "source_type": MCPSource.SourceType.MCP_SERVER,
            "is_enabled": True,
            "description": "Bundled stdio demo MCP server for validating the full end-to-end integration path.",
            "config": {
                "transport_kind": "stdio",
                "label": "Bundled Demo Stdio Server",
                "timeout": 30,
                "command": sys.executable,
                "args": [str(demo_server_path)],
                "cwd": str(project_root),
            },
        },
    )
    clear_diagnostics_result(source)
    default_dispatcher.refresh()
    return HttpResponseRedirect(reverse("mcp_source_list"))

def mcp_source_create(request):
    workspace = list_workspaces().first() or get_or_create_default_workspace()
    if request.method == "POST":
        form = MCPSourceForm(request.POST)
        if form.is_valid():
            form.save()
            default_dispatcher.refresh()
            return HttpResponseRedirect(reverse("mcp_source_list"))
    else:
        form = MCPSourceForm()

    return render(
        request,
        "tree_ui/mcp_source_form.html",
        {
            "form": form,
            "title": "Add MCP Source",
            "workspace": workspace,
            "workspace_list": _serialize_workspace_list(workspace),
        },
    )

def mcp_source_edit(request, source_id: int):
    workspace = list_workspaces().first() or get_or_create_default_workspace()
    source = get_object_or_404(MCPSource, pk=source_id)
    if request.method == "POST":
        form = MCPSourceForm(request.POST, instance=source)
        if form.is_valid():
            source = form.save()
            clear_diagnostics_result(source)
            default_dispatcher.refresh()
            return HttpResponseRedirect(reverse("mcp_source_list"))
    else:
        form = MCPSourceForm(instance=source)

    return render(
        request,
        "tree_ui/mcp_source_form.html",
        {
            "form": form,
            "title": f"Edit Source: {source.name}",
            "workspace": workspace,
            "workspace_list": _serialize_workspace_list(workspace),
        },
    )

@require_POST
def mcp_source_delete(request, source_id: int):
    source = get_object_or_404(MCPSource, pk=source_id)
    source.delete()
    default_dispatcher.refresh()
    return HttpResponseRedirect(reverse("mcp_source_list"))


@require_POST
def mcp_source_test(request, source_id: int):
    source = get_object_or_404(MCPSource, pk=source_id)
    result = diagnose_source(source)
    save_diagnostics_result(source, result)
    return HttpResponseRedirect(reverse("mcp_source_list"))
