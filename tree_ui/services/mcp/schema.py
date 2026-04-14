from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    source_type: str = "internal"
    source_id: str = "local"


@dataclass(frozen=True)
class ToolInvocationRequest:
    name: str
    arguments: Dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """
    Normalized result shape for tool execution, aligning with MCP CallToolResult.
    """
    content: List[Dict[str, Any]]
    is_error: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_text(cls, text: str, is_error: bool = False, metadata: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls(
            content=[{"type": "text", "text": text}],
            is_error=is_error,
            metadata=metadata or {},
        )

    @classmethod
    def from_error(cls, message: str, metadata: Optional[Dict[str, Any]] = None) -> "ToolResult":
        return cls.from_text(text=message, is_error=True, metadata=metadata)
