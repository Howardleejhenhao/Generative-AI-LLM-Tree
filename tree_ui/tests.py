import json
from unittest.mock import patch

from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from tree_ui.models import ConversationNode, NodeMessage, Workspace
from tree_ui.services.context_builder import build_generation_messages
from tree_ui.services.node_creation import create_node
from tree_ui.services.providers.base import GenerationResult


class WorkspaceGraphViewTests(TestCase):
    def test_homepage_renders_graph_shell(self):
        response = self.client.get(reverse("workspace_graph"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Conversation DAG")
        self.assertContains(response, "graph-payload")
        self.assertContains(response, "Drag the canvas to pan in any direction.")
        self.assertEqual(Workspace.objects.count(), 1)

    def test_can_create_root_node_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")

        response = self.client.post(
            reverse("create_workspace_node", args=[workspace.slug]),
            data=json.dumps(
                {
                    "title": "Root node",
                    "prompt": "Plan the first branch.",
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
        self.assertEqual(NodeMessage.objects.filter(node=node).count(), 2)
        self.assertIn("Fallback openai response", node.messages.get(role="assistant").content)

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
                    "prompt": "Continue from the root.",
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

    @override_settings(LLM_STREAM_CHUNK_DELAY_SECONDS=0)
    def test_can_stream_node_creation_via_api(self):
        workspace = Workspace.objects.create(name="Main", slug="main")

        response = self.client.post(
            reverse("stream_workspace_node", args=[workspace.slug]),
            data=json.dumps(
                {
                    "title": "Streaming root",
                    "prompt": "Stream the first branch.",
                    "provider": "openai",
                    "model_name": "gpt-4.1-mini",
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
    def test_create_node_uses_provider_result_when_available(self, mock_generate_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        mock_generate_text.return_value = GenerationResult(
            text="Real provider output",
            provider="openai",
            model_name="gpt-4.1-mini",
        )

        node = create_node(
            workspace=workspace,
            parent=None,
            title="",
            prompt="Summarize the plan",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )

        self.assertEqual(
            node.messages.get(role=NodeMessage.Role.ASSISTANT).content,
            "Real provider output",
        )
        mock_generate_text.assert_called_once()
