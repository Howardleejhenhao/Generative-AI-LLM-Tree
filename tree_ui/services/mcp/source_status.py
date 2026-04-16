from typing import Any, Dict
from django.utils import timezone

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


def save_diagnostics_result(source_model: Any, result: Dict[str, Any]) -> None:
    source_model.last_checked_at = timezone.now()
    source_model.last_check_ok = result.get("ok", False)
    source_model.last_check_label = result.get("label", "Unknown")
    source_model.last_check_message = result.get("message", "")
    source_model.last_check_tool_count = result.get("tool_count", 0)
    source_model.last_check_tools_summary = ", ".join(result.get("tool_names", []))
    source_model.save(
        update_fields=[
            "last_checked_at",
            "last_check_ok",
            "last_check_label",
            "last_check_message",
            "last_check_tool_count",
            "last_check_tools_summary",
            "updated_at",
        ]
    )


def clear_diagnostics_result(source_model: Any) -> None:
    source_model.last_checked_at = None
    source_model.last_check_ok = None
    source_model.last_check_label = ""
    source_model.last_check_message = ""
    source_model.last_check_tool_count = None
    source_model.last_check_tools_summary = ""
    source_model.save(
        update_fields=[
            "last_checked_at",
            "last_check_ok",
            "last_check_label",
            "last_check_message",
            "last_check_tool_count",
            "last_check_tools_summary",
            "updated_at",
        ]
    )
