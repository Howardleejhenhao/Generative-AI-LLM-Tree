from __future__ import annotations

from typing import Any

from tree_ui.models import MCPSource
from tree_ui.services.mcp.dispatcher import create_adapter_from_model


def _status_tone(status_code: str) -> str:
    if status_code in {"ready", "connected", "stub_ready"}:
        return "success"
    if status_code in {"skeleton", "not_implemented"}:
        return "warning"
    if status_code in {"unavailable", "error"}:
        return "danger"
    return "muted"


def _status_label(status_code: str) -> str:
    labels = {
        "ready": "Ready",
        "connected": "Connected",
        "stub_ready": "Stub Ready",
        "skeleton": "Skeleton",
        "not_implemented": "Not Implemented",
        "unavailable": "Unavailable",
        "disabled": "Disabled",
        "error": "Error",
    }
    return labels.get(status_code, "Unknown")


def describe_source(source: MCPSource) -> dict[str, Any]:
    transport_kind = ""
    if source.source_type == MCPSource.SourceType.MCP_SERVER:
        transport_kind = source.config.get("transport_kind", "stub")

    if not source.is_enabled:
        return {
            "source": source,
            "transport_kind": transport_kind,
            "status_code": "disabled",
            "status_label": _status_label("disabled"),
            "status_tone": _status_tone("disabled"),
            "tool_count": 0,
            "status_message": "Source is disabled and will not be registered by the dispatcher.",
            "tool_names": [],
            "client_info": {},
        }

    adapter = create_adapter_from_model(source)
    if not adapter:
        return {
            "source": source,
            "transport_kind": transport_kind,
            "status_code": "error",
            "status_label": _status_label("error"),
            "status_tone": _status_tone("error"),
            "tool_count": 0,
            "status_message": "No adapter could be created for this source type.",
            "tool_names": [],
            "client_info": {},
        }

    tools = adapter.list_tools()
    client_info = adapter.get_status()["client_info"] if hasattr(adapter, "get_status") else {}
    status_code = client_info.get("status", "ready")
    status_message = ""

    if tools and tools[0].name.endswith("__unavailable"):
        status_code = "unavailable"
        status_message = tools[0].description
    elif status_code == "connected" and transport_kind == "stub":
        status_code = "stub_ready"
        status_message = "Stub transport is active and returning simulated tools."
    elif status_code == "skeleton":
        status_message = "Stdio transport skeleton is configured; real subprocess protocol is not implemented yet."
    elif status_code == "not_implemented":
        status_message = "Transport is recognized but not implemented yet."
    elif source.source_type == MCPSource.SourceType.INTERNAL:
        status_message = "Internal tool registry is active."
    elif source.source_type == MCPSource.SourceType.MOCK:
        status_message = "Mock external source is active."
    else:
        status_message = "Source is active."

    return {
        "source": source,
        "transport_kind": transport_kind,
        "status_code": status_code,
        "status_label": _status_label(status_code),
        "status_tone": _status_tone(status_code),
        "tool_count": len(tools),
        "status_message": status_message,
        "tool_names": [tool.name for tool in tools[:4]],
        "client_info": client_info,
    }


def describe_sources(sources: list[MCPSource]) -> list[dict[str, Any]]:
    return [describe_source(source) for source in sources]
