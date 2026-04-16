from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Iterator

from django.conf import settings
from django.db import transaction

from tree_ui.models import ConversationNode, NodeAttachment, NodeMessage, ToolInvocation, Workspace
from tree_ui.services.context_builder import (
    build_system_instruction,
    build_branch_lineage,
    build_generation_messages,
    ContextMessage,
)
from tree_ui.services.memory_drafting import refresh_workspace_preference_memory
from tree_ui.services.model_catalog import resolve_model_name
from tree_ui.services.memory_service import format_memories_for_prompt, retrieve_memories_for_generation
from tree_ui.services.providers import ProviderError, generate_text, stream_text
from tree_ui.services.router import route_model
from tree_ui.services.mcp.dispatcher import default_dispatcher


@dataclass(frozen=True)
class ReplyChunk:
    text: str = ""
    tool_call: dict | None = None
    tool_result: dict | None = None


def _safe_parse_tool_arguments(raw_arguments: str) -> dict:
    if not raw_arguments:
        return {}
    try:
        return json.loads(raw_arguments)
    except json.JSONDecodeError:
        return {
            "error": "Invalid tool arguments JSON",
            "raw": raw_arguments,
        }


def _build_summary(prompt: str) -> str:
    prompt = " ".join(prompt.split())
    if len(prompt) <= 92:
        return prompt
    return f"{prompt[:89]}..."


def _build_node_title(title: str) -> str:
    clean_title = title.strip()
    if clean_title:
        return clean_title
    return "Untitled conversation"


def _normalize_system_prompt(system_prompt: Any) -> str:
    if system_prompt is None:
        return ""
    if not isinstance(system_prompt, str):
        raise ValueError("System prompt must be a string.")
    return system_prompt.strip()


def _normalize_optional_float(
    *,
    value: Any,
    field_label: str,
    minimum: float,
    maximum: float,
) -> float | None:
    if value in (None, ""):
        return None

    try:
        normalized_value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_label} must be a number.") from exc

    if normalized_value < minimum or normalized_value > maximum:
        raise ValueError(f"{field_label} must be between {minimum} and {maximum}.")

    return round(normalized_value, 4)


def _normalize_max_output_tokens(value: Any) -> int | None:
    if value in (None, ""):
        return None

    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("Max output tokens must be an integer.")
        normalized_value = int(value)
    else:
        if isinstance(value, str) and "." in value:
            raise ValueError("Max output tokens must be an integer.")
        try:
            normalized_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Max output tokens must be an integer.") from exc

    if normalized_value <= 0:
        raise ValueError("Max output tokens must be greater than 0.")

    return normalized_value


def _build_fallback_assistant_message(
    *,
    parent: ConversationNode | None,
    provider: str,
    model_name: str,
    prompt: str,
    reason: str,
) -> str:
    lineage = build_branch_lineage(parent)
    lineage_titles = " -> ".join(node.title for node in lineage) or "root"
    return (
        f"[Fallback {provider} response via {model_name}] "
        f"Branch context follows: {lineage_titles}. "
        f"Latest prompt: {prompt.strip()} "
        f"(Reason: {reason})"
    )


