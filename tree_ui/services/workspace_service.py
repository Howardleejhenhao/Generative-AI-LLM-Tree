from tree_ui.models import Workspace

DEFAULT_WORKSPACE_SLUG = "main-workspace"


def get_or_create_default_workspace() -> Workspace:
    workspace, _ = Workspace.objects.get_or_create(
        slug=DEFAULT_WORKSPACE_SLUG,
        defaults={
            "name": "Main Workspace",
            "description": (
                "Primary branching conversation graph for the local LLM-Tree MVP."
            ),
        },
    )
    return workspace
