import { postJSON } from "./api.js";
import { renderCanvas } from "./canvas.js";
import { syncModelOptions } from "./model-options.js";
import { renderMessageEditors, renderNodeDetails } from "./node-panel.js";
import { createViewportController } from "./viewport.js";

const payload = JSON.parse(document.getElementById("graph-payload").textContent);

const workspaceName = document.getElementById("workspace-name");
const nodeTitle = document.getElementById("node-title");
const nodeProvider = document.getElementById("node-provider");
const openChatLink = document.getElementById("open-chat-link");
const nodeModel = document.getElementById("node-model");
const nodeParent = document.getElementById("node-parent");
const nodeSummary = document.getElementById("node-summary");
const messageList = document.getElementById("message-list");
const formTarget = document.getElementById("form-target");
const feedback = document.getElementById("form-feedback");
const nodeForm = document.getElementById("node-form");
const workspaceCreateForm = document.getElementById("workspace-create-form");
const workspaceNameInput = document.getElementById("workspace-name-input");
const workspaceCreateButton = document.getElementById("workspace-create-button");
const workspaceCreateFeedback = document.getElementById("workspace-create-feedback");
const nodeTitleInput = document.getElementById("node-title-input");
const providerInput = document.getElementById("node-provider-input");
const modelInput = document.getElementById("node-model-input");
const submitButton = document.getElementById("node-submit-button");
const rootModeToggle = document.getElementById("root-mode-toggle");
const editBox = document.getElementById("edit-box");
const editForm = document.getElementById("edit-form");
const editTitleInput = document.getElementById("edit-title-input");
const editMessageList = document.getElementById("edit-message-list");
const editSubmitButton = document.getElementById("edit-submit-button");
const editFeedback = document.getElementById("edit-feedback");
const csrfToken = document.getElementById("csrf-token").value;

const viewport = createViewportController();

workspaceName.textContent = payload.workspace.name;

const nodesById = new Map(payload.nodes.map((node) => [String(node.id), node]));
let selectedNodeId = String(payload.nodes[0]?.id || "");

function getSelectedNode() {
  return nodesById.get(selectedNodeId) || null;
}

function getNodeChatUrl(nodeId) {
  return openChatLink.dataset.nodeChatUrlTemplate.replace("999999", String(nodeId));
}

function isRootModeEnabled() {
  return rootModeToggle.checked;
}

function updateFormState() {
  const selectedNode = getSelectedNode();
  if (isRootModeEnabled() || !selectedNode) {
    formTarget.textContent = selectedNode && isRootModeEnabled()
      ? `New node target: separate root conversation (selection kept on "${selectedNode.title}")`
      : "New node target: root conversation";
    submitButton.textContent = "Create root conversation node";
    return;
  }

  formTarget.textContent = `New node target: child conversation of "${selectedNode.title}"`;
  submitButton.textContent = "Create child conversation node";
}

function showEmptyNodeState() {
  nodeTitle.textContent = "No node selected";
  nodeProvider.textContent = "Waiting";
  delete nodeProvider.dataset.provider;
  openChatLink.hidden = true;
  nodeModel.textContent = "-";
  nodeParent.textContent = "Root";
  nodeSummary.textContent = "Create a root conversation node to begin the workspace.";
  messageList.innerHTML = "";
  editBox.hidden = true;
}