def generate_assistant_reply(
    *,
    parent: ConversationNode | None,
    provider: str,
    model_name: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float | None = None,
    top_p: float | None = None,
    max_output_tokens: int | None = None,
    prompt_attachments: list[NodeAttachment] | None = None,
) -> str:
    context_messages = build_generation_messages(
        parent=parent,
        prompt=prompt,
        prompt_attachments=prompt_attachments,
    )
    memory_text = ""
    if parent is not None:
        memory_text = format_memories_for_prompt(
            retrieve_memories_for_generation(
                workspace=parent.workspace,
                parent=parent,
            )
        )
    
    system_instruction = build_system_instruction(
        system_prompt,
        retrieved_memory_text=memory_text,
    )
    tools = default_dispatcher.get_tool_schemas()

    active_messages = list(context_messages)
    max_steps = 3
    
    try:
        for _ in range(max_steps):
            result = generate_text(
                provider_name=provider,
                model_name=model_name,
                messages=active_messages,
                system_instruction=system_instruction,
                tools=tools,
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_output_tokens,
            )

            if not result.tool_calls:
                return result.text

            # OpenAI can return multiple tool calls.
            # Execute all of them and feed them back into the next pass.
            # Add the assistant message with tool calls to history
            active_messages.append(
                ContextMessage(
                    role="assistant",
                    content=result.text,
                    tool_calls=tuple(result.tool_calls)
                )
            )

            for tc in result.tool_calls:
                context = {"workspace": parent.workspace} if parent else {}
                mcp_result = default_dispatcher.execute_tool(tc.name, tc.arguments, context=context)

                # Standardize persistence using MCP result shape
                if parent:
                    tool_def = next((t for t in default_dispatcher.list_tools() if t.name == tc.name), None)
                    tool_type = tool_def.source_type if tool_def else "unknown"
                    source_id = tool_def.source_id if tool_def else ""

                    ToolInvocation.objects.create(
                        node=parent,
                        tool_name=tc.name,
                        tool_type=tool_type,
                        source_id=source_id,
                        invocation_payload=json.dumps(tc.arguments),
                        result_payload=json.dumps(mcp_result.content),
                        success=not mcp_result.is_error,
                    )

                # Append tool result to history
                active_messages.append(
                    ContextMessage(
                        role="tool",
                        content=json.dumps(mcp_result.content),
                        tool_call_id=tc.call_id or tc.name,
                        tool_name=tc.name
                    )
                )

        # If we reached max_steps and the model is still asking for tools
        return f"[Tool limit reached after {max_steps} steps. Last result: {active_messages[-1].content[:100]}...]"

    except ProviderError as exc:
        return _build_fallback_assistant_message(
            parent=parent,
            provider=provider,
            model_name=model_name,
            prompt=prompt,
            reason=str(exc),
        )


def _calculate_position(
    *,
    workspace: Workspace,
    parent: ConversationNode | None,
) -> tuple[int, int]:
    if parent is None:
        root_count = workspace.nodes.filter(parent__isnull=True).count()
        return 80, 120 + (root_count * 190)

    sibling_count = parent.children.count()
    return parent.position_x + 340, parent.position_y + (sibling_count * 180)


def resolve_node_creation_inputs(
    *,
    workspace: Workspace,
    parent: ConversationNode | None,
    title: str,
    provider: str,
    model_name: str,
    routing_mode: str = ConversationNode.RoutingMode.MANUAL,
    system_prompt: Any,
    temperature: Any,
    top_p: Any,
    max_output_tokens: Any,
    prompt: str = "",
    has_attachments: bool = False,
) -> dict:
    if routing_mode == ConversationNode.RoutingMode.MANUAL:
        if provider not in ConversationNode.Provider.values:
            raise ValueError("Unsupported provider.")
        resolved_provider = provider
        resolved_model = resolve_model_name(provider=provider, model_name=model_name)
        routing_decision = ""
    else:
        # Routing with available signals.
        routing_result = route_model(
            routing_mode=routing_mode,
            provider=provider,
            has_attachments=has_attachments,
            prompt_length=len(prompt),
        )
        resolved_provider = routing_result.provider
        resolved_model = routing_result.model
        routing_decision = routing_result.decision

    position_x, position_y = _calculate_position(workspace=workspace, parent=parent)

    return {
        "provider": resolved_provider,
        "model_name": resolved_model,
        "routing_mode": routing_mode,
        "routing_decision": routing_decision,
        "title": _build_node_title(title),
        "summary": "Open this node to start the conversation.",
        "system_prompt": _normalize_system_prompt(system_prompt),
        "temperature": _normalize_optional_float(
            value=temperature,
            field_label="Temperature",
            minimum=0.0,
            maximum=2.0,
        ),
        "top_p": _normalize_optional_float(
            value=top_p,
            field_label="Top p",
            minimum=0.0,
            maximum=1.0,
        ),
        "max_output_tokens": _normalize_max_output_tokens(max_output_tokens),
        "position_x": position_x,
        "position_y": position_y,
    }


def resolve_message_append_inputs(*, prompt: str, has_attachments: bool = False) -> dict:
    normalized_prompt = prompt.strip()
    if not normalized_prompt and not has_attachments:
        raise ValueError("Prompt is required.")

    if normalized_prompt:
        summary = _build_summary(normalized_prompt)
    elif has_attachments:
        summary = "Image attachment"
    else:
        summary = "Untitled message"

    return {
        "prompt": normalized_prompt,
        "summary": summary,
    }


