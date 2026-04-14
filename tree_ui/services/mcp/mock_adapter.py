import json
from typing import Any, Dict, List

from .base import ToolSource
from .schema import ToolDefinition, ToolResult


class MockExternalMCPAdapter(ToolSource):
    """
    A mock MCP source adapter for testing multi-source architectural readiness.
    It simulates tools provided by an external server.
    """

    def __init__(self, source_id: str, name: str = "Mock Source"):
        self._source_id = source_id
        self._name = name

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def source_type(self) -> str:
        return "mock"

    def list_tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                name="external_echo",
                description="A mock tool from an 'external' source that echoes input.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Text to echo back",
                        }
                    },
                    "required": ["message"],
                },
                source_type=self.source_type,
                source_id=self.source_id,
            ),
            ToolDefinition(
                name="external_timestamp",
                description="Returns a mock timestamp from an external source.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["iso", "unix"],
                            "default": "iso",
                        }
                    },
                },
                source_type=self.source_type,
                source_id=self.source_id,
            ),
        ]

    def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> ToolResult:
        if name == "external_echo":
            msg = arguments.get("message", "No message provided.")
            return ToolResult.from_text(
                f"Mock external echo: {msg}",
                metadata={"source_name": self._name},
            )

        if name == "external_timestamp":
            fmt = arguments.get("format", "iso")
            ts = "2026-04-14T12:00:00Z" if fmt == "iso" else "1776254400"
            return ToolResult.from_text(
                ts,
                metadata={"source_name": self._name, "format": fmt},
            )

        return ToolResult.from_error(f"Tool '{name}' not found in mock source {self._source_id}.")
