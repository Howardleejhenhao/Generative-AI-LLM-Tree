from django.utils.text import slugify

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


def list_workspaces():
    return Workspace.objects.order_by("created_at")


def get_workspace_by_slug(slug: str) -> Workspace:
    return Workspace.objects.get(slug=slug)


def build_unique_workspace_slug(name: str) -> str:
    base_slug = slugify(name) or "workspace"
    candidate = base_slug
    suffix = 2
    while Workspace.objects.filter(slug=candidate).exists():
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
    return candidate


def create_workspace(*, name: str, description: str = "") -> Workspace:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Workspace name is required.")

    workspace = Workspace.objects.create(
        name=clean_name,
        slug=build_unique_workspace_slug(clean_name),
        description=description.strip(),
    )
    return workspace
