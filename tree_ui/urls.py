from django.urls import path

from tree_ui import views

urlpatterns = [
    path("", views.workspace_graph, name="workspace_graph"),
]