def iter_text_chunks(text: str, chunk_size: int = 24):
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]
        if settings.LLM_STREAM_CHUNK_DELAY_SECONDS > 0:
            time.sleep(settings.LLM_STREAM_CHUNK_DELAY_SECONDS)


def stream_assistant_reply(
    *,
    parent: ConversationNode | None,
    provider: str,
    model_name: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float | None = None,
    top_p: float | None = None,
    max_output_tokens: int | None = None,
    prompt_attachments: list[NodeAttachment] | None = None,
) -> Iterator[ReplyChunk]:
    context_messages = build_generation_messages(
        parent=parent,
        prompt=prompt,
        prompt_attachments=prompt_attachments,
    )
    memory_text = ""
    if parent is not None:
        memory_text = format_memories_for_prompt(
            retrieve_memories_for_generation(
                workspace=parent.workspace,
                parent=parent,
            )
        )

    system_instruction = build_system_instruction(
        system_prompt,
        retrieved_memory_text=memory_text,
    )
    tools = default_dispatcher.get_tool_schemas()

    # Multi-turn tool execution loop
    active_messages = list(context_messages)
    emitted_anything = False
    max_steps = 3
    step_count = 0

    while True:
        if step_count >= max_steps:
            yield ReplyChunk(text=f"\n[Tool limit reached after {max_steps} steps.]")
            break
        
        step_count += 1
        current_text = ""
        # In streaming, we only support one tool call per turn for simplicity of yielding.
        # However, OpenAI can return multiple. We'll track them.
        turn_tool_calls: dict[str, dict] = {} # call_id -> {name, arguments}

        try:
            for delta in stream_text(
                provider_name=provider,
                model_name=model_name,
                messages=active_messages,
                system_instruction=system_instruction,
                tools=tools,
                temperature=temperature,
                top_p=top_p,
                max_output_tokens=max_output_tokens,
            ):
                emitted_anything = True
                if delta.text:
                    current_text += delta.text
                    yield ReplyChunk(text=delta.text)
                if delta.tool_call:
                    call_id = delta.tool_call.call_id
                    if call_id not in turn_tool_calls:
                        turn_tool_calls[call_id] = {"name": delta.tool_call.name, "arguments": ""}
                        yield ReplyChunk(tool_call={"name": delta.tool_call.name, "id": call_id})
                    turn_tool_calls[call_id]["arguments"] += delta.tool_call.arguments
        except ProviderError as exc:
            if emitted_anything:
                raise

            fallback_message = _build_fallback_assistant_message(
                parent=parent,
                provider=provider,
                model_name=model_name,
                prompt=prompt,
                reason=str(exc),
            )
            for chunk in iter_text_chunks(fallback_message):
                yield ReplyChunk(text=chunk)
            return

        if not turn_tool_calls:
            break

        # Record assistant message with tool calls in history
        from tree_ui.services.providers.base import ToolCall
        tool_calls_objs = [
            ToolCall(
                call_id=cid,
                name=tc["name"],
                arguments=_safe_parse_tool_arguments(tc["arguments"]),
            )
            for cid, tc in turn_tool_calls.items()
        ]
        active_messages.append(
            ContextMessage(
                role="assistant",
                content=current_text,
                tool_calls=tuple(tool_calls_objs)
            )
        )

        # Execute tool calls
        for tc_obj in tool_calls_objs:
            context = {"workspace": parent.workspace} if parent else {}
            mcp_result = default_dispatcher.execute_tool(tc_obj.name, tc_obj.arguments, context=context)

            # Standardize persistence using MCP result shape
            if parent:
                tool_def = next((t for t in default_dispatcher.list_tools() if t.name == tc_obj.name), None)
                tool_type = tool_def.source_type if tool_def else "unknown"
                source_id = tool_def.source_id if tool_def else ""

                ToolInvocation.objects.create(
                    node=parent,
                    tool_name=tc_obj.name,
                    tool_type=tool_type,
                    source_id=source_id,
                    invocation_payload=json.dumps(tc_obj.arguments),
                    result_payload=json.dumps(mcp_result.content),
                    success=not mcp_result.is_error,
                )

            # Emit result for streaming consumers
            yield ReplyChunk(tool_result={"name": tc_obj.name, "result": mcp_result.content})

            # Feed back to model
            active_messages.append(
                ContextMessage(
                    role="tool",
                    content=json.dumps(mcp_result.content),
                    tool_call_id=tc_obj.call_id or tc_obj.name,
                    tool_name=tc_obj.name
                )
            )
        
        # Reset for next model pass
        continue


