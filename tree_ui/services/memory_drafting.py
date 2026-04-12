from __future__ import annotations

import json
import re

from django.db import transaction

from tree_ui.models import ConversationMemory, ConversationNode
from tree_ui.services.context_builder import ContextMessage, build_generation_messages
from tree_ui.services.providers import ProviderError, generate_text


MEMORY_DRAFT_SYSTEM_INSTRUCTION = (
    "You create one useful long-term memory draft from a branching conversation. "
    "Return strict JSON only with keys: scope, memory_type, title, content. "
    "Choose scope as either 'workspace' or 'branch'. "
    "Choose memory_type as one of: fact, preference, summary, task, artifact. "
    "Create a concise, reusable memory the user may want to keep. "
    "Keep content as one short complete paragraph in plain text. "
    "Do not use bullet lists. Do not end with ellipsis. "
    "Do not include markdown fences or explanations."
)

WORKSPACE_MEMORY_SYSTEM_INSTRUCTION = (
    "You maintain one read-only workspace memory block for an entire conversation workspace. "
    "Summarize the important ongoing context, goals, decisions, preferences, and recurring instructions across the whole workspace. "
    "This memory will be reused as reference for future replies in the workspace. "
    "Return strict JSON only with keys: title, content. "
    "Set title to 'Workspace memory'. "
    "Content must be one short complete paragraph in plain text. "
    "Do not use bullet lists. Do not end with ellipsis. "
    "If the workspace is still empty, say that no durable workspace memory has been established yet."
)


def _extract_json_object(raw_text: str) -> dict:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Draft response did not contain JSON.")
    return json.loads(raw_text[start : end + 1])


def _fallback_memory_draft(node: ConversationNode) -> dict:
    latest_message = node.messages.order_by("-order_index", "-created_at").first()
    fallback_content = latest_message.content.strip() if latest_message else node.summary.strip()
    if not fallback_content:
        fallback_content = f"Key detail from {node.title}."

    compact = _normalize_draft_content(fallback_content)

    return {
        "scope": ConversationMemory.Scope.BRANCH,
        "memory_type": ConversationMemory.MemoryType.SUMMARY,
        "title": node.title[:160],
        "content": compact,
        "used_fallback": True,
    }


def _normalize_draft_content(raw_content: str) -> str:
    compact = " ".join(raw_content.split())
    compact = re.sub(r"(\.\.\.|…)+\s*$", "", compact).strip()
    if len(compact) > 420:
        sentence_matches = list(re.finditer(r"[。！？!?]", compact))
        truncated = compact[:420].rstrip()
        for match in sentence_matches:
            if match.end() <= 420:
                truncated = compact[: match.end()].strip()
        compact = truncated

    if compact and compact[-1] not in "。！？!?.":  # keep the draft looking complete
        compact = f"{compact}。"
    return compact


def generate_memory_draft_for_node(node: ConversationNode) -> dict:
    prompt = (
        "Generate one best long-term memory draft for this node. "
        "Prefer branch scope unless the memory is clearly useful across the whole workspace."
    )
    messages: list[ContextMessage] = build_generation_messages(parent=node, prompt=prompt)

    try:
        result = generate_text(
            provider_name=node.provider,
            model_name=node.model_name,
            messages=messages,
            system_instruction=MEMORY_DRAFT_SYSTEM_INSTRUCTION,
            temperature=0.2,
            top_p=0.9,
            max_output_tokens=420,
        )
        payload = _extract_json_object(result.text)
    except (ProviderError, ValueError, json.JSONDecodeError):
        return _fallback_memory_draft(node)

    scope = payload.get("scope", ConversationMemory.Scope.BRANCH)
    if scope not in ConversationMemory.Scope.values:
        scope = ConversationMemory.Scope.BRANCH

    memory_type = payload.get("memory_type", ConversationMemory.MemoryType.SUMMARY)
    if memory_type not in ConversationMemory.MemoryType.values:
        memory_type = ConversationMemory.MemoryType.SUMMARY

    title = str(payload.get("title", "")).strip()[:160]
    content = _normalize_draft_content(str(payload.get("content", "")).strip())
    if not content:
        return _fallback_memory_draft(node)

    return {
        "scope": scope,
        "memory_type": memory_type,
        "title": title,
        "content": content,
        "used_fallback": False,
    }


def _build_workspace_context_messages(workspace) -> list[ContextMessage]:
    rows = (
        workspace.nodes.filter(messages__isnull=False)
        .prefetch_related("messages")
        .order_by("created_at")
    )
    transcript_lines: list[str] = []
    for node in rows:
        transcript_lines.append(f"[Node] {node.title}")
        for message in node.messages.order_by("order_index", "created_at"):
            compact = " ".join(message.content.split())
            if len(compact) > 240:
                compact = f"{compact[:237].rstrip()}..."
            transcript_lines.append(f"{message.role.upper()}: {compact}")

    if not transcript_lines:
        transcript_lines.append("No prior conversation yet.")

    snapshot = "\n".join(transcript_lines)
    if len(snapshot) > 12000:
        snapshot = snapshot[-12000:]

    return [
        ContextMessage(
            role="user",
            content=(
                "Summarize this workspace's conversations into one durable workspace memory.\n\n"
                f"{snapshot}"
            ),
        )
    ]


def refresh_workspace_preference_memory(reference_node: ConversationNode) -> ConversationMemory:
    workspace = reference_node.workspace
    messages = _build_workspace_context_messages(workspace)
    fallback = {
        "title": "Workspace memory",
        "content": "No durable workspace memory has been established yet.",
    }

    try:
        result = generate_text(
            provider_name=reference_node.provider,
            model_name=reference_node.model_name,
            messages=messages,
            system_instruction=WORKSPACE_MEMORY_SYSTEM_INSTRUCTION,
            temperature=0.1,
            top_p=0.8,
            max_output_tokens=260,
        )
        payload = _extract_json_object(result.text)
        title = str(payload.get("title", fallback["title"])).strip()[:160] or fallback["title"]
        content = _normalize_draft_content(str(payload.get("content", "")).strip()) or fallback["content"]
    except (ProviderError, ValueError, json.JSONDecodeError):
        title = fallback["title"]
        content = fallback["content"]

    with transaction.atomic():
        memory, _ = ConversationMemory.objects.update_or_create(
            workspace=workspace,
            scope=ConversationMemory.Scope.WORKSPACE,
            source=ConversationMemory.Source.EXTRACTED,
            memory_type=ConversationMemory.MemoryType.SUMMARY,
            title="Workspace memory",
            defaults={
                "content": content,
                "branch_anchor": None,
                "source_node": reference_node,
                "source_message": None,
                "is_pinned": True,
            },
        )
        return memory
