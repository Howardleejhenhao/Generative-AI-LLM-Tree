import json
import tempfile
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from tree_ui.models import ConversationMemory, ConversationNode, NodeAttachment, NodeMessage, ToolInvocation, Workspace, MCPSource
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
from tree_ui.services.providers.base import GenerationResult, ProviderDelta, ToolCallDelta
from tree_ui.services.providers.registry import generate_text as registry_generate_text
from tree_ui.services.router import route_model


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
        self.assertContains(response, "Read only")
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
        self.assertContains(response, "Main")
        self.assertContains(response, "Openai")
        self.assertContains(response, "gpt-4.1-mini")
        self.assertContains(response, "Jump to latest")
        self.assertContains(response, "想問就問")
        self.assertContains(response, "Workspace memory")
        self.assertContains(response, "Edit as variant")
        self.assertContains(response, "Create edited variant")
        self.assertContains(response, "Edit and branch")
        self.assertContains(response, 'id="chat-image-lightbox"')
        self.assertContains(response, 'accept="image/*,application/pdf"')
        self.assertContains(response, "Enter sends. Shift + Enter adds a new line.")
        self.assertNotContains(response, "Open memory")
        self.assertNotContains(response, "The model prepares a first version. You edit it before saving.")

    def test_workspace_node_chat_page_renders_node_attachments(self):
        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                workspace = Workspace.objects.create(name="Main", slug="main")
                node = ConversationNode.objects.create(
                    workspace=workspace,
                    title="Image node",
                    summary="Discuss the attached screenshot.",
                    provider=ConversationNode.Provider.OPENAI,
                    model_name="gpt-4.1-mini",
                )
                NodeAttachment.objects.create(
                    node=node,
                    file=SimpleUploadedFile("diagram.png", b"fake-image-bytes", content_type="image/png"),
                    original_name="diagram.png",
                    content_type="image/png",
                    size_bytes=16,
                )

                response = self.client.get(reverse("workspace_node_chat", args=[workspace.slug, node.id]))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="chat-image-input"')
                self.assertNotContains(response, "Attached to this node")
                self.assertContains(response, "multiple hidden")

    @patch("tree_ui.views.ensure_workspace_memory")
    def test_workspace_page_renders_saved_workspace_memory_without_regeneration(self, mock_ensure_workspace_memory):
        workspace = Workspace.objects.create(name="Main", slug="main")
        source_node = ConversationNode.objects.create(
            workspace=workspace,
            title="Root node",
            summary="",
            provider=ConversationNode.Provider.OPENAI,
            model_name="gpt-4.1-mini",
        )
        memory = ConversationMemory.objects.create(
            workspace=workspace,
            scope=ConversationMemory.Scope.WORKSPACE,
            memory_type=ConversationMemory.MemoryType.SUMMARY,
            source=ConversationMemory.Source.EXTRACTED,
            title="Workspace memory",
            content="This workspace is focused on C++ learning progress.",
            source_node=source_node,
            is_pinned=True,
        )
        mock_ensure_workspace_memory.return_value = memory

        response = self.client.get(reverse("workspace_graph", args=[workspace.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This workspace is focused on C++ learning progress.")
        self.assertContains(response, "Workspace Memory")
        self.assertContains(response, "Last refreshed from")
        self.assertContains(response, "Root node")
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
        self.assertContains(response, "Edit as variant")
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
        self.assertIn("Manual long-term memory editing has been removed.", response.content.decode("utf-8"))

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
        self.assertIn("Manual long-term memory editing has been removed.", response.content.decode("utf-8"))

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
        mock_stream_text.return_value = iter([ProviderDelta(text="Streamed "), ProviderDelta(text="reply")])

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
    def test_can_stream_node_message_with_image_attachment_via_api(self, mock_stream_text):
        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                workspace = Workspace.objects.create(name="Main", slug="main")
                node = ConversationNode.objects.create(
                    workspace=workspace,
                    title="Vision node",
                    summary="",
                    provider=ConversationNode.Provider.OPENAI,
                    model_name="gpt-4.1-mini",
                )
                mock_stream_text.return_value = iter([ProviderDelta(text="Vision "), ProviderDelta(text="reply")])

                response = self.client.post(
                    reverse("stream_node_message", args=[workspace.slug, node.id]),
                    data={
                        "prompt": "Describe this image.",
                        "images": [
                            SimpleUploadedFile(
                                "photo.png",
                                b"fake-image-bytes",
                                content_type="image/png",
                            )
                        ],
                    },
                )

                self.assertEqual(response.status_code, 200)
                streamed = b"".join(response.streaming_content).decode("utf-8")
                self.assertIn('"attachment_count": 1', streamed)
                self.assertEqual(NodeAttachment.objects.filter(node=node).count(), 1)
                user_message = NodeMessage.objects.get(node=node, role=NodeMessage.Role.USER)
                self.assertEqual(user_message.content, "Describe this image.")
                self.assertEqual(user_message.attachments.count(), 1)
                self.assertEqual(mock_stream_text.call_args.kwargs["messages"][-1].attachments[0].name, "photo.png")
                self.assertEqual(mock_stream_text.call_args.kwargs["messages"][-1].attachments[0].content_type, "image/png")

    @override_settings(LLM_STREAM_CHUNK_DELAY_SECONDS=0)
    @patch("tree_ui.services.node_creation.stream_text")
    def test_can_stream_node_message_with_multiple_image_attachments_via_api(self, mock_stream_text):
        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                workspace = Workspace.objects.create(name="Main", slug="main")
                node = ConversationNode.objects.create(
                    workspace=workspace,
                    title="Vision node",
                    summary="",
                    provider=ConversationNode.Provider.OPENAI,
                    model_name="gpt-4.1-mini",
                )
                mock_stream_text.return_value = iter([ProviderDelta(text="Vision "), ProviderDelta(text="reply")])

                response = self.client.post(
                    reverse("stream_node_message", args=[workspace.slug, node.id]),
                    data={
                        "prompt": "Describe these images.",
                        "images": [
                            SimpleUploadedFile(
                                "photo-1.png",
                                b"fake-image-bytes-1",
                                content_type="image/png",
                            ),
                            SimpleUploadedFile(
                                "photo-2.png",
                                b"fake-image-bytes-2",
                                content_type="image/png",
                            ),
                        ],
                    },
                )

                self.assertEqual(response.status_code, 200)
                streamed = b"".join(response.streaming_content).decode("utf-8")
                self.assertIn('"attachment_count": 2', streamed)
                self.assertEqual(NodeAttachment.objects.filter(node=node).count(), 2)
                user_message = NodeMessage.objects.get(node=node, role=NodeMessage.Role.USER)
                self.assertEqual(user_message.attachments.count(), 2)
                self.assertEqual(len(mock_stream_text.call_args.kwargs["messages"][-1].attachments), 2)

    @override_settings(LLM_STREAM_CHUNK_DELAY_SECONDS=0)
    @patch("tree_ui.services.context_builder.render_pdf_attachment_as_data_urls")
    @patch("tree_ui.services.node_creation.stream_text")
    def test_can_stream_node_message_with_pdf_attachment_via_api(
        self,
        mock_stream_text,
        mock_render_pdf_attachment_as_data_urls,
    ):
        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                workspace = Workspace.objects.create(name="Main", slug="main")
                node = ConversationNode.objects.create(
                    workspace=workspace,
                    title="PDF node",
                    summary="",
                    provider=ConversationNode.Provider.OPENAI,
                    model_name="gpt-4.1-mini",
                )
                mock_stream_text.return_value = iter([ProviderDelta(text="PDF "), ProviderDelta(text="reply")])
                mock_render_pdf_attachment_as_data_urls.return_value = [
                    "data:image/png;base64,ZmFrZS1wYWdlLTE=",
                    "data:image/png;base64,ZmFrZS1wYWdlLTI=",
                ]

                response = self.client.post(
                    reverse("stream_node_message", args=[workspace.slug, node.id]),
                    data={
                        "prompt": "Summarize this PDF.",
                        "images": [
                            SimpleUploadedFile(
                                "slides.pdf",
                                b"%PDF-1.4 fake-pdf",
                                content_type="application/pdf",
                            )
                        ],
                    },
                )

                self.assertEqual(response.status_code, 200)
                streamed = b"".join(response.streaming_content).decode("utf-8")
                self.assertIn('"attachment_count": 1', streamed)
                attachment = NodeAttachment.objects.get(node=node)
                self.assertEqual(attachment.kind, NodeAttachment.Kind.PDF)
                context_attachments = mock_stream_text.call_args.kwargs["messages"][-1].attachments
                self.assertEqual(len(context_attachments), 2)
                self.assertTrue(all(item.kind == NodeAttachment.Kind.IMAGE for item in context_attachments))
                self.assertTrue(all(item.content_type == "image/png" for item in context_attachments))

    @override_settings(LLM_STREAM_CHUNK_DELAY_SECONDS=0)
    @patch("tree_ui.services.node_creation.stream_text")
    def test_can_stream_node_message_with_image_only_via_api(self, mock_stream_text):
        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                workspace = Workspace.objects.create(name="Main", slug="main")
                node = ConversationNode.objects.create(
                    workspace=workspace,
                    title="Vision node",
                    summary="",
                    provider=ConversationNode.Provider.OPENAI,
                    model_name="gpt-4.1-mini",
                )
                mock_stream_text.return_value = iter([ProviderDelta(text="Vision only")])

                response = self.client.post(
                    reverse("stream_node_message", args=[workspace.slug, node.id]),
                    data={
                        "prompt": "",
                        "images": [
                            SimpleUploadedFile(
                                "photo.png",
                                b"fake-image-bytes",
                                content_type="image/png",
                            )
                        ],
                    },
                )

                self.assertEqual(response.status_code, 200)
                streamed = b"".join(response.streaming_content).decode("utf-8")
                self.assertIn('"attachment_count": 1', streamed)
                user_message = NodeMessage.objects.get(node=node, role=NodeMessage.Role.USER)
                self.assertEqual(user_message.content, "")
                self.assertEqual(user_message.attachments.count(), 1)
                self.assertEqual(mock_stream_text.call_args.kwargs["messages"][-1].content, "")
                self.assertEqual(len(mock_stream_text.call_args.kwargs["messages"][-1].attachments), 1)

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
        mock_stream_text.return_value = iter([ProviderDelta(text="Branch "), ProviderDelta(text="reply")])

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

    def test_build_generation_messages_keeps_attachments_on_original_user_message(self):
        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                workspace = Workspace.objects.create(name="Main", slug="main")
                node = ConversationNode.objects.create(
                    workspace=workspace,
                    title="Root",
                    summary="",
                    provider=ConversationNode.Provider.OPENAI,
                    model_name="gpt-4.1-mini",
                )
                user_message = NodeMessage.objects.create(
                    node=node,
                    role=NodeMessage.Role.USER,
                    content="Describe the attached image.",
                    order_index=0,
                )
                NodeMessage.objects.create(
                    node=node,
                    role=NodeMessage.Role.ASSISTANT,
                    content="I can see the screenshot.",
                    order_index=1,
                )
                NodeAttachment.objects.create(
                    node=node,
                    source_message=user_message,
                    file=SimpleUploadedFile("diagram.png", b"fake-image-bytes", content_type="image/png"),
                    original_name="diagram.png",
                    content_type="image/png",
                    size_bytes=16,
                )

                messages = build_generation_messages(
                    parent=node,
                    prompt="Continue selected branch",
                )

                self.assertEqual(messages[0].content, "Describe the attached image.")
                self.assertEqual(messages[0].attachments[0].name, "diagram.png")
                self.assertEqual(messages[1].attachments, ())

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

class RoutingTests(TestCase):
    def test_auto_fast_routing_picks_correct_models(self):
        # Text only
        result = route_model(routing_mode=ConversationNode.RoutingMode.AUTO_FAST, has_attachments=False)
        self.assertEqual(result.provider, ConversationNode.Provider.OPENAI)
        self.assertEqual(result.model, "gpt-4.1-mini")
        self.assertIn("Fast mode", result.decision)

        # With attachments
        result = route_model(routing_mode=ConversationNode.RoutingMode.AUTO_FAST, has_attachments=True)
        self.assertEqual(result.provider, ConversationNode.Provider.GEMINI)
        self.assertEqual(result.model, "gemini-2.5-flash")
        self.assertIn("multimodal", result.decision)

    def test_auto_quality_routing_picks_correct_models(self):
        # Text only
        result = route_model(routing_mode=ConversationNode.RoutingMode.AUTO_QUALITY, has_attachments=False)
        self.assertEqual(result.provider, ConversationNode.Provider.GEMINI)
        self.assertEqual(result.model, "gemini-2.5-pro")

        # With attachments
        result = route_model(routing_mode=ConversationNode.RoutingMode.AUTO_QUALITY, has_attachments=True)
        self.assertEqual(result.provider, ConversationNode.Provider.OPENAI)
        self.assertEqual(result.model, "gpt-4.1")

    def test_node_creation_with_auto_routing_persists_decision(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        response = self.client.post(
            reverse("create_workspace_node", args=[workspace.slug]),
            data=json.dumps({
                "title": "Auto node",
                "routing_mode": "auto-quality",
                "provider": "", # Explicitly allow cross-provider
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        node = ConversationNode.objects.get()
        self.assertEqual(node.routing_mode, "auto-quality")
        self.assertEqual(node.provider, ConversationNode.Provider.GEMINI)
        self.assertEqual(node.model_name, "gemini-2.5-pro")
        self.assertIn("Quality mode", node.routing_decision)

    @override_settings(LLM_STREAM_CHUNK_DELAY_SECONDS=0)
    @patch("tree_ui.services.node_creation.stream_text")
    def test_first_message_triggers_re_routing_if_auto_mode(self, mock_stream_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        # Create node in auto-fast mode with NO provider restriction
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Auto node",
            routing_mode=ConversationNode.RoutingMode.AUTO_FAST,
            provider="", # No restriction
            model_name="gpt-4.1-mini",
        )
        mock_stream_text.return_value = iter([ProviderDelta(text="Reply")])

        # Send a message WITH attachments. Auto-fast should re-route to Gemini Flash.
        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse("stream_node_message", args=[workspace.slug, node.id]),
                    data={
                        "prompt": "Look at this.",
                        "images": [SimpleUploadedFile("img.png", b"...", content_type="image/png")],
                    },
                )
                self.assertEqual(response.status_code, 200)
                node.refresh_from_db()
                self.assertEqual(node.provider, ConversationNode.Provider.GEMINI)
                self.assertEqual(node.model_name, "gemini-2.5-flash")
                self.assertIn("multimodal", node.routing_decision)

    def test_auto_routing_restricted_to_provider(self):
        # Restricted to OpenAI
        result = route_model(
            routing_mode=ConversationNode.RoutingMode.AUTO_FAST,
            provider=ConversationNode.Provider.OPENAI,
            has_attachments=True # Normally Gemini Flash would be picked for attachments
        )
        self.assertEqual(result.provider, ConversationNode.Provider.OPENAI)
        self.assertEqual(result.model, "gpt-4.1-mini")
        self.assertIn("(Openai)", result.decision)

        # Restricted to Gemini
        result = route_model(
            routing_mode=ConversationNode.RoutingMode.AUTO_FAST,
            provider=ConversationNode.Provider.GEMINI,
            has_attachments=False # Normally OpenAI would be picked for text
        )
        self.assertEqual(result.provider, ConversationNode.Provider.GEMINI)
        self.assertEqual(result.model, "gemini-2.5-flash")
        self.assertIn("(Gemini)", result.decision)

class ToolUseTests(TestCase):
    def setUp(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        default_dispatcher.refresh()

    def test_compare_branches_tool_registered(self):
        from tree_ui.services.tools import default_registry
        tool = default_registry.get_tool("compare_branches")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "compare_branches")

    def test_compare_branches_workspace_boundary(self):
        workspace_a = Workspace.objects.create(name="A", slug="a")
        workspace_b = Workspace.objects.create(name="B", slug="b")
        
        node_a = ConversationNode.objects.create(
            workspace=workspace_a, title="Node A", provider="openai", model_name="gpt-4.1-mini"
        )
        node_b = ConversationNode.objects.create(
            workspace=workspace_b, title="Node B", provider="openai", model_name="gpt-4.1-mini"
        )
        
        from tree_ui.services.tools.branch_comparison import BranchComparisonTool
        tool = BranchComparisonTool()
        
        # Test with context from workspace A
        result = tool.execute(context={"workspace": workspace_a}, node_id_a=node_a.id, node_id_b=node_b.id)
        self.assertIn("error", result)
        self.assertIn("different workspace", result["error"])
        
        # Test with nodes in same workspace but no context (fallback check)
        node_a2 = ConversationNode.objects.create(
            workspace=workspace_a, title="Node A2", provider="openai", model_name="gpt-4.1-mini"
        )
        result = tool.execute(node_id_a=node_a.id, node_id_b=node_a2.id)
        self.assertNotIn("error", result)
        self.assertEqual(result["branch_a"]["title"], "Node A")

    @patch("tree_ui.services.node_creation.generate_text")
    def test_tool_invocation_persistence(self, mock_generate_text):
        from tree_ui.services.providers.base import ToolCall
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace, title="Root", provider="openai", model_name="gpt-4.1-mini"
        )
        
        mock_generate_text.return_value = GenerationResult(
            text="",
            provider="openai",
            model_name="gpt-4.1-mini",
            tool_calls=[ToolCall(call_id="call_1", name="compare_branches", arguments={"node_id_a": node.id, "node_id_b": node.id})]
        )
        
        from tree_ui.services.node_creation import generate_assistant_reply
        generate_assistant_reply(
            parent=node,
            provider="openai",
            model_name="gpt-4.1-mini",
            prompt="Compare branches"
        )
        
        self.assertEqual(ToolInvocation.objects.count(), 1)
        inv = ToolInvocation.objects.get()
        self.assertEqual(inv.tool_name, "compare_branches")
        self.assertEqual(inv.node, node)
        self.assertTrue(inv.success)

    def test_serialize_node_includes_tool_invocations(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace, title="Root", provider="openai", model_name="gpt-4.1-mini"
        )
        ToolInvocation.objects.create(
            node=node,
            tool_name="test_tool",
            tool_type="internal",
            source_id="test-source",
            invocation_payload='{"arg": 1}',
            result_payload='{"res": "ok"}',
            success=True
        )

        from tree_ui.services.graph_payload import serialize_node
        data = serialize_node(node)
        self.assertEqual(len(data["tool_invocations"]), 1)
        self.assertEqual(data["tool_invocations"][0]["name"], "test_tool")
        self.assertEqual(data["tool_invocations"][0]["tool_type"], "internal")
        self.assertEqual(data["tool_invocations"][0]["source_id"], "test-source")
        self.assertEqual(data["tool_invocations"][0]["args"], {"arg": 1})
    def test_serialize_node_includes_routing_metadata(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace,
            title="Root",
            provider="openai",
            model_name="gpt-4.1-mini",
            routing_mode=ConversationNode.RoutingMode.AUTO_FAST,
            routing_decision="Detected image input"
        )
        
        from tree_ui.services.graph_payload import serialize_node
        data = serialize_node(node)
        self.assertEqual(data["routing_mode"], "auto-fast")
        self.assertEqual(data["routing_decision"], "Detected image input")

    @override_settings(LLM_STREAM_CHUNK_DELAY_SECONDS=0)
    @patch("tree_ui.services.node_creation.stream_text")
    def test_streaming_tool_call_events(self, mock_stream_text):
        from tree_ui.services.providers.base import ProviderDelta, ToolCallDelta
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace, title="Root", provider="openai", model_name="gpt-4.1-mini"
        )
        
        mock_stream_text.return_value = iter([
            ProviderDelta(tool_call=ToolCallDelta(call_id="c1", name="compare_branches", arguments='{"node_id_a":')),
            ProviderDelta(tool_call=ToolCallDelta(call_id="c1", name="", arguments=' 1, "node_id_b": 1}')),
        ])
        
        response = self.client.post(
            reverse("stream_node_message", args=[workspace.slug, node.id]),
            data=json.dumps({"prompt": "test tool"}),
            content_type="application/json",
        )
        
        self.assertEqual(response.status_code, 200)
        streamed = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("event: tool_call", streamed)
        self.assertIn("event: tool_result", streamed)
        self.assertIn("compare_branches", streamed)

    def test_openai_tool_call_parsing(self):
        from tree_ui.services.providers.openai_provider import _extract_tool_calls
        response_data = {
            "output": [
                {
                    "type": "tool_calls",
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "function": {
                                "name": "compare_branches",
                                "arguments": '{"node_id_a": 123, "node_id_b": 456}'
                            }
                        }
                    ]
                }
            ]
        }
        tool_calls = _extract_tool_calls(response_data)
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0].name, "compare_branches")
        self.assertEqual(tool_calls[0].arguments["node_id_a"], 123)

    def test_gemini_tool_call_parsing(self):
        from tree_ui.services.providers.gemini_provider import _extract_tool_calls
        response_data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "compare_branches",
                                    "args": {"node_id_a": 123, "node_id_b": 456}
                                }
                            }
                        ]
                    }
                }
            ]
        }
        tool_calls = _extract_tool_calls(response_data)
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0].name, "compare_branches")
        self.assertEqual(tool_calls[0].arguments["node_id_a"], 123)

    def test_serialize_node_handles_empty_metadata(self):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace, title="Root", provider="openai", model_name="gpt-4.1-mini"
        )
        from tree_ui.services.graph_payload import serialize_node
        data = serialize_node(node)
        self.assertEqual(data["tool_invocations"], [])
        self.assertEqual(data["routing_decision"], "")

    @override_settings(LLM_STREAM_CHUNK_DELAY_SECONDS=0)
    @patch("tree_ui.services.node_creation.stream_text")
    def test_stream_node_message_returns_full_node_at_end(self, mock_stream_text):
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace, title="Root", provider="openai", model_name="gpt-4.1-mini"
        )
        mock_stream_text.return_value = iter([ProviderDelta(text="Hello")])
        
        response = self.client.post(
            reverse("stream_node_message", args=[workspace.slug, node.id]),
            data=json.dumps({"prompt": "hi"}),
            content_type="application/json",
        )
        
        streamed = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("event: node", streamed)
        # Parse the JSON from the 'node' event
        node_event_line = [line for line in streamed.split("\n") if line.startswith("data: {\"node\":")][0]
        node_data = json.loads(node_event_line[6:])["node"]
        self.assertIn("tool_invocations", node_data)
        self.assertIn("routing_decision", node_data)


