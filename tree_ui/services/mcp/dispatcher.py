from typing import Any, Dict, List, Optional

from .base import ToolSource
from .internal_adapter import InternalToolAdapter
from .schema import ToolDefinition, ToolResult


class MCPDispatcher:
    """
    Main entry point for tool management and execution.
    Orchestrates multiple tool sources (Internal, MCP Servers).
    """

    def __init__(self, sources: List[ToolSource] | None = None):
        self._sources: Dict[str, ToolSource] = {}
        if sources:
            for source in sources:
                self.add_source(source)

    def add_source(self, source: ToolSource):
        self._sources[source.source_id] = source

    def list_tools(self) -> List[ToolDefinition]:
        """Aggregate all tools from all registered sources."""
        all_tools = []
        for source in self._sources.values():
            all_tools.extend(source.list_tools())
        return all_tools

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Returns all tool schemas in a format compatible with common LLM providers (e.g., OpenAI).
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self.list_tools()
        ]

    def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> ToolResult:
        """
        Finds and executes the requested tool.
        In this foundation version, we assume unique tool names across sources.
        """
        # Search for the tool in each source
        for source in self._sources.values():
            # Quick check if tool exists in this source
            tool_found = any(t.name == name for t in source.list_tools())
            if tool_found:
                return source.execute_tool(name, arguments, context=context)

        return ToolResult.from_error(f"Tool '{name}' not found in any registered source.")


# Initialize the global default dispatcher with the internal adapter.
default_dispatcher = MCPDispatcher(sources=[InternalToolAdapter()])
