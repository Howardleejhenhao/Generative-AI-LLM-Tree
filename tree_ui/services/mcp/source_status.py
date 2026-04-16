from typing import Any, Dict

from .dispatcher import create_adapter_from_model


def diagnose_source(source_model: Any) -> Dict[str, Any]:
    adapter = create_adapter_from_model(source_model)
    if adapter is None:
        return {
            "source_id": source_model.source_id,
            "ok": False,
            "label": "Unavailable",
            "message": "No adapter is available for this source type.",
            "tool_count": 0,
            "tool_names": [],
        }

    base_status = adapter.get_status() if hasattr(adapter, "get_status") else {}
    client_info = base_status.get("client_info", {}) if isinstance(base_status, dict) else {}
    transport = client_info.get("transport") or source_model.config.get("transport_kind", "")

    try:
        tools = adapter.list_tools()
    except Exception as exc:
        return {
            "source_id": source_model.source_id,
            "ok": False,
            "label": "Unavailable",
            "message": str(exc),
            "tool_count": 0,
            "tool_names": [],
            "transport": transport,
            "client_status": client_info.get("status", "error"),
        }

    unavailable_name = f"{source_model.source_id}__unavailable"
    if len(tools) == 1 and tools[0].name == unavailable_name:
        return {
            "source_id": source_model.source_id,
            "ok": False,
            "label": "Unavailable",
            "message": tools[0].description,
            "tool_count": 0,
            "tool_names": [],
            "transport": transport,
            "client_status": client_info.get("status", "error"),
        }

    tool_names = [tool.name for tool in tools]
    return {
        "source_id": source_model.source_id,
        "ok": True,
        "label": "Ready",
        "message": f"Connection succeeded. Discovered {len(tool_names)} tool(s).",
        "tool_count": len(tool_names),
        "tool_names": tool_names,
        "transport": transport,
        "client_status": client_info.get("status", "connected"),
    }
