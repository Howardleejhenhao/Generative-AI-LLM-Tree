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
    path("api/workspaces/", views.create_workspace_view, name="create_workspace"),
    path(
        "api/workspaces/<slug:slug>/nodes/",
        views.create_workspace_node,
        name="create_workspace_node",
    ),
    path(
        "api/workspaces/<slug:slug>/nodes/stream/",
        views.stream_workspace_node,
        name="stream_workspace_node",
    ),
    path(
        "api/workspaces/<slug:slug>/nodes/<int:node_id>/edit-variant/",
        views.create_edited_node_variant,
        name="create_edited_node_variant",
    ),
]
