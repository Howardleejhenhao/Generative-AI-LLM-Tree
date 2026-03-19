from django.test import TestCase
from django.urls import reverse


class WorkspaceGraphViewTests(TestCase):
    def test_homepage_renders_graph_shell(self):
        response = self.client.get(reverse("workspace_graph"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Conversation DAG")
        self.assertContains(response, "graph-payload")
