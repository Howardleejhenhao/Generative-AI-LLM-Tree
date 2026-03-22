from django.contrib import admin

from tree_ui.models import ConversationNode, NodeMessage, Workspace


class NodeMessageInline(admin.TabularInline):
    model = NodeMessage
    extra = 0
    ordering = ("order_index",)


@admin.register(ConversationNode)
class ConversationNodeAdmin(admin.ModelAdmin):
    list_display = ("title", "workspace", "provider", "model_name", "temperature", "parent")
    list_filter = ("provider", "workspace")
    search_fields = ("title", "summary", "model_name", "system_prompt")
    inlines = [NodeMessageInline]


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "updated_at")
    search_fields = ("name", "slug")
