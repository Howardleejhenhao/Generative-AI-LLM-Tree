from django.urls import path

from tree_ui import views

urlpatterns = [
    path("", views.workspace_graph, name="workspace_graph"),
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
]
