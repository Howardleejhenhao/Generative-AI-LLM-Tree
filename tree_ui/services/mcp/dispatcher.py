from typing import Any, Dict, List, Optional

from .base import ToolSource
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

    @classmethod
    def from_db(cls):
        """
        Factory method to create a dispatcher with sources loaded from the database.
        """
        dispatcher = cls()
        try:
            from tree_ui.models import MCPSource

            enabled_sources = list(MCPSource.objects.filter(is_enabled=True))
            has_internal_registration = MCPSource.objects.filter(
                source_type=MCPSource.SourceType.INTERNAL
            ).exists()

            if not has_internal_registration:
                # Preserve backward compatibility unless internal has been explicitly configured.
                from .internal_adapter import InternalToolAdapter

                dispatcher.add_source(InternalToolAdapter())

            for source_model in enabled_sources:
                adapter = create_adapter_from_model(source_model)
                if adapter:
                    dispatcher.add_source(adapter)
        except Exception:
            # Fallback if DB is not ready or during migrations
            from .internal_adapter import InternalToolAdapter

            dispatcher.add_source(InternalToolAdapter())

        return dispatcher


def create_adapter_from_model(source_model: Any) -> Optional[ToolSource]:
    """
    Creates the appropriate adapter for a given MCPSource model instance.
    """
    from tree_ui.models import MCPSource

    if source_model.source_type == MCPSource.SourceType.INTERNAL:
        from .internal_adapter import InternalToolAdapter

        return InternalToolAdapter(
            source_id=source_model.source_id,
            name=source_model.name,
        )
    elif source_model.source_type == MCPSource.SourceType.MOCK:
        from .mock_adapter import MockExternalMCPAdapter

        return MockExternalMCPAdapter(
            source_id=source_model.source_id, name=source_model.name
        )
    elif source_model.source_type == MCPSource.SourceType.MCP_SERVER:
        from .remote_adapter import RemoteMCPSourceAdapter

        return RemoteMCPSourceAdapter(
            source_id=source_model.source_id,
            name=source_model.name,
            config=source_model.config,
        )
    return None


class LazyDispatcher:
    """
    Proxies calls to a singleton MCPDispatcher instance that is lazily loaded.
    """

    def __init__(self):
        self._instance: Optional[MCPDispatcher] = None

    def _get_instance(self) -> MCPDispatcher:
        if self._instance is None:
            self._instance = MCPDispatcher.from_db()
        return self._instance

    def list_tools(self) -> List[ToolDefinition]:
        return self._get_instance().list_tools()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return self._get_instance().get_tool_schemas()

    def execute_tool(self, *args, **kwargs) -> ToolResult:
        return self._get_instance().execute_tool(*args, **kwargs)

    def add_source(self, source: ToolSource):
        self._get_instance().add_source(source)

    def refresh(self):
        """Force reload from DB."""
        self._instance = MCPDispatcher.from_db()


# Replace the hardcoded dispatcher with the lazy one.
default_dispatcher = LazyDispatcher()
