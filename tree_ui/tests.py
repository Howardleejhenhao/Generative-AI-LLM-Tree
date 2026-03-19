import json
from unittest.mock import patch

from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from tree_ui.models import ConversationNode, NodeMessage, Workspace
from tree_ui.services.context_builder import build_generation_messages
from tree_ui.services.node_creation import append_messages_to_node
from tree_ui.services.node_editing import create_edited_variant
from tree_ui.services.providers.base import GenerationResult


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
        self.assertContains(response, "Conversation DAG")
        self.assertContains(response, "graph-payload")
        self.assertContains(response, "Use the graph as the main workspace, not a side panel.")
        self.assertContains(
            response,
            "Drag nodes to rearrange the layout. Drag the background to pan. Use the zoom controls for larger trees.",
        )
        self.assertContains(response, "Workspace Zoom")
        self.assertContains(response, "Fit view")
        self.assertContains(response, "Minimap")
        self.assertContains(response, "Hide inspector")
        self.assertContains(response, "Create Workspace")
        self.assertContains(response, "Pick the graph you want to work in.")
        self.assertContains(response, "Live canvas summary")
        self.assertContains(response, "Selected focus")

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
        self.assertContains(response, "Lineage")
        self.assertContains(response, "Child Branches")

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

    def test_can_create_root_node_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")

        response = self.client.post(
            reverse("create_workspace_node", args=[workspace.slug]),
            data=json.dumps(
                {
                    "title": "Root node",
                    "provider": "openai",
                    "model_name": "gpt-4.1-mini",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(ConversationNode.objects.count(), 1)
        node = ConversationNode.objects.get()
        self.assertIsNone(node.parent)
        self.assertEqual(node.provider, ConversationNode.Provider.OPENAI)
        self.assertEqual(NodeMessage.objects.filter(node=node).count(), 0)
        self.assertEqual(node.summary, "Open this node to start the conversation.")

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
                    "model_name": "gemini-2.0-flash",
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
                    "model_name": "gemini-2.0-flash",
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
    def test_can_stream_node_message_append_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Root node",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )

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
            model_name="gemini-2.0-flash",
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

    @patch("tree_ui.services.node_creation.generate_text")
    def test_append_messages_to_node_uses_provider_result_when_available(self, mock_generate_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Main conversation",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
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

    def test_create_edited_variant_preserves_original_node(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        original = ConversationNode.objects.create(
            workspace=workspace,
            title="Original",
            summary="Original",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
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
