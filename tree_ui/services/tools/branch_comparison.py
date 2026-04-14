from typing import Any, Dict
from tree_ui.models import ConversationNode
from tree_ui.services.context_builder import build_branch_lineage
from .base import BaseTool

class BranchComparisonTool(BaseTool):
    @property
    def name(self) -> str:
        return "compare_branches"

    @property
    def description(self) -> str:
        return (
            "Compares two different conversation branches by summarizing their conversation history. "
            "Use this to understand differences in perspective or conclusions between sibling branches."
        )

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id_a": {
                    "type": "integer",
                    "description": "The ID of the leaf node for the first branch."
                },
                "node_id_b": {
                    "type": "integer",
                    "description": "The ID of the leaf node for the second branch."
                }
            },
            "required": ["node_id_a", "node_id_b"]
        }

    def execute(self, context: Dict[str, Any] | None = None, **kwargs) -> Any:
        node_id_a = kwargs.get("node_id_a")
        node_id_b = kwargs.get("node_id_b")
        workspace = context.get("workspace") if context else None

        if not node_id_a or not node_id_b:
            return {"error": "node_id_a and node_id_b are required."}

        try:
            if workspace:
                node_a = ConversationNode.objects.get(pk=node_id_a, workspace=workspace)
                node_b = ConversationNode.objects.get(pk=node_id_b, workspace=workspace)
            else:
                # Fallback if no workspace context, but at least ensure they share the same workspace
                node_a = ConversationNode.objects.get(pk=node_id_a)
                node_b = ConversationNode.objects.get(pk=node_id_b)
                if node_a.workspace_id != node_b.workspace_id:
                    return {"error": "Nodes must belong to the same workspace."}
        except ConversationNode.DoesNotExist:
            return {"error": "One or both node IDs are invalid or belong to a different workspace."}

        def get_branch_text(node):
            lineage = build_branch_lineage(node)
            summary = []
            for n in lineage:
                summary.append(f"Node: {n.title}")
                for msg in n.messages.all():
                    content_preview = msg.content[:200] + ("..." if len(msg.content) > 200 else "")
                    summary.append(f"  [{msg.role}] {content_preview}")
            return "\n".join(summary)

        return {
            "branch_a": {
                "id": node_id_a,
                "title": node_a.title,
                "content_summary": get_branch_text(node_a)
            },
            "branch_b": {
                "id": node_id_b,
                "title": node_b.title,
                "content_summary": get_branch_text(node_b)
            }
        }
