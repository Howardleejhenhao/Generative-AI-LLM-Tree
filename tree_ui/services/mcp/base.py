from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .schema import ToolDefinition, ToolResult


class ToolSource(ABC):
    """
    Abstract base for a source of tools (e.g., Internal Registry, Remote MCP Server).
    """

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique identifier for this source."""
        pass

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Type of source: 'internal' or 'mcp'."""
        pass

    @abstractmethod
    def list_tools(self) -> List[ToolDefinition]:
        """List all tools available from this source."""
        pass

    @abstractmethod
    def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute a tool from this source."""
        pass
