import json
from typing import Any, Dict, List

from tree_ui.services.tools.registry import ToolRegistry, default_registry

from .base import ToolSource
from .schema import ToolDefinition, ToolResult


class InternalToolAdapter(ToolSource):
    """
    Adapts existing internal tools into the MCP-compatible interface.
    """

    def __init__(self, registry: ToolRegistry = default_registry):
        self._registry = registry

    @property
    def source_id(self) -> str:
        return "internal-registry"

    @property
    def source_type(self) -> str:
        return "internal"

    def list_tools(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description,
                input_schema=tool.parameters_schema,
                source_type=self.source_type,
                source_id=self.source_id,
            )
            for tool in self._registry.list_tools()
        ]

    def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> ToolResult:
        tool = self._registry.get_tool(name)
        if not tool:
            return ToolResult.from_error(f"Internal tool '{name}' not found.")

        try:
            result = tool.execute(context=context, **arguments)
            # Normalize internal tool result (usually a dict or primitive) to MCP text shape
            if isinstance(result, dict) and "error" in result:
                return ToolResult.from_error(message=str(result["error"]), metadata=result)

            if isinstance(result, (dict, list)):
                text_content = json.dumps(result)
            else:
                text_content = str(result)

            return ToolResult.from_text(text=text_content, metadata={"raw": result})
        except Exception as e:
            return ToolResult.from_error(f"Internal tool execution failed: {str(e)}")
