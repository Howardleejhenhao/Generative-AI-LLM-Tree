from typing import Any, Dict
from django.utils import timezone

from .dispatcher import create_adapter_from_model


def summarize_client_info(client_info: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(client_info, dict):
        client_info = {}

    return {
        "transport": client_info.get("transport", ""),
        "client_status": client_info.get("status", ""),
        "message_endpoint": client_info.get("message_endpoint", ""),
        "last_error": client_info.get("last_error", ""),
    }


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
    client_summary = summarize_client_info(client_info)
    transport = client_summary.get("transport") or source_model.config.get("transport_kind", "")

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
            "client_status": client_summary.get("client_status", "error"),
            "message_endpoint": client_summary.get("message_endpoint", ""),
            "last_error": client_summary.get("last_error", ""),
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
            "client_status": client_summary.get("client_status", "error"),
            "message_endpoint": client_summary.get("message_endpoint", ""),
            "last_error": client_summary.get("last_error", ""),
        }

    refreshed_status = adapter.get_status() if hasattr(adapter, "get_status") else {}
    refreshed_client_info = (
        refreshed_status.get("client_info", {}) if isinstance(refreshed_status, dict) else {}
    )
    refreshed_client_summary = summarize_client_info(refreshed_client_info)
    tool_names = [tool.name for tool in tools]
    return {
        "source_id": source_model.source_id,
        "ok": True,
        "label": "Ready",
        "message": f"Connection succeeded. Discovered {len(tool_names)} tool(s).",
        "tool_count": len(tool_names),
        "tool_names": tool_names,
        "transport": refreshed_client_summary.get("transport") or transport,
        "client_status": refreshed_client_summary.get("client_status", "connected"),
        "message_endpoint": refreshed_client_summary.get("message_endpoint", ""),
        "last_error": refreshed_client_summary.get("last_error", ""),
    }


def save_diagnostics_result(source_model: Any, result: Dict[str, Any]) -> None:
    source_model.last_checked_at = timezone.now()
    source_model.last_check_ok = result.get("ok", False)
    source_model.last_check_label = result.get("label", "Unknown")
    source_model.last_check_message = result.get("message", "")
    source_model.last_check_tool_count = result.get("tool_count", 0)
    source_model.last_check_tools_summary = ", ".join(result.get("tool_names", []))
    source_model.last_check_transport = result.get("transport", "")
    source_model.last_check_client_status = result.get("client_status", "")
    source_model.last_check_message_endpoint = result.get("message_endpoint", "")
    source_model.last_check_last_error = result.get("last_error", "")
    source_model.save(
        update_fields=[
            "last_checked_at",
            "last_check_ok",
            "last_check_label",
            "last_check_message",
            "last_check_tool_count",
            "last_check_tools_summary",
            "last_check_transport",
            "last_check_client_status",
            "last_check_message_endpoint",
            "last_check_last_error",
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
    source_model.last_check_transport = ""
    source_model.last_check_client_status = ""
    source_model.last_check_message_endpoint = ""
    source_model.last_check_last_error = ""
    source_model.save(
        update_fields=[
            "last_checked_at",
            "last_check_ok",
            "last_check_label",
            "last_check_message",
            "last_check_tool_count",
            "last_check_tools_summary",
            "last_check_transport",
            "last_check_client_status",
            "last_check_message_endpoint",
            "last_check_last_error",
            "updated_at",
        ]
    )
