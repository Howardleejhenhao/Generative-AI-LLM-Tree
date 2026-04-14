from django.urls import path

from tree_ui import views

urlpatterns = [
    path("", views.workspace_home, name="workspace_home"),
    path("workspaces/<slug:slug>/", views.workspace_graph, name="workspace_graph"),
    path(
        "workspaces/<slug:slug>/nodes/<int:node_id>/",
        views.workspace_node_chat,
        name="workspace_node_chat",
    ),
    path(
        "workspaces/<slug:slug>/nodes/<int:node_id>/memory/",
        views.workspace_node_memory,
        name="workspace_node_memory",
    ),
    path("api/workspaces/", views.create_workspace_view, name="create_workspace"),
    path(
        "api/workspaces/<slug:slug>/memories/",
        views.create_workspace_memory_view,
        name="create_workspace_memory",
    ),
    path(
        "api/workspaces/<slug:slug>/delete/",
        views.delete_workspace_view,
        name="delete_workspace",
    ),
    path(
        "api/workspaces/<slug:slug>/nodes/",
        views.create_workspace_node,
        name="create_workspace_node",
    ),
    path(
        "api/workspaces/<slug:slug>/nodes/<int:node_id>/delete/",
        views.delete_workspace_node,
        name="delete_workspace_node",
    ),
    path(
        "api/workspaces/<slug:slug>/nodes/<int:node_id>/position/",
        views.update_node_position,
        name="update_node_position",
    ),
    path(
        "api/workspaces/<slug:slug>/nodes/<int:node_id>/title/",
        views.update_node_title,
        name="update_node_title",
    ),
    path(
        "api/workspaces/<slug:slug>/nodes/stream/",
        views.stream_workspace_node,
        name="stream_workspace_node",
    ),
    path(
        "api/workspaces/<slug:slug>/nodes/<int:node_id>/messages/stream/",
        views.stream_node_message,
        name="stream_node_message",
    ),
    path(
        "api/workspaces/<slug:slug>/nodes/<int:node_id>/edit-variant/",
        views.create_edited_node_variant,
        name="create_edited_node_variant",
    ),
]