def create_node(
    *,
    workspace: Workspace,
    parent: ConversationNode | None,
    title: str,
    provider: str,
    model_name: str,
    routing_mode: str = ConversationNode.RoutingMode.MANUAL,
    system_prompt: Any = "",
    temperature: Any = None,
    top_p: Any = None,
    max_output_tokens: Any = None,
    prompt: str = "",
    has_attachments: bool = False,
) -> ConversationNode:
    resolved_inputs = resolve_node_creation_inputs(
        workspace=workspace,
        parent=parent,
        title=title,
        provider=provider,
        model_name=model_name,
        routing_mode=routing_mode,
        system_prompt=system_prompt,
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_output_tokens,
        prompt=prompt,
        has_attachments=has_attachments,
    )
    return ConversationNode.objects.create(
        workspace=workspace,
        parent=parent,
        title=resolved_inputs["title"],
        summary=resolved_inputs["summary"],
        provider=resolved_inputs["provider"],
        model_name=resolved_inputs["model_name"],
        routing_mode=resolved_inputs["routing_mode"],
        routing_decision=resolved_inputs["routing_decision"],
        system_prompt=resolved_inputs["system_prompt"],
        temperature=resolved_inputs["temperature"],
        top_p=resolved_inputs["top_p"],
        max_output_tokens=resolved_inputs["max_output_tokens"],
        position_x=resolved_inputs["position_x"],
        position_y=resolved_inputs["position_y"],
    )


def create_continuation_child(
    *,
    source_node: ConversationNode,
    title: str,
    prompt: str = "",
    has_attachments: bool = False,
) -> ConversationNode:
    return create_node(
        workspace=source_node.workspace,
        parent=source_node,
        title=title,
        provider=source_node.provider,
        model_name=source_node.model_name,
        routing_mode=source_node.routing_mode,
        system_prompt=source_node.system_prompt,
        temperature=source_node.temperature,
        top_p=source_node.top_p,
        max_output_tokens=source_node.max_output_tokens,
        prompt=prompt,
        has_attachments=has_attachments,
    )


def append_messages_to_node_with_reply(
    *,
    node: ConversationNode,
    prompt: str,
    assistant_reply: str,
    prompt_attachments: list[NodeAttachment] | None = None,
) -> ConversationNode:
    resolved_inputs = resolve_message_append_inputs(
        prompt=prompt,
        has_attachments=bool(prompt_attachments),
    )
    starting_order = node.messages.count()

    with transaction.atomic():
        user_message = NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.USER,
            content=resolved_inputs["prompt"],
            order_index=starting_order,
        )
        NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.ASSISTANT,
            content=assistant_reply,
            order_index=starting_order + 1,
        )
        if prompt_attachments:
            NodeAttachment.objects.filter(
                pk__in=[attachment.pk for attachment in prompt_attachments],
            ).update(source_message=user_message)
        node.summary = resolved_inputs["summary"]
        node.save(update_fields=["summary", "updated_at"])

    updated_node = ConversationNode.objects.prefetch_related("messages__attachments", "attachments").get(pk=node.pk)

    try:
        refresh_workspace_preference_memory(updated_node)
    except Exception:
        # Memory refresh is best-effort and must not break the main chat flow.
        pass

    return updated_node


def append_messages_to_node(
    *,
    node: ConversationNode,
    prompt: str,
    prompt_attachments: list[NodeAttachment] | None = None,
) -> ConversationNode:
    resolved_inputs = resolve_message_append_inputs(
        prompt=prompt,
        has_attachments=bool(prompt_attachments),
    )
    assistant_reply = generate_assistant_reply(
        parent=node,
        provider=node.provider,
        model_name=node.model_name,
        prompt=resolved_inputs["prompt"],
        system_prompt=node.system_prompt,
        temperature=node.temperature,
        top_p=node.top_p,
        max_output_tokens=node.max_output_tokens,
        prompt_attachments=prompt_attachments,
    )
    return append_messages_to_node_with_reply(
        node=node,
        prompt=resolved_inputs["prompt"],
        assistant_reply=assistant_reply,
        prompt_attachments=prompt_attachments,
    )
