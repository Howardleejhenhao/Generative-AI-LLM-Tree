import json
from unittest.mock import Mock, patch

from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from tree_ui.models import ConversationMemory, ConversationNode, NodeMessage, Workspace
from tree_ui.services.context_builder import build_generation_messages
from tree_ui.services.memory_drafting import (
    WORKSPACE_MEMORY_FALLBACK_CONTENT,
    ensure_workspace_memory,
    generate_memory_draft_for_node,
    refresh_workspace_preference_memory,
)
from tree_ui.services.memory_service import (
    create_memory,
    format_memories_for_prompt,
    retrieve_memories_for_generation,
)
from tree_ui.services.node_creation import append_messages_to_node
from tree_ui.services.node_editing import create_edited_variant
from tree_ui.services.providers import ProviderError
from tree_ui.services.providers.base import GenerationResult
from tree_ui.services.providers.registry import generate_text as registry_generate_text


class WorkspaceGraphViewTests(TestCase):
    def test_homepage_redirects_to_a_workspace(self):
        response = self.client.get(reverse("workspace_home"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Workspace.objects.count(), 1)
        workspace = Workspace.objects.get()
        self.assertEqual(response.url, reverse("workspace_graph", args=[workspace.slug]))

    def test_workspace_page_renders_graph_shell(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        response = self.client.get(reverse("workspace_graph", args=[workspace.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LLM tree")
        self.assertContains(response, "graph-payload")
        self.assertContains(response, "A branching chat workspace for exploring conversations as a graph.")
        self.assertContains(response, "Zoom")
        self.assertContains(response, "Fit view")
        self.assertContains(response, "Shortcuts")
        self.assertContains(response, "Workspace Shortcuts")
        self.assertContains(response, "Create Workspace")
        self.assertContains(response, "Workspaces")
        self.assertContains(response, "No root yet.")
        self.assertContains(response, "Search")
        self.assertContains(response, "Add child node")
        self.assertContains(response, "Delete workspace")
        self.assertContains(response, "Rename node")
        self.assertContains(response, "Delete node")
        self.assertContains(response, "Workspace Memory")
        self.assertContains(response, WORKSPACE_MEMORY_FALLBACK_CONTENT)
        self.assertNotContains(response, "Research lane")
        self.assertNotContains(response, "Model comparison")
        self.assertNotContains(response, "Branch review")
        self.assertNotContains(response, "Drag nodes. Drag canvas to pan.")
        self.assertNotContains(response, "Minimap")
        self.assertNotContains(response, "Node Detail")
        self.assertNotContains(response, "Open chat")
        self.assertNotContains(response, "Recent Activity")
        self.assertNotContains(response, "Branch / Version Source")

    def test_workspace_node_chat_page_renders_transcript_and_composer(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Root node",
            summary="Discuss the launch plan.",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.USER,
            content="Plan the product launch.",
            order_index=0,
        )
        NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.ASSISTANT,
            content="Here is a staged launch outline.",
            order_index=1,
        )

        response = self.client.get(reverse("workspace_node_chat", args=[workspace.slug, node.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Back to graph")
        self.assertContains(response, "Send")
        self.assertContains(response, "Root node")
        self.assertContains(response, "Main · Openai / gpt-4.1-mini")
        self.assertContains(response, "Jump to latest")
        self.assertContains(response, "想問就問")
        self.assertContains(response, "Workspace memory")
        self.assertNotContains(response, "Open memory")
        self.assertNotContains(response, "The model prepares a first version. You edit it before saving.")

    @patch("tree_ui.views.ensure_workspace_memory")
    def test_workspace_page_renders_saved_workspace_memory_without_regeneration(self, mock_ensure_workspace_memory):
        workspace = Workspace.objects.create(name="Main", slug="main")
        memory = ConversationMemory.objects.create(
            workspace=workspace,
            scope=ConversationMemory.Scope.WORKSPACE,
            memory_type=ConversationMemory.MemoryType.SUMMARY,
            source=ConversationMemory.Source.EXTRACTED,
            title="Workspace memory",
            content="This workspace is focused on C++ learning progress.",
            is_pinned=True,
        )
        mock_ensure_workspace_memory.return_value = memory

        response = self.client.get(reverse("workspace_graph", args=[workspace.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This workspace is focused on C++ learning progress.")
        self.assertContains(response, "Workspace Memory")
        mock_ensure_workspace_memory.assert_called_once_with(workspace)

    @patch("tree_ui.services.memory_drafting.generate_text")
    def test_workspace_page_auto_creates_workspace_memory_when_missing(self, mock_generate_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Root node",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.USER,
            content="We are studying C++ basics in this workspace.",
            order_index=0,
        )
        mock_generate_text.return_value = GenerationResult(
            text='{"title":"Workspace memory","content":"This workspace is focused on learning C++ basics."}',
            provider="openai",
            model_name="gpt-4.1-mini",
        )

        response = self.client.get(reverse("workspace_graph", args=[workspace.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This workspace is focused on learning C++ basics.")
        memory = ConversationMemory.objects.get(
            workspace=workspace,
            scope=ConversationMemory.Scope.WORKSPACE,
            title="Workspace memory",
        )
        self.assertEqual(memory.content, "This workspace is focused on learning C++ basics.")

    def test_workspace_node_memory_page_redirects_to_workspace_memory_panel(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Root node",
            summary="Discuss the launch plan.",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )

        response = self.client.get(reverse("workspace_node_memory", args=[workspace.slug, node.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"{reverse('workspace_graph', args=[workspace.slug])}#workspace-memory-panel")

    def test_non_leaf_node_chat_page_warns_that_sending_creates_new_child(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Parent node",
            summary="Discuss the launch plan.",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        ConversationNode.objects.create(
            workspace=workspace,
            parent=node,
            title="Existing child",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )

        response = self.client.get(reverse("workspace_node_chat", args=[workspace.slug, node.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "History node")
        self.assertContains(response, "Continue in new child")
        self.assertContains(
            response,
            "This node already has child branches. Your message will be written into a newly created child branch, not this historical node.",
        )

    def test_can_create_workspace_via_api(self):
        response = self.client.post(
            reverse("create_workspace"),
            data=json.dumps({"name": "Research Space"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Workspace.objects.count(), 1)
        workspace = Workspace.objects.get()
        self.assertEqual(workspace.name, "Research Space")
        self.assertEqual(workspace.slug, "research-space")
        self.assertIn(reverse("workspace_graph", args=[workspace.slug]), response.json()["redirect_url"])

    def test_can_delete_workspace_via_api_and_redirect(self):
        first = Workspace.objects.create(name="Main", slug="main")
        second = Workspace.objects.create(name="Alt", slug="alt")

        response = self.client.post(
            reverse("delete_workspace", args=[first.slug]),
            data=json.dumps({"confirm": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Workspace.objects.filter(pk=first.pk).exists())
        self.assertTrue(Workspace.objects.filter(pk=second.pk).exists())
        self.assertEqual(response.json()["redirect_url"], reverse("workspace_graph", args=[second.slug]))

    def test_delete_workspace_requires_confirmation(self):
        workspace = Workspace.objects.create(name="Main", slug="main")

        response = self.client.post(
            reverse("delete_workspace", args=[workspace.slug]),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(Workspace.objects.filter(pk=workspace.pk).exists())

    def test_can_create_root_node_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")

        response = self.client.post(
            reverse("create_workspace_node", args=[workspace.slug]),
            data=json.dumps(
                {
                    "title": "Root node",
                    "provider": "openai",
                    "model_name": "gpt-4.1-mini",
                    "system_prompt": "Answer tersely.",
                    "temperature": 0.3,
                    "top_p": 0.8,
                    "max_output_tokens": 256,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ConversationNode.objects.count(), 1)
        node = ConversationNode.objects.get()
        self.assertIsNone(node.parent)
        self.assertEqual(node.provider, ConversationNode.Provider.OPENAI)
        self.assertEqual(node.system_prompt, "Answer tersely.")
        self.assertEqual(node.temperature, 0.3)
        self.assertEqual(node.top_p, 0.8)
        self.assertEqual(node.max_output_tokens, 256)
        self.assertEqual(NodeMessage.objects.filter(node=node).count(), 0)
        self.assertEqual(node.summary, "Open this node to start the conversation.")
        self.assertEqual(response.json()["node"]["system_prompt"], "Answer tersely.")

    def test_can_create_multiple_root_nodes_in_one_workspace(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        first = self.client.post(
            reverse("create_workspace_node", args=[workspace.slug]),
            data=json.dumps(
                {
                    "title": "Conversation A",
                    "provider": "openai",
                    "model_name": "gpt-4.1-mini",
                }
            ),
            content_type="application/json",
        )
        second = self.client.post(
            reverse("create_workspace_node", args=[workspace.slug]),
            data=json.dumps(
                {
                    "title": "Conversation B",
                    "provider": "gemini",
                    "model_name": "gemini-2.5-flash",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(ConversationNode.objects.filter(workspace=workspace).count(), 2)
        self.assertEqual(
            ConversationNode.objects.filter(workspace=workspace, parent__isnull=True).count(),
            2,
        )

    def test_can_create_child_node_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        parent = ConversationNode.objects.create(
            workspace=workspace,
            title="Root node",
            summary="Root",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
            position_x=80,
            position_y=120,
        )

        response = self.client.post(
            reverse("create_workspace_node", args=[workspace.slug]),
            data=json.dumps(
                {
                    "title": "Branch node",
                    "provider": "gemini",
                    "model_name": "gemini-2.5-flash",
                    "parent_id": parent.id,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        child = ConversationNode.objects.exclude(pk=parent.pk).get()
        self.assertEqual(child.parent, parent)
        self.assertEqual(child.provider, ConversationNode.Provider.GEMINI)
        self.assertEqual(child.position_x, parent.position_x + 340)

    def test_create_node_rejects_invalid_generation_config(self):
        workspace = Workspace.objects.create(name="Main", slug="main")

        response = self.client.post(
            reverse("create_workspace_node", args=[workspace.slug]),
            data=json.dumps(
                {
                    "title": "Invalid config node",
                    "provider": "openai",
                    "model_name": "gpt-4.1-mini",
                    "temperature": 3,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Temperature must be between 0.0 and 2.0.", response.content.decode("utf-8"))

    def test_can_update_node_title_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Old title",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )

        response = self.client.post(
            reverse("update_node_title", args=[workspace.slug, node.id]),
            data=json.dumps({"title": "New title"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        node.refresh_from_db()
        self.assertEqual(node.title, "New title")
        self.assertEqual(response.json()["node"]["title"], "New title")

    def test_blank_node_title_is_normalized_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Old title",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )

        response = self.client.post(
            reverse("update_node_title", args=[workspace.slug, node.id]),
            data=json.dumps({"title": "   "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        node.refresh_from_db()
        self.assertEqual(node.title, "Untitled conversation")

    def test_can_delete_node_subtree_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        root = ConversationNode.objects.create(
            workspace=workspace,
            title="Root",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        branch = ConversationNode.objects.create(
            workspace=workspace,
            parent=root,
            title="Branch",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        grandchild = ConversationNode.objects.create(
            workspace=workspace,
            parent=branch,
            title="Grandchild",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        sibling = ConversationNode.objects.create(
            workspace=workspace,
            parent=root,
            title="Sibling",
            summary="",
            provider=ConversationNode.Provider.GEMINI,
            model_name="gemini-2.5-flash",
        )

        response = self.client.post(
            reverse("delete_workspace_node", args=[workspace.slug, branch.id]),
            data=json.dumps({"confirm": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ConversationNode.objects.filter(pk=branch.pk).exists())
        self.assertFalse(ConversationNode.objects.filter(pk=grandchild.pk).exists())
        self.assertTrue(ConversationNode.objects.filter(pk=root.pk).exists())
        self.assertTrue(ConversationNode.objects.filter(pk=sibling.pk).exists())
        self.assertEqual(set(response.json()["deleted_node_ids"]), {branch.id, grandchild.id})
        self.assertEqual(response.json()["deleted_count"], 2)

    def test_delete_node_requires_confirmation(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Root",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )

        response = self.client.post(
            reverse("delete_workspace_node", args=[workspace.slug, node.id]),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(ConversationNode.objects.filter(pk=node.pk).exists())

    def test_can_create_edited_variant_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        original = ConversationNode.objects.create(
            workspace=workspace,
            title="Original node",
            summary="Original",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
            position_x=120,
            position_y=200,
        )
        NodeMessage.objects.create(
            node=original,
            role=NodeMessage.Role.USER,
            content="Original prompt",
            order_index=0,
        )
        NodeMessage.objects.create(
            node=original,
            role=NodeMessage.Role.ASSISTANT,
            content="Original answer",
            order_index=1,
        )

        response = self.client.post(
            reverse("create_edited_node_variant", args=[workspace.slug, original.id]),
            data=json.dumps(
                {
                    "title": "Original node (Edited)",
                    "messages": [
                        {"role": "user", "content": "Edited prompt", "order_index": 0},
                        {"role": "assistant", "content": "Edited answer", "order_index": 1},
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        edited = ConversationNode.objects.exclude(pk=original.pk).get()
        self.assertEqual(edited.edited_from, original)
        self.assertEqual(edited.parent, original.parent)
        self.assertEqual(edited.messages.first().content, "Edited prompt")
        self.assertEqual(original.messages.first().content, "Original prompt")
        self.assertIn(
            reverse("workspace_node_chat", args=[workspace.slug, edited.id]),
            response.json()["node_chat_url"],
        )

    def test_manual_branch_memory_creation_is_disabled_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Memory node",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        message = NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.ASSISTANT,
            content="Remember that the demo should stay under 3 minutes.",
            order_index=0,
        )

        response = self.client.post(
            reverse("create_workspace_memory", args=[workspace.slug]),
            data=json.dumps(
                {
                    "context_node_id": node.id,
                    "scope": ConversationMemory.Scope.BRANCH,
                    "memory_type": ConversationMemory.MemoryType.SUMMARY,
                    "title": "Demo limit",
                    "branch_anchor_id": node.id,
                    "source_node_id": node.id,
                    "source_message_id": message.id,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(ConversationMemory.objects.count(), 0)
        self.assertIn("Workspace memory is automatic and read only.", response.content.decode("utf-8"))

    def test_workspace_memory_cannot_be_created_manually_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Memory node",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )

        response = self.client.post(
            reverse("create_workspace_memory", args=[workspace.slug]),
            data=json.dumps(
                {
                    "context_node_id": node.id,
                    "scope": ConversationMemory.Scope.WORKSPACE,
                    "memory_type": ConversationMemory.MemoryType.PREFERENCE,
                    "title": "Manual workspace edit",
                    "content": "Should be rejected.",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Workspace memory is automatic and read only.", response.content.decode("utf-8"))

    @patch("tree_ui.views.generate_memory_draft_for_node")
    def test_can_generate_memory_draft_via_api(self, mock_generate_memory_draft_for_node):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Memory node",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        mock_generate_memory_draft_for_node.return_value = {
            "scope": "branch",
            "memory_type": "summary",
            "title": "Draft title",
            "content": "Draft content",
            "used_fallback": False,
        }

        response = self.client.post(
            reverse("generate_node_memory_draft", args=[workspace.slug, node.id]),
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["draft"]["title"], "Draft title")
        mock_generate_memory_draft_for_node.assert_called_once()

    def test_can_update_node_position_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Draggable node",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
            position_x=80,
            position_y=120,
        )

        response = self.client.post(
            reverse("update_node_position", args=[workspace.slug, node.id]),
            data=json.dumps(
                {
                    "position_x": 420,
                    "position_y": 260,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        node.refresh_from_db()
        self.assertEqual(node.position_x, 420)
        self.assertEqual(node.position_y, 260)
        self.assertEqual(response.json()["node"]["position"], {"x": 420, "y": 260})

    @override_settings(LLM_STREAM_CHUNK_DELAY_SECONDS=0)
    @patch("tree_ui.services.node_creation.stream_text")
    def test_can_stream_node_message_append_via_api(self, mock_stream_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Root node",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
            system_prompt="Stay concise.",
            temperature=0.4,
            top_p=0.9,
            max_output_tokens=300,
        )
        mock_stream_text.return_value = iter(["Streamed ", "reply"])

        response = self.client.post(
            reverse("stream_node_message", args=[workspace.slug, node.id]),
            data=json.dumps(
                {
                    "prompt": "Stream the first reply.",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        streamed = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("event: preview", streamed)
        self.assertIn("event: delta", streamed)
        self.assertIn("event: node", streamed)
        self.assertEqual(ConversationNode.objects.count(), 1)
        self.assertEqual(NodeMessage.objects.filter(node=node).count(), 2)
        self.assertEqual(
            NodeMessage.objects.get(node=node, role=NodeMessage.Role.ASSISTANT).content,
            "Streamed reply",
        )
        self.assertEqual(mock_stream_text.call_args.kwargs["temperature"], 0.4)
        self.assertEqual(mock_stream_text.call_args.kwargs["top_p"], 0.9)
        self.assertEqual(mock_stream_text.call_args.kwargs["max_output_tokens"], 300)
        self.assertIn("Stay concise.", mock_stream_text.call_args.kwargs["system_instruction"])

    @override_settings(LLM_STREAM_CHUNK_DELAY_SECONDS=0)
    @patch("tree_ui.services.node_creation.stream_text")
    def test_streaming_from_non_leaf_node_creates_new_child_branch(self, mock_stream_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Root node",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        ConversationNode.objects.create(
            workspace=workspace,
            parent=node,
            title="Existing child",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        mock_stream_text.return_value = iter(["Branch ", "reply"])

        response = self.client.post(
            reverse("stream_node_message", args=[workspace.slug, node.id]),
            data=json.dumps(
                {
                    "prompt": "Continue from the historical node.",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        streamed = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn('"created_new_branch": true', streamed)
        self.assertEqual(ConversationNode.objects.filter(workspace=workspace).count(), 3)
        self.assertEqual(NodeMessage.objects.filter(node=node).count(), 0)
        new_child = ConversationNode.objects.filter(workspace=workspace, parent=node).latest("created_at")
        self.assertEqual(NodeMessage.objects.filter(node=new_child).count(), 2)
        self.assertEqual(
            NodeMessage.objects.get(node=new_child, role=NodeMessage.Role.ASSISTANT).content,
            "Branch reply",
        )

    def test_branch_local_context_uses_selected_lineage_only(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        root = ConversationNode.objects.create(
            workspace=workspace,
            title="Root",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        NodeMessage.objects.create(
            node=root,
            role=NodeMessage.Role.USER,
            content="Root prompt",
            order_index=0,
        )
        NodeMessage.objects.create(
            node=root,
            role=NodeMessage.Role.ASSISTANT,
            content="Root answer",
            order_index=1,
        )
        selected_branch = ConversationNode.objects.create(
            workspace=workspace,
            parent=root,
            title="Branch A",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        NodeMessage.objects.create(
            node=selected_branch,
            role=NodeMessage.Role.USER,
            content="Branch A prompt",
            order_index=0,
        )
        sibling_branch = ConversationNode.objects.create(
            workspace=workspace,
            parent=root,
            title="Branch B",
            summary="",
            provider=ConversationNode.Provider.GEMINI,
            model_name="gemini-2.5-flash",
        )
        NodeMessage.objects.create(
            node=sibling_branch,
            role=NodeMessage.Role.USER,
            content="Sibling prompt",
            order_index=0,
        )

        messages = build_generation_messages(
            parent=selected_branch,
            prompt="Continue selected branch",
        )

        self.assertEqual(
            [message.content for message in messages],
            [
                "Root prompt",
                "Root answer",
                "Branch A prompt",
                "Continue selected branch",
            ],
        )

    @patch("tree_ui.services.node_creation.refresh_workspace_preference_memory")
    @patch("tree_ui.services.node_creation.generate_text")
    def test_append_messages_to_node_uses_provider_result_when_available(self, mock_generate_text, mock_refresh_workspace_preference_memory):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Main conversation",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
            system_prompt="Always answer as a bullet list.",
            temperature=0.2,
            top_p=0.7,
            max_output_tokens=120,
        )
        mock_generate_text.return_value = GenerationResult(
            text="Real provider output",
            provider="openai",
            model_name="gpt-4.1-mini",
        )

        updated_node = append_messages_to_node(
            node=node,
            prompt="Summarize the plan",
        )

        self.assertEqual(
            updated_node.messages.get(role=NodeMessage.Role.ASSISTANT).content,
            "Real provider output",
        )
        mock_generate_text.assert_called_once()
        self.assertIn(
            "Always answer as a bullet list.",
            mock_generate_text.call_args.kwargs["system_instruction"],
        )
        self.assertEqual(mock_generate_text.call_args.kwargs["temperature"], 0.2)
        self.assertEqual(mock_generate_text.call_args.kwargs["top_p"], 0.7)
        self.assertEqual(mock_generate_text.call_args.kwargs["max_output_tokens"], 120)
        mock_refresh_workspace_preference_memory.assert_called_once()

    @patch("tree_ui.services.providers.registry._get_provider")
    def test_legacy_gemini_model_alias_is_upgraded_for_generation(self, mock_get_provider):
        provider = Mock()
        provider.generate.return_value = GenerationResult(
            text="Aliased provider output",
            provider="gemini",
            model_name="gemini-2.5-flash",
        )
        mock_get_provider.return_value = provider

        result = registry_generate_text(
            provider_name=ConversationNode.Provider.GEMINI,
            model_name="gemini-2.0-flash",
            messages=[],
            system_instruction="Test instruction",
        )

        self.assertEqual(result.model_name, "gemini-2.5-flash")
        self.assertEqual(provider.generate.call_args.kwargs["model_name"], "gemini-2.5-flash")

    def test_create_edited_variant_preserves_original_node(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        original = ConversationNode.objects.create(
            workspace=workspace,
            title="Original",
            summary="Original",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
            system_prompt="Retain technical depth.",
            temperature=0.5,
            top_p=0.95,
            max_output_tokens=512,
        )
        NodeMessage.objects.create(
            node=original,
            role=NodeMessage.Role.USER,
            content="Original prompt",
            order_index=0,
        )

        edited = create_edited_variant(
            original_node=original,
            title="Original (Edited)",
            messages=[
                {
                    "role": NodeMessage.Role.USER,
                    "content": "Edited prompt",
                    "order_index": 0,
                }
            ],
        )

        self.assertEqual(edited.edited_from, original)
        self.assertEqual(original.messages.get().content, "Original prompt")
        self.assertEqual(edited.messages.get().content, "Edited prompt")
        self.assertEqual(edited.system_prompt, "Retain technical depth.")
        self.assertEqual(edited.temperature, 0.5)
        self.assertEqual(edited.top_p, 0.95)
        self.assertEqual(edited.max_output_tokens, 512)


class MemoryFoundationTests(TestCase):
    def test_can_create_workspace_memory(self):
        workspace = Workspace.objects.create(name="Main", slug="main")

        memory = create_memory(
            workspace=workspace,
            scope=ConversationMemory.Scope.WORKSPACE,
            memory_type=ConversationMemory.MemoryType.FACT,
            title="Company preference",
            content="Always answer in Traditional Chinese.",
            is_pinned=True,
        )

        self.assertEqual(memory.workspace, workspace)
        self.assertEqual(memory.scope, ConversationMemory.Scope.WORKSPACE)
        self.assertIsNone(memory.branch_anchor)
        self.assertTrue(memory.is_pinned)

    def test_branch_memory_requires_anchor(self):
        workspace = Workspace.objects.create(name="Main", slug="main")

        with self.assertRaisesMessage(ValueError, "Branch memories require a branch anchor node."):
            create_memory(
                workspace=workspace,
                scope=ConversationMemory.Scope.BRANCH,
                memory_type=ConversationMemory.MemoryType.SUMMARY,
                content="Branch-only plan.",
            )

    def test_retrieval_keeps_workspace_and_selected_branch_scope_separate_from_siblings(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        root = ConversationNode.objects.create(
            workspace=workspace,
            title="Root",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        selected_branch = ConversationNode.objects.create(
            workspace=workspace,
            parent=root,
            title="Selected branch",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        sibling_branch = ConversationNode.objects.create(
            workspace=workspace,
            parent=root,
            title="Sibling branch",
            summary="",
            provider=ConversationNode.Provider.GEMINI,
            model_name="gemini-2.5-flash",
        )

        workspace_memory = create_memory(
            workspace=workspace,
            scope=ConversationMemory.Scope.WORKSPACE,
            memory_type=ConversationMemory.MemoryType.SUMMARY,
            title="Workspace memory",
            source=ConversationMemory.Source.EXTRACTED,
            content="This workspace is evaluating launch risks with concise updates.",
            is_pinned=True,
        )
        branch_memory = create_memory(
            workspace=workspace,
            scope=ConversationMemory.Scope.BRANCH,
            memory_type=ConversationMemory.MemoryType.SUMMARY,
            title="Branch summary",
            content="This branch is evaluating launch risks.",
            branch_anchor=selected_branch,
        )
        create_memory(
            workspace=workspace,
            scope=ConversationMemory.Scope.BRANCH,
            memory_type=ConversationMemory.MemoryType.TASK,
            title="Sibling task",
            content="Only relevant to the sibling branch.",
            branch_anchor=sibling_branch,
        )

        retrieved = retrieve_memories_for_generation(
            workspace=workspace,
            parent=selected_branch,
        )

        self.assertEqual(
            {(item.id, item.scope) for item in retrieved},
            {
                (workspace_memory.id, ConversationMemory.Scope.WORKSPACE),
            },
        )
        self.assertNotIn(branch_memory.id, {item.id for item in retrieved})

    def test_format_memories_for_prompt_produces_explicit_memory_block(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        create_memory(
            workspace=workspace,
            scope=ConversationMemory.Scope.WORKSPACE,
            memory_type=ConversationMemory.MemoryType.ARTIFACT,
            title="Canonical outline",
            content="The final deliverable needs a 3-minute demo.",
        )

        retrieved = retrieve_memories_for_generation(workspace=workspace, parent=None)
        formatted = format_memories_for_prompt(retrieved)

        self.assertIn("Retrieved long-term memory:", formatted)
        self.assertIn("[workspace/artifact] Canonical outline:", formatted)
        self.assertIn("The final deliverable needs a 3-minute demo.", formatted)

    @patch("tree_ui.services.memory_drafting.generate_text")
    def test_generate_memory_draft_for_node_returns_structured_payload(self, mock_generate_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Draft source",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.USER,
            content="Remember that the user wants concise launch risks.",
            order_index=0,
        )
        mock_generate_text.return_value = GenerationResult(
            text='{"scope":"branch","memory_type":"summary","title":"Launch risks","content":"This branch focuses on concise launch risk analysis."}',
            provider="openai",
            model_name="gpt-4.1-mini",
        )

        draft = generate_memory_draft_for_node(node)

        self.assertEqual(draft["scope"], "branch")
        self.assertEqual(draft["memory_type"], "summary")
        self.assertEqual(draft["title"], "Launch risks")
        self.assertIn("concise launch risk analysis", draft["content"])

    @patch("tree_ui.services.memory_drafting.generate_text")
    def test_generate_memory_draft_normalizes_trailing_ellipsis(self, mock_generate_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Draft source",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        mock_generate_text.return_value = GenerationResult(
            text='{"scope":"branch","memory_type":"summary","title":"C++ basics","content":"Learner already understands that C++ extends C and includes object-oriented programming..."}',
            provider="openai",
            model_name="gpt-4.1-mini",
        )

        draft = generate_memory_draft_for_node(node)

        self.assertFalse(draft["content"].endswith("..."))
        self.assertFalse(draft["content"].endswith("…"))

    @patch("tree_ui.services.memory_drafting.generate_text", side_effect=ProviderError("provider unavailable"))
    def test_refresh_workspace_preference_memory_uses_local_summary_when_generation_fails(self, _mock_generate_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="C basics",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.USER,
            content="教我 C 語言的基本概念",
            order_index=0,
        )

        memory = refresh_workspace_preference_memory(node)

        self.assertEqual(memory.title, "Workspace memory")
        self.assertNotEqual(memory.content, WORKSPACE_MEMORY_FALLBACK_CONTENT)
        self.assertIn("C basics", memory.content)

    @patch("tree_ui.services.memory_drafting.generate_text")
    def test_refresh_workspace_preference_memory_updates_read_only_profile(self, mock_generate_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Draft source",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.USER,
            content="I prefer concise answers and Traditional Chinese.",
            order_index=0,
        )
        mock_generate_text.return_value = GenerationResult(
            text='{"title":"Workspace memory","content":"This workspace is teaching C++ basics and the learner prefers concise Traditional Chinese explanations."}',
            provider="openai",
            model_name="gpt-4.1-mini",
        )

        memory = refresh_workspace_preference_memory(node)

        self.assertEqual(memory.scope, ConversationMemory.Scope.WORKSPACE)
        self.assertEqual(memory.source, ConversationMemory.Source.EXTRACTED)
        self.assertEqual(memory.memory_type, ConversationMemory.MemoryType.SUMMARY)
        self.assertEqual(memory.title, "Workspace memory")
        self.assertTrue(memory.is_pinned)
        self.assertIn("Traditional Chinese", memory.content)

    def test_ensure_workspace_memory_creates_fallback_record_for_empty_workspace(self):
        workspace = Workspace.objects.create(name="Main", slug="main")

        memory = ensure_workspace_memory(workspace)

        self.assertEqual(memory.workspace, workspace)
        self.assertEqual(memory.title, "Workspace memory")
        self.assertEqual(memory.content, WORKSPACE_MEMORY_FALLBACK_CONTENT)
        self.assertEqual(memory.scope, ConversationMemory.Scope.WORKSPACE)
        self.assertEqual(memory.memory_type, ConversationMemory.MemoryType.SUMMARY)

    @patch("tree_ui.services.memory_drafting.generate_text")
    def test_ensure_workspace_memory_replaces_fallback_when_workspace_has_conversation(self, mock_generate_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        ConversationMemory.objects.create(
            workspace=workspace,
            scope=ConversationMemory.Scope.WORKSPACE,
            source=ConversationMemory.Source.EXTRACTED,
            memory_type=ConversationMemory.MemoryType.SUMMARY,
            title="Workspace memory",
            content=WORKSPACE_MEMORY_FALLBACK_CONTENT,
            is_pinned=True,
        )
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Root node",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        NodeMessage.objects.create(
            node=node,
            role=NodeMessage.Role.USER,
            content="This workspace is about C language learning.",
            order_index=0,
        )
        mock_generate_text.return_value = GenerationResult(
            text='{"title":"Workspace memory","content":"This workspace is focused on C language learning."}',
            provider="openai",
            model_name="gpt-4.1-mini",
        )

        memory = ensure_workspace_memory(workspace)

        self.assertEqual(memory.content, "This workspace is focused on C language learning.")
        self.assertEqual(
            ConversationMemory.objects.filter(workspace=workspace, title="Workspace memory").count(),
            1,
        )

    @patch("tree_ui.services.node_creation.generate_text")
    def test_append_messages_to_node_includes_retrieved_memory_in_system_instruction(self, mock_generate_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Memory-aware node",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
            system_prompt="Stay concise.",
        )
        create_memory(
            workspace=workspace,
            scope=ConversationMemory.Scope.WORKSPACE,
            memory_type=ConversationMemory.MemoryType.SUMMARY,
            source=ConversationMemory.Source.EXTRACTED,
            title="Workspace memory",
            content="This workspace should keep answers in Traditional Chinese.",
        )
        mock_generate_text.return_value = GenerationResult(
            text="Provider output",
            provider="openai",
            model_name="gpt-4.1-mini",
        )

        append_messages_to_node(
            node=node,
            prompt="Summarize the next step.",
        )

        system_instruction = mock_generate_text.call_args.kwargs["system_instruction"]
        self.assertIn("Long-term memory retrieved separately from the current branch transcript:", system_instruction)
        self.assertIn("Retrieved long-term memory:", system_instruction)
        self.assertIn("Traditional Chinese", system_instruction)