function updateSelection(nodeId) {
  selectedNodeId = String(nodeId);
  const node = getSelectedNode();

  if (!node) {
    showEmptyNodeState();
    updateFormState();
    const metrics = renderCanvas(payload.nodes, selectedNodeId, updateSelection);
    viewport.setCanvasMetrics(metrics, payload.nodes.length > 0);
    return;
  }

  nodeTitle.textContent = node.title;
  nodeProvider.textContent = node.provider;
  nodeProvider.dataset.provider = node.provider;
  openChatLink.hidden = false;
  openChatLink.href = getNodeChatUrl(node.id);
  nodeModel.textContent = node.model_name;
  nodeParent.textContent = node.parent_id ? `Node ${node.parent_id}` : "Root";
  nodeSummary.textContent = node.summary || "Open this node to continue the conversation.";
  renderNodeDetails(messageList, node.messages.slice(-2));
  editBox.hidden = false;
  editTitleInput.value = `${node.title} (Edited)`;
  editFeedback.textContent = "";
  renderMessageEditors(editMessageList, node.messages);
  updateFormState();
  const metrics = renderCanvas(payload.nodes, selectedNodeId, updateSelection);
  viewport.setCanvasMetrics(metrics, payload.nodes.length > 0);
}

function getEditUrl(nodeId) {
  return editForm.dataset.nodeEditUrlTemplate.replace("999999", String(nodeId));
}

async function handleEditSubmit(event) {
  event.preventDefault();
  const selectedNode = getSelectedNode();
  if (!selectedNode) {
    editFeedback.textContent = "Select a node before creating an edited variant.";
    return;
  }

  editFeedback.textContent = "";
  editSubmitButton.disabled = true;

  try {
    const messages = Array.from(editMessageList.querySelectorAll("textarea")).map(
      (textarea, index) => ({
        role: textarea.dataset.role,
        content: textarea.value,
        order_index: index,
      }),
    );
    const response = await fetch(getEditUrl(selectedNode.id), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({
        title: editTitleInput.value,
        messages,
      }),
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed with status ${response.status}`);
    }
    const result = await response.json();
    payload.nodes.push(result.node);
    nodesById.set(String(result.node.id), result.node);
    editFeedback.textContent = `Edited variant "${result.node.title}" created.`;
    updateSelection(result.node.id);
  } catch (error) {
    editFeedback.textContent = error.message;
  } finally {
    editSubmitButton.disabled = false;
  }
}

async function handleWorkspaceCreateSubmit(event) {
  event.preventDefault();
  workspaceCreateFeedback.textContent = "";
  workspaceCreateButton.disabled = true;

  try {
    const response = await fetch(workspaceCreateForm.dataset.createWorkspaceUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({
        name: workspaceNameInput.value,
      }),
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Request failed with status ${response.status}`);
    }
    const result = await response.json();
    workspaceCreateFeedback.textContent = `Workspace "${result.workspace.name}" created.`;
    window.location.href = result.redirect_url;
  } catch (error) {
    workspaceCreateFeedback.textContent = error.message;
  } finally {
    workspaceCreateButton.disabled = false;
  }
}

async function handleNodeSubmit(event) {
  event.preventDefault();
  feedback.textContent = "";
  submitButton.disabled = true;

  try {
    const result = await postJSON(
      nodeForm.dataset.nodeCreateUrl,
      {
        parent_id: isRootModeEnabled() ? null : getSelectedNode()?.id ?? null,
        title: nodeTitleInput.value,
        provider: providerInput.value,
        model_name: modelInput.value,
      },
      csrfToken,
    );
    payload.nodes.push(result.node);
    nodesById.set(String(result.node.id), result.node);
    nodeTitleInput.value = "";
    feedback.textContent = `Conversation node "${result.node.title}" created. Open it to chat.`;
    updateSelection(result.node.id);
  } catch (error) {
    feedback.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

providerInput.addEventListener("change", () => syncModelOptions(providerInput, modelInput));
rootModeToggle.addEventListener("change", updateFormState);
nodeForm.addEventListener("submit", handleNodeSubmit);
editForm.addEventListener("submit", handleEditSubmit);
workspaceCreateForm.addEventListener("submit", handleWorkspaceCreateSubmit);
syncModelOptions(providerInput, modelInput);
const initialMetrics = renderCanvas(payload.nodes, selectedNodeId, updateSelection);
viewport.setCanvasMetrics(initialMetrics, payload.nodes.length > 0);
updateSelection(selectedNodeId);