class MCPAdapterTests(TestCase):
    def setUp(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        default_dispatcher.refresh()

    def test_internal_adapter_lists_tools(self):
        from tree_ui.services.mcp.internal_adapter import InternalToolAdapter
        adapter = InternalToolAdapter()
        tools = adapter.list_tools()
        self.assertTrue(len(tools) > 0)
        tool_names = [t.name for t in tools]
        self.assertIn("compare_branches", tool_names)

        # Check ToolDefinition shape
        compare_tool = next(t for t in tools if t.name == "compare_branches")
        self.assertEqual(compare_tool.source_type, "internal")
        self.assertEqual(compare_tool.source_id, "internal-registry")
        self.assertIn("node_id_a", compare_tool.input_schema["properties"])

    def test_dispatcher_aggregates_tools(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        schemas = default_dispatcher.get_tool_schemas()
        self.assertTrue(len(schemas) > 0)
        self.assertEqual(schemas[0]["type"], "function")

    def test_dispatcher_executes_internal_tool(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace, title="Root", provider="openai", model_name="gpt-4.1-mini"
        )

        # Execute compare_branches (internal tool) via dispatcher
        result = default_dispatcher.execute_tool(
            "compare_branches",
            {"node_id_a": node.id, "node_id_b": node.id},
            context={"workspace": workspace}
        )

        self.assertFalse(result.is_error)
        self.assertEqual(len(result.content), 1)
        self.assertEqual(result.content[0]["type"], "text")
        self.assertIn("Root", result.content[0]["text"])
        self.assertEqual(result.metadata["raw"]["branch_a"]["title"], "Root")

    def test_dispatcher_returns_error_for_unknown_tool(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        result = default_dispatcher.execute_tool("non_existent_tool", {})
        self.assertTrue(result.is_error)
        self.assertIn("not found", result.content[0]["text"])

    @patch("tree_ui.services.node_creation.generate_text")
    def test_node_creation_uses_mcp_dispatcher_and_persists_metadata(self, mock_generate_text):
        from tree_ui.services.providers.base import ToolCall
        workspace = Workspace.objects.create(name="Main", slug="main")
        node = ConversationNode.objects.create(
            workspace=workspace, title="Root", provider="openai", model_name="gpt-4.1-mini"
        )

        mock_generate_text.return_value = GenerationResult(
            text="",
            provider="openai",
            model_name="gpt-4.1-mini",
            tool_calls=[ToolCall(call_id="call_1", name="compare_branches", arguments={"node_id_a": node.id, "node_id_b": node.id})]
        )

        from tree_ui.services.node_creation import generate_assistant_reply
        generate_assistant_reply(
            parent=node,
            provider="openai",
            model_name="gpt-4.1-mini",
            prompt="Compare branches"
        )

        self.assertEqual(ToolInvocation.objects.count(), 1)
        inv = ToolInvocation.objects.get()
        self.assertEqual(inv.tool_name, "compare_branches")
        self.assertEqual(inv.tool_type, "internal")  # Verified standardized metadata
        self.assertEqual(inv.node, node)
        self.assertTrue(inv.success)
        # Check if result_payload is the serialized MCP content (list of blocks)
        content = json.loads(inv.result_payload)
        self.assertIsInstance(content, list)
        self.assertEqual(content[0]["type"], "text")

    def test_mcpsource_registration_and_listing(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        from tree_ui.models import MCPSource

        # Clear existing sources and refresh
        MCPSource.objects.all().delete()
        default_dispatcher.refresh()

        # Add internal source record
        MCPSource.objects.create(
            name="Internal Tools",
            source_id="internal-registry-db",
            source_type=MCPSource.SourceType.INTERNAL,
            is_enabled=True,
        )

        # Add mock source record
        MCPSource.objects.create(
            name="Mock External",
            source_id="mock-ext",
            source_type=MCPSource.SourceType.MOCK,
            is_enabled=True,
        )

        default_dispatcher.refresh()
        tools = default_dispatcher.list_tools()

        # Should have internal tools + mock tools
        tool_names = [t.name for t in tools]
        self.assertIn("compare_branches", tool_names)
        self.assertIn("external_echo", tool_names)

        # Verify source metadata in ToolDefinition
        echo_tool = next(t for t in tools if t.name == "external_echo")
        self.assertEqual(echo_tool.source_id, "mock-ext")
        self.assertEqual(echo_tool.source_type, "mock")

    def test_enabled_disabled_source(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        from tree_ui.models import MCPSource

        MCPSource.objects.all().delete()

        # Add disabled mock source
        MCPSource.objects.create(
            name="Disabled Mock",
            source_id="disabled-mock",
            source_type=MCPSource.SourceType.MOCK,
            is_enabled=False,
        )

        default_dispatcher.refresh()
        tools = default_dispatcher.list_tools()
        tool_names = [t.name for t in tools]
        self.assertNotIn("external_echo", tool_names)

    def test_mock_external_tool_execution(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        from tree_ui.models import MCPSource

        MCPSource.objects.all().delete()
        MCPSource.objects.create(
            name="Mock External",
            source_id="mock-ext",
            source_type=MCPSource.SourceType.MOCK,
            is_enabled=True,
        )
        default_dispatcher.refresh()

        result = default_dispatcher.execute_tool(
            "external_echo", {"message": "hello multi-source"}
        )
        self.assertFalse(result.is_error)
        self.assertIn(
            "Mock external echo: hello multi-source", result.content[0]["text"]
        )
        self.assertEqual(result.metadata["source_name"], "Mock External")

    def test_mock_only_source_still_keeps_internal_tools(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        from tree_ui.models import MCPSource

        MCPSource.objects.all().delete()
        MCPSource.objects.create(
            name="Mock External",
            source_id="mock-ext",
            source_type=MCPSource.SourceType.MOCK,
            is_enabled=True,
        )

        default_dispatcher.refresh()
        tool_names = [t.name for t in default_dispatcher.list_tools()]
        self.assertIn("external_echo", tool_names)
        self.assertIn("compare_branches", tool_names)

    def test_internal_source_registration_controls_source_identity(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        from tree_ui.models import MCPSource

        MCPSource.objects.all().delete()
        MCPSource.objects.create(
            name="Registered Internal",
            source_id="registered-internal",
            source_type=MCPSource.SourceType.INTERNAL,
            is_enabled=True,
        )

        default_dispatcher.refresh()
        compare_tool = next(
            t for t in default_dispatcher.list_tools() if t.name == "compare_branches"
        )
        self.assertEqual(compare_tool.source_type, "internal")
        self.assertEqual(compare_tool.source_id, "registered-internal")

    def test_dispatcher_fallback_to_internal_when_no_sources_in_db(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        from tree_ui.models import MCPSource

        # Ensure no sources in DB
        MCPSource.objects.all().delete()
        default_dispatcher.refresh()

        tools = default_dispatcher.list_tools()
        tool_names = [t.name for t in tools]
        # Should still find internal tools due to fallback logic in dispatcher
        self.assertIn("compare_branches", tool_names)


class RemoteMCPAdapterTests(TestCase):
    def setUp(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher

        default_dispatcher.refresh()

    def test_remote_adapter_config_validation(self):
        from tree_ui.services.mcp.remote_adapter import RemoteMCPSourceAdapter

        # Test empty config (should use defaults)
        adapter = RemoteMCPSourceAdapter(source_id="test-remote", name="Test Remote", config={})
        status = adapter.get_status()
        self.assertEqual(status["config"]["transport_kind"], "stub")
        self.assertEqual(status["config"]["label"], "Remote MCP Server")

        # Test valid custom config
        custom_config = {
            "transport_kind": "sse",
            "endpoint": "http://localhost:8080/mcp",
            "label": "Custom Remote Server",
            "timeout": 60,
        }
        adapter2 = RemoteMCPSourceAdapter(
            source_id="test-remote-2", name="Test Remote 2", config=custom_config
        )
        status2 = adapter2.get_status()
        self.assertEqual(status2["config"]["transport_kind"], "sse")
        self.assertEqual(status2["config"]["endpoint"], "http://localhost:8080/mcp")
        self.assertEqual(status2["config"]["label"], "Custom Remote Server")
        self.assertEqual(status2["config"]["timeout"], 60)

    def test_remote_adapter_uses_transport_specific_client_selection(self):
        from tree_ui.services.mcp.client import StubMCPClient, UnsupportedTransportClient
        from tree_ui.services.mcp.remote_adapter import RemoteMCPSourceAdapter

        stub_adapter = RemoteMCPSourceAdapter(
            source_id="stub-remote", name="Stub Remote", config={"transport_kind": "stub"}
        )
        self.assertIsInstance(stub_adapter._client, StubMCPClient)

        sse_adapter = RemoteMCPSourceAdapter(
            source_id="sse-remote", name="SSE Remote", config={"transport_kind": "sse"}
        )
        self.assertIsInstance(sse_adapter._client, UnsupportedTransportClient)
        self.assertEqual(sse_adapter.get_status()["client_info"]["status"], "not_implemented")

    def test_remote_adapter_lists_tools_via_stub_client(self):
        from tree_ui.services.mcp.remote_adapter import RemoteMCPSourceAdapter

        adapter = RemoteMCPSourceAdapter(
            source_id="test-remote", name="Test Remote", config={"label": "Remote Calc Server"}
        )
        tools = adapter.list_tools()

        self.assertEqual(len(tools), 2)
        tool_names = [t.name for t in tools]
        self.assertIn("remote_calculator", tool_names)
        self.assertIn("remote_fetch", tool_names)

        # Verify ToolDefinition metadata
        calc_tool = next(t for t in tools if t.name == "remote_calculator")
        self.assertEqual(calc_tool.source_type, "mcp_server")
        self.assertEqual(calc_tool.source_id, "test-remote")
        self.assertIn("Remote Calc Server", calc_tool.description)

    def test_remote_adapter_executes_tool_via_stub_client(self):
        from tree_ui.services.mcp.remote_adapter import RemoteMCPSourceAdapter

        adapter = RemoteMCPSourceAdapter(
            source_id="test-remote", name="Test Remote", config={"label": "Remote Calc Server"}
        )

        result = adapter.execute_tool(
            "remote_calculator", {"operation": "multiply", "a": 6, "b": 7}
        )

        self.assertFalse(result.is_error)
        self.assertEqual(result.content[0]["text"], "Result: 42")
        self.assertEqual(result.metadata["server"], "Remote Calc Server")

    def test_dispatcher_uses_remote_adapter_for_mcp_server_source(self):
        from tree_ui.models import MCPSource
        from tree_ui.services.mcp.dispatcher import default_dispatcher

        MCPSource.objects.all().delete()
        MCPSource.objects.create(
            name="Real-like Remote",
            source_id="real-remote",
            source_type=MCPSource.SourceType.MCP_SERVER,
            config={"label": "Production Server", "transport_kind": "sse"},
            is_enabled=True,
        )

        default_dispatcher.refresh()
        tools = default_dispatcher.list_tools()
        tool_names = [t.name for t in tools]

        self.assertIn("compare_branches", tool_names)  # Internal tool fallback should still work
        self.assertIn("real-remote__unavailable", tool_names)

        unavailable_tool = next(t for t in tools if t.name == "real-remote__unavailable")
        self.assertEqual(unavailable_tool.source_type, "mcp_server")
        self.assertEqual(unavailable_tool.source_id, "real-remote")
        self.assertIn("not yet implemented", unavailable_tool.description)

    def test_multi_source_coexistence(self):
        from tree_ui.models import MCPSource
        from tree_ui.services.mcp.dispatcher import default_dispatcher

        MCPSource.objects.all().delete()

        # 1. Internal
        MCPSource.objects.create(
            name="Internal",
            source_id="internal-db",
            source_type=MCPSource.SourceType.INTERNAL,
            is_enabled=True,
        )
        # 2. Mock
        MCPSource.objects.create(
            name="Mock",
            source_id="mock-db",
            source_type=MCPSource.SourceType.MOCK,
            is_enabled=True,
        )
        # 3. Remote
        MCPSource.objects.create(
            name="Remote",
            source_id="remote-db",
            source_type=MCPSource.SourceType.MCP_SERVER,
            config={"label": "Remote Hub"},
            is_enabled=True,
        )

        default_dispatcher.refresh()
        tools = default_dispatcher.list_tools()
        tool_names = [t.name for t in tools]

        self.assertIn("compare_branches", tool_names)  # from internal
        self.assertIn("external_echo", tool_names)  # from mock
        self.assertIn("remote_calculator", tool_names)  # from remote

        # Execute one from each
        res_int = default_dispatcher.execute_tool(
            "compare_branches",
            {"node_id_a": 0, "node_id_b": 0},
            context={"workspace": None},
        )
        self.assertTrue(res_int.is_error)  # Error is expected because node 0 doesn't exist

        res_mock = default_dispatcher.execute_tool("external_echo", {"message": "hi"})
        self.assertFalse(res_mock.is_error)
        self.assertIn("Mock external echo", res_mock.content[0]["text"])

        res_rem = default_dispatcher.execute_tool(
            "remote_calculator", {"operation": "add", "a": 10, "b": 20}
        )
        self.assertFalse(res_rem.is_error)
        self.assertEqual(res_rem.content[0]["text"], "Result: 30")

    def test_remote_adapter_handles_client_failure(self):
        from tree_ui.services.mcp.client import BaseMCPClient
        from tree_ui.services.mcp.remote_adapter import RemoteMCPSourceAdapter

        class FailingClient(BaseMCPClient):
            def list_tools(self):
                raise Exception("Network timeout")

            def call_tool(self, name, arguments):
                raise Exception("Server crashed")

            def get_server_info(self):
                return {"status": "error"}

        adapter = RemoteMCPSourceAdapter(
            source_id="fail", name="Fail", config={}, client=FailingClient()
        )

        tools = adapter.list_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].source_id, "fail")
        self.assertIn("Remote source unavailable", tools[0].description)
        result = adapter.execute_tool("any", {})
        self.assertTrue(result.is_error)
        self.assertIn("Remote MCP execution failed: Server crashed", result.content[0]["text"])

class MCPSourceManagementTests(TestCase):
    def setUp(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher

        default_dispatcher.refresh()

    def test_mcp_source_list_page_renders(self):
        MCPSource.objects.create(
            name="Test Source",
            source_id="test-source",
            source_type=MCPSource.SourceType.INTERNAL,
            is_enabled=True,
        )
        response = self.client.get(reverse("mcp_source_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Source")
        self.assertContains(response, "test-source")
        self.assertContains(response, "Internal Registry")

    def test_can_create_mcp_source(self):
        response = self.client.post(reverse("mcp_source_create"), {
            "name": "New Remote",
            "source_id": "new-remote",
            "source_type": "mcp_server",
            "is_enabled": True,
            "description": "A new remote source",
            "config_json": json.dumps({"transport_kind": "sse", "endpoint": "http://localhost:8080"})
        })
        self.assertEqual(response.status_code, 302)
        source = MCPSource.objects.get(source_id="new-remote")
        self.assertEqual(source.name, "New Remote")
        self.assertEqual(source.config["transport_kind"], "sse")

    def test_can_edit_mcp_source(self):
        source = MCPSource.objects.create(
            name="Old Name",
            source_id="old-source",
            source_type=MCPSource.SourceType.MOCK,
            is_enabled=True,
        )
        response = self.client.post(reverse("mcp_source_edit", args=[source.id]), {
            "name": "Updated Name",
            "source_id": "old-source",
            "source_type": "mock",
            "is_enabled": False,
            "description": "Updated",
            "config_json": "{}"
        })
        self.assertEqual(response.status_code, 302)
        source.refresh_from_db()
        self.assertEqual(source.name, "Updated Name")
        self.assertFalse(source.is_enabled)

    def test_invalid_json_config_returns_error(self):
        response = self.client.post(reverse("mcp_source_create"), {
            "name": "Invalid Config",
            "source_id": "invalid-config",
            "source_type": "mcp_server",
            "is_enabled": True,
            "config_json": "{ invalid json"
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid JSON format.")
        self.assertEqual(MCPSource.objects.filter(source_id="invalid-config").count(), 0)

    def test_can_delete_mcp_source(self):
        source = MCPSource.objects.create(
            name="To Delete",
            source_id="to-delete",
            source_type=MCPSource.SourceType.MOCK,
        )
        response = self.client.post(reverse("mcp_source_delete", args=[source.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MCPSource.objects.filter(pk=source.id).exists())

    def test_mcp_source_management_refreshes_dispatcher_cache(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher

        initial_tool_names = [t.name for t in default_dispatcher.list_tools()]
        self.assertIn("compare_branches", initial_tool_names)
        self.assertNotIn("external_echo", initial_tool_names)

        response = self.client.post(reverse("mcp_source_create"), {
            "name": "New Mock",
            "source_id": "new-mock",
            "source_type": "mock",
            "is_enabled": True,
            "description": "Mock source",
            "config_json": "{}"
        })
        self.assertEqual(response.status_code, 302)

        updated_tool_names = [t.name for t in default_dispatcher.list_tools()]
        self.assertIn("compare_branches", updated_tool_names)
        self.assertIn("external_echo", updated_tool_names)

    def test_can_run_mcp_source_diagnostic_for_mock_source(self):
        source = MCPSource.objects.create(
            name="Mock Source",
            source_id="mock-source",
            source_type=MCPSource.SourceType.MOCK,
            is_enabled=True,
        )

        response = self.client.post(reverse("mcp_source_test", args=[source.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ready")
        self.assertContains(response, "Connection succeeded. Discovered 2 tool(s).")
        self.assertContains(response, "external_echo")

    def test_can_run_mcp_source_diagnostic_for_stdio_failure(self):
        source = MCPSource.objects.create(
            name="Broken Stdio",
            source_id="broken-stdio",
            source_type=MCPSource.SourceType.MCP_SERVER,
            is_enabled=True,
            config={"transport_kind": "stdio", "command": "non-existent-command-123"},
        )

        response = self.client.post(reverse("mcp_source_test", args=[source.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unavailable")
        self.assertContains(response, "Failed to start subprocess")

class StdioMCPTransportTests(TestCase):
    def setUp(self):
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        default_dispatcher.refresh()

    def test_stdio_client_initialization(self):
        from tree_ui.services.mcp.stdio_client import StdioMCPClient
        config = {
            "command": "python3",
            "args": ["server.py"],
            "env": {"DEBUG": "1"},
            "label": "Test Server"
        }
        client = StdioMCPClient(config)
        self.assertEqual(client.command, "python3")
        self.assertEqual(client.args, ["server.py"])
        self.assertEqual(client.env, {"DEBUG": "1"})
        self.assertEqual(client.server_label, "Test Server")
        self.assertEqual(client.get_server_info()["status"], "skeleton")

    def test_remote_adapter_config_validation_for_stdio(self):
        from tree_ui.services.mcp.remote_adapter import RemoteMCPSourceAdapter
        config = {
            "transport_kind": "stdio",
            "command": "node",
            "args": ["mcp-server.js"],
            "cwd": "/tmp"
        }
        adapter = RemoteMCPSourceAdapter(source_id="stdio-test", name="Stdio Source", config=config)
        status = adapter.get_status()
        self.assertEqual(status["config"]["transport_kind"], "stdio")
        self.assertEqual(status["config"]["command"], "node")
        self.assertEqual(status["config"]["args"], ["mcp-server.js"])
        self.assertEqual(status["config"]["cwd"], "/tmp")

    def test_remote_adapter_normalizes_invalid_stdio_config_shapes(self):
        from tree_ui.services.mcp.remote_adapter import RemoteMCPSourceAdapter

        adapter = RemoteMCPSourceAdapter(
            source_id="stdio-invalid",
            name="Broken Stdio",
            config={
                "transport_kind": "stdio",
                "command": 123,
                "args": "server.py",
                "env": ["DEBUG=1"],
                "cwd": ["not-a-path"],
            },
        )
        status = adapter.get_status()
        self.assertEqual(status["config"]["command"], "")
        self.assertEqual(status["config"]["args"], [])
        self.assertEqual(status["config"]["env"], {})
        self.assertIsNone(status["config"]["cwd"])

    def test_remote_adapter_normalizes_invalid_timeout(self):
        from tree_ui.services.mcp.remote_adapter import RemoteMCPSourceAdapter

        adapter = RemoteMCPSourceAdapter(
            source_id="stdio-invalid-timeout",
            name="Broken Timeout",
            config={
                "transport_kind": "stdio",
                "command": "python3",
                "timeout": "abc",
            },
        )
        status = adapter.get_status()
        self.assertEqual(status["config"]["timeout"], 30.0)

    def test_adapter_builds_stdio_client(self):
        from tree_ui.services.mcp.remote_adapter import RemoteMCPSourceAdapter
        from tree_ui.services.mcp.stdio_client import StdioMCPClient
        config = {"transport_kind": "stdio", "command": "ls"}
        adapter = RemoteMCPSourceAdapter(source_id="ls-source", name="LS", config=config)
        self.assertIsInstance(adapter._client, StdioMCPClient)

    def test_stdio_client_real_handshake_and_discovery(self):
        from tree_ui.services.mcp.stdio_client import StdioMCPClient
        import os
        server_path = os.path.join(os.path.dirname(__file__), "services/mcp/test_mcp_server.py")
        client = StdioMCPClient({"command": "python3", "args": [server_path], "label": "Real Server"})
        
        try:
            tools = client.list_tools()
            self.assertEqual(len(tools), 1)
            self.assertEqual(tools[0].name, "echo")
            self.assertIn("Echoes back", tools[0].description)
            
            # Check server info
            info = client.get_server_info()
            self.assertEqual(info["status"], "connected")
            self.assertEqual(info["server_info"]["name"], "Test Echo Server")
        finally:
            client._stop_process()

    def test_stdio_client_real_call(self):
        from tree_ui.services.mcp.stdio_client import StdioMCPClient
        import os
        server_path = os.path.join(os.path.dirname(__file__), "services/mcp/test_mcp_server.py")
        client = StdioMCPClient({"command": "python3", "args": [server_path], "label": "Real Server"})
        
        try:
            result = client.call_tool("echo", {"message": "Hello World"})
            self.assertFalse(result.is_error)
            self.assertEqual(result.content[0]["text"], "Echo: Hello World")
        finally:
            client._stop_process()

    def test_stdio_source_registration_in_dispatcher_real(self):
        from tree_ui.models import MCPSource
        from tree_ui.services.mcp.dispatcher import default_dispatcher
        import os
        server_path = os.path.join(os.path.dirname(__file__), "services/mcp/test_mcp_server.py")

        MCPSource.objects.all().delete()
        MCPSource.objects.create(
            name="Real Subprocess Server",
            source_id="stdio-source",
            source_type=MCPSource.SourceType.MCP_SERVER,
            config={"transport_kind": "stdio", "command": "python3", "args": [server_path], "label": "Real Server"},
            is_enabled=True,
        )

        default_dispatcher.refresh()
        tools = default_dispatcher.list_tools()
        tool_names = [t.name for t in tools]
        self.assertIn("echo", tool_names)

        # Execute it
        result = default_dispatcher.execute_tool("echo", {"message": "Dispatcher Test"})
        self.assertFalse(result.is_error)
        self.assertIn("Echo: Dispatcher Test", result.content[0]["text"])

    def test_stdio_client_process_failure_path(self):
        from tree_ui.services.mcp.stdio_client import StdioMCPClient
        # Use a non-existent command
        client = StdioMCPClient({"command": "non_existent_command_12345", "label": "Fail Server"})
        with self.assertRaises(RuntimeError) as cm:
            client.list_tools()
        self.assertIn("Failed to start subprocess", str(cm.exception))

    def test_stdio_client_malformed_json_failure(self):
        from tree_ui.services.mcp.stdio_client import StdioMCPClient
        import os
        server_path = os.path.join(os.path.dirname(__file__), "services/mcp/malformed_mcp_server.py")
        client = StdioMCPClient({"command": "python3", "args": [server_path], "label": "Malformed Server"})
        
        try:
            with self.assertRaises(RuntimeError) as cm:
                client.list_tools()
            self.assertIn("Failed to parse JSON", str(cm.exception))
        finally:
            client._stop_process()

    def test_stdio_client_timeout_failure(self):
        from tree_ui.services.mcp.stdio_client import StdioMCPClient
        import os

        server_path = os.path.join(os.path.dirname(__file__), "services/mcp/hanging_mcp_server.py")
        client = StdioMCPClient(
            {
                "command": "python3",
                "args": [server_path],
                "label": "Hanging Server",
                "timeout": 0.1,
            }
        )

        try:
            with self.assertRaises(RuntimeError) as cm:
                client.list_tools()
            self.assertIn("Timed out waiting for stdio MCP response", str(cm.exception))
        finally:
            client._stop_process()

    def test_stdio_client_handshake_mismatch_failure(self):
        from tree_ui.services.mcp.stdio_client import StdioMCPClient
        import os
        # Use cat as a server, it will just echo back our initialize request, 
        # but it won't have an ID that matches what we expect if we expect result.
        # Wait, cat will echo the line, so _read_json will get the request we sent.
        # But our request has "id": 1, so _read_json will see "id": 1.
        # But it won't have "result" or "error", so _request will fail or loop.
        
        client = StdioMCPClient({"command": "cat", "label": "Cat Server"})
        try:
            with self.assertRaises(RuntimeError) as cm:
                # We expect it to fail because it doesn't return a valid initialize response
                client.list_tools()
            self.assertIn("Handshake failed", str(cm.exception))
        finally:
            client._stop_process()

    def test_invalid_stdio_config_list_tools_fails(self):
        from tree_ui.services.mcp.stdio_client import StdioMCPClient
        # Missing command
        client = StdioMCPClient({"transport_kind": "stdio"})
        with self.assertRaises(RuntimeError) as cm:
            client.list_tools()
        self.assertIn("No command configured", str(cm.exception))

    def test_invalid_stdio_config_call_tool_returns_error(self):
        from tree_ui.services.mcp.stdio_client import StdioMCPClient

        client = StdioMCPClient({"transport_kind": "stdio"})
        result = client.call_tool("bad__unavailable", {})
        self.assertTrue(result.is_error)
        self.assertIn("No command configured", result.content[0]["text"])

    def test_sse_remains_unimplemented(self):
        from tree_ui.services.mcp.remote_adapter import RemoteMCPSourceAdapter
        from tree_ui.services.mcp.client import UnsupportedTransportClient
        config = {"transport_kind": "sse"}
        adapter = RemoteMCPSourceAdapter(source_id="sse-test", name="SSE", config=config)
        self.assertIsInstance(adapter._client, UnsupportedTransportClient)
        
        # list_tools handles Exception and returns an "unavailable" indicator
        tools = adapter.list_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].source_id, "sse-test")
        self.assertIn("unavailable", tools[0].name.lower())
        self.assertIn("unsupported", tools[0].description.lower())
        self.assertIn("recognized but not yet implemented", tools[0].description)


class MCPSourcePersistenceTests(TestCase):
    def test_diagnostic_persistence_on_success(self):
        source = MCPSource.objects.create(
            name="Mock Source",
            source_id="mock-source",
            source_type=MCPSource.SourceType.MOCK,
            is_enabled=True,
        )

        response = self.client.post(reverse("mcp_source_test", args=[source.id]))
        self.assertEqual(response.status_code, 302)

        source.refresh_from_db()
        self.assertIsNotNone(source.last_checked_at)
        self.assertTrue(source.last_check_ok)
        self.assertEqual(source.last_check_label, "Ready")
        self.assertEqual(source.last_check_tool_count, 2)
        self.assertIn("external_echo", source.last_check_tools_summary)

    def test_diagnostic_persistence_on_failure(self):
        source = MCPSource.objects.create(
            name="Broken Stdio",
            source_id="broken-stdio",
            source_type=MCPSource.SourceType.MCP_SERVER,
            is_enabled=True,
            config={"transport_kind": "stdio", "command": "non-existent-cmd"},
        )

        self.client.post(reverse("mcp_source_test", args=[source.id]))
        source.refresh_from_db()

        self.assertIsNotNone(source.last_checked_at)
        self.assertFalse(source.last_check_ok)
        self.assertEqual(source.last_check_label, "Unavailable")
        self.assertIn("Failed to start subprocess", source.last_check_message)

    def test_list_page_displays_persisted_status(self):
        from django.utils import timezone
        source = MCPSource.objects.create(
            name="Persisted Source",
            source_id="persisted-source",
            source_type=MCPSource.SourceType.MOCK,
            last_checked_at=timezone.now(),
            last_check_ok=True,
            last_check_label="Persisted Ready",
            last_check_message="Everything is fine",
            last_check_tool_count=5,
            last_check_tools_summary="tool1, tool2, tool3",
        )

        response = self.client.get(reverse("mcp_source_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Persisted Ready")
        self.assertContains(response, "Everything is fine")
        self.assertContains(response, "Tools: 5")
        self.assertContains(response, "tool1, tool2, tool3")
