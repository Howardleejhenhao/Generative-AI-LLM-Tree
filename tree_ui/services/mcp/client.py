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


class StdioMCPClient(BaseMCPClient):
    """
    Client for MCP servers running as local subprocesses via stdio.
    This is a skeleton for the v2 foundation phase.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.server_label = config.get("label", "Local Stdio Server")
        self.transport_kind = "stdio"

        # Stdio-specific config parsing
        self.command = config.get("command", "")
        self.args = config.get("args", [])
        self.env = config.get("env", {})
        self.cwd = config.get("cwd", None)
        self.timeout = config.get("timeout", 30)

    def list_tools(self) -> List[ToolDefinition]:
        """
        Placeholder for listing tools from a subprocess-based server.
        For the skeleton phase, we return a transport-incomplete indicator.
        """
        if not self.command:
            raise ValueError("No command configured for stdio transport.")

        # In a real implementation, we would start the subprocess here
        # or reuse an existing process, and perform the MCP handshake.
        return [
            ToolDefinition(
                name=f"stdio_placeholder_{self.server_label.replace(' ', '_').lower()}",
                description=(
                    f"[{self.server_label}] Stdio transport skeleton is active. "
                    "Full protocol exchange not yet implemented."
                ),
                input_schema={
                    "type": "object",
                    "properties": {},
                },
            )
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        Placeholder for calling a tool on a subprocess-based server.
        """
        return ToolResult.from_text(
            f"Stdio transport skeleton for '{self.server_label}' received call to '{name}'. "
            "Actual subprocess execution is not yet implemented in this foundation version.",
            metadata={
                "transport": "stdio",
                "command": self.command,
                "status": "skeleton_only",
            },
        )

    def get_server_info(self) -> Dict[str, Any]:
        return {
            "label": self.server_label,
            "transport": self.transport_kind,
            "command": self.command,
            "status": "skeleton",
        }
