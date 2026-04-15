from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .schema import ToolDefinition, ToolResult


class BaseMCPClient(ABC):
    """
    Abstract interface for communicating with an MCP server.
    This can be implemented for different transports (stdio, sse, etc.).
    """

    @abstractmethod
    def list_tools(self) -> List[ToolDefinition]:
        """Fetch available tools from the remote server."""
        pass

    @abstractmethod
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """Invoke a tool on the remote server."""
        pass

    @abstractmethod
    def get_server_info(self) -> Dict[str, Any]:
        """Return information about the connected server."""
        pass


class UnsupportedTransportClient(BaseMCPClient):
    """
    Placeholder client for remote transport kinds that are recognized but not yet implemented.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.server_label = config.get("label", "Remote MCP Server")
        self.transport_kind = config.get("transport_kind", "unknown")

    def list_tools(self) -> List[ToolDefinition]:
        raise NotImplementedError(
            f"Transport '{self.transport_kind}' is recognized but not yet implemented (unsupported)."
        )

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        return ToolResult.from_error(
            f"Transport '{self.transport_kind}' is recognized but not yet implemented."
        )

    def get_server_info(self) -> Dict[str, Any]:
        return {
            "label": self.server_label,
            "transport": self.transport_kind,
            "status": "not_implemented",
        }


class StubMCPClient(BaseMCPClient):
    """
    A stub implementation of BaseMCPClient for the v2 foundation phase.
    It simulates a remote server without real network I/O.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.server_label = config.get("label", "Stub Server")
        self.transport_kind = config.get("transport_kind", "stub")

    def list_tools(self) -> List[ToolDefinition]:
        # Simulate some tools that look like they come from a remote server
        return [
            ToolDefinition(
                name="remote_calculator",
                description=f"[{self.server_label}] Performs calculations on a remote server.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "enum": ["add", "multiply"]},
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                    },
                    "required": ["operation", "a", "b"],
                },
            ),
            ToolDefinition(
                name="remote_fetch",
                description=f"[{self.server_label}] Fetches data from a simulated remote endpoint.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                    },
                    "required": ["url"],
                },
            ),
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        if name == "remote_calculator":
            op = arguments["operation"]
            a = arguments["a"]
            b = arguments["b"]
            res = a + b if op == "add" else a * b
            return ToolResult.from_text(
                f"Result: {res}",
                metadata={"server": self.server_label, "op": op},
            )

        if name == "remote_fetch":
            url = arguments["url"]
            return ToolResult.from_text(
                f"Simulated data from {url}",
                metadata={"server": self.server_label, "url": url},
            )

        return ToolResult.from_error(f"Tool '{name}' not found on stub server.")

    def get_server_info(self) -> Dict[str, Any]:
        return {
            "label": self.server_label,
            "transport": self.transport_kind,
            "status": "connected",
        }
