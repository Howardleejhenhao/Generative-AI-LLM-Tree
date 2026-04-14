from typing import Any, Dict, List, Optional

from .base import ToolSource
from .client import BaseMCPClient, StubMCPClient, UnsupportedTransportClient
from .schema import ToolDefinition, ToolResult


class RemoteMCPSourceAdapter(ToolSource):
    """
    Adapter for a 'remote' MCP server.
    Handles configuration parsing, validation, and client lifecycle management.
    """

    SUPPORTED_TRANSPORTS = ["stub", "sse", "stdio"]

    def __init__(
        self,
        source_id: str,
        name: str,
        config: Dict[str, Any],
        client: Optional[BaseMCPClient] = None,
    ):
        self._source_id = source_id
        self._name = name
        self._raw_config = config
        self._parsed_config = self.parse_and_validate_config(config)

        self._client = client or self.build_client(self._parsed_config)

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def source_type(self) -> str:
        return "mcp_server"

    @classmethod
    def parse_and_validate_config(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensures the config has the required minimum structure for a remote source.
        """
        validated = config.copy()

        # Minimum transport_kind requirement
        transport_kind = validated.get("transport_kind", "stub")
        if transport_kind not in cls.SUPPORTED_TRANSPORTS:
            transport_kind = "stub"
        validated["transport_kind"] = transport_kind

        # Minimum metadata
        validated["label"] = validated.get("label", "Remote MCP Server")
        validated["endpoint"] = validated.get("endpoint", "")
        validated["timeout"] = validated.get("timeout", 30)

        # Potential for tool filtering / subsetting
        validated["enabled_tools"] = validated.get("enabled_tools", [])

        return validated

    @staticmethod
    def build_client(config: Dict[str, Any]) -> BaseMCPClient:
        transport_kind = config.get("transport_kind", "stub")
        if transport_kind == "stub":
            return StubMCPClient(config)
        return UnsupportedTransportClient(config)

    def list_tools(self) -> List[ToolDefinition]:
        """List all tools fetched from the remote client."""
        try:
            tools = self._client.list_tools()
            # Enrich tool metadata with source context
            enriched = []
            for t in tools:
                enriched.append(
                    ToolDefinition(
                        name=t.name,
                        description=t.description,
                        input_schema=t.input_schema,
                        source_type=self.source_type,
                        source_id=self.source_id,
                    )
                )
            return enriched
        except Exception as e:
            return [
                ToolDefinition(
                    name=f"{self.source_id}__unavailable",
                    description=(
                        f"[{self._name}] Remote source unavailable: {str(e)}"
                    ),
                    input_schema={
                        "type": "object",
                        "properties": {},
                    },
                    source_type=self.source_type,
                    source_id=self.source_id,
                )
            ]

    def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> ToolResult:
        """Executes a tool call via the remote client."""
        try:
            return self._client.call_tool(name, arguments)
        except Exception as e:
            return ToolResult.from_error(f"Remote MCP execution failed: {str(e)}")

    def get_status(self) -> Dict[str, Any]:
        """Returns diagnostic info for this source."""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "config": self._parsed_config,
            "client_info": self._client.get_server_info(),
        }
