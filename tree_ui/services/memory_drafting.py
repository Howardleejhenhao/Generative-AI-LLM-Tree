from __future__ import annotations

import json

from tree_ui.models import ConversationMemory, ConversationNode
from tree_ui.services.context_builder import ContextMessage, build_generation_messages
from tree_ui.services.providers import ProviderError, generate_text


MEMORY_DRAFT_SYSTEM_INSTRUCTION = (
    "You create one useful long-term memory draft from a branching conversation. "
    "Return strict JSON only with keys: scope, memory_type, title, content. "
    "Choose scope as either 'workspace' or 'branch'. "
    "Choose memory_type as one of: fact, preference, summary, task, artifact. "
    "Create a concise, reusable memory the user may want to keep. "
    "Do not include markdown fences or explanations."
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

    compact = " ".join(fallback_content.split())
    if len(compact) > 220:
        compact = f"{compact[:217]}..."

    return {
        "scope": ConversationMemory.Scope.BRANCH,
        "memory_type": ConversationMemory.MemoryType.SUMMARY,
        "title": node.title[:160],
        "content": compact,
        "used_fallback": True,
    }


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
            max_output_tokens=220,
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
    content = str(payload.get("content", "")).strip()
    if not content:
        return _fallback_memory_draft(node)

    return {
        "scope": scope,
        "memory_type": memory_type,
        "title": title,
        "content": content,
        "used_fallback": False,
    }
