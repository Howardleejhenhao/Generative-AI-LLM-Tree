import { renderCanvas } from "./canvas.js";
import { renderNodeDetails, renderStreamingPreview } from "./node-panel.js";
import { getStreamingLabel, streamJSON } from "./streaming.js";
import { createViewportController } from "./viewport.js";

const payload = JSON.parse(document.getElementById("graph-payload").textContent);

const workspaceName = document.getElementById("workspace-name");
const nodeTitle = document.getElementById("node-title");
const nodeProvider = document.getElementById("node-provider");
const nodeModel = document.getElementById("node-model");
const nodeParent = document.getElementById("node-parent");
const nodeSummary = document.getElementById("node-summary");
const messageList = document.getElementById("message-list");
const streamingStatus = document.getElementById("streaming-status");
const formTarget = document.getElementById("form-target");
const feedback = document.getElementById("form-feedback");
const nodeForm = document.getElementById("node-form");
const nodeTitleInput = document.getElementById("node-title-input");
const providerInput = document.getElementById("node-provider-input");
const modelInput = document.getElementById("node-model-input");
const promptInput = document.getElementById("node-prompt-input");
const submitButton = document.getElementById("node-submit-button");
const rootModeToggle = document.getElementById("root-mode-toggle");
const csrfToken = document.getElementById("csrf-token").value;

const MODEL_OPTIONS = {
  openai: ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
  gemini: ["gemini-2.0-flash", "gemini-2.0-pro-exp", "gemini-1.5-pro"],
};
const viewport = createViewportController();

workspaceName.textContent = payload.workspace.name;

const nodesById = new Map(payload.nodes.map((node) => [String(node.id), node]));
let selectedNodeId = String(payload.nodes[0]?.id || "");

function syncModelOptions() {
  const provider = providerInput.value;
  const options = MODEL_OPTIONS[provider] || [];
  const previousValue = modelInput.value;
  modelInput.innerHTML = "";

  for (const option of options) {
    const element = document.createElement("option");
    element.value = option;
    element.textContent = option;
    if (option === previousValue) {
      element.selected = true;
    }
    modelInput.appendChild(element);
  }
}

function getSelectedNode() {
  return nodesById.get(selectedNodeId) || null;
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
    submitButton.textContent = "Create root conversation";
    return;
  }

  formTarget.textContent = `New node target: child of "${selectedNode.title}"`;
  submitButton.textContent = "Create child node";
}

function renderStreamingState(preview, assistantText) {
  nodeTitle.textContent = preview.title || "Streaming draft";
  nodeProvider.textContent = preview.provider;
  nodeProvider.dataset.provider = preview.provider;
  nodeModel.textContent = preview.model_name;
  nodeParent.textContent = preview.parent_id ? `Node ${preview.parent_id}` : "Root";
  nodeSummary.textContent = preview.summary || "Streaming response in progress.";
  streamingStatus.textContent = `Streaming response for ${preview.provider} / ${preview.model_name}...`;
  renderStreamingPreview(messageList, preview.prompt, assistantText);
}

function showEmptyNodeState() {
  nodeTitle.textContent = "No node selected";
  nodeProvider.textContent = "Waiting";
  delete nodeProvider.dataset.provider;
  nodeModel.textContent = "-";
  nodeParent.textContent = "Root";
  nodeSummary.textContent = "Create a root node to begin the workspace.";
  messageList.innerHTML = "";
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
  nodeModel.textContent = node.model_name;
  nodeParent.textContent = node.parent_id ? `Node ${node.parent_id}` : "Root";
  nodeSummary.textContent = node.summary || "No summary yet.";
  streamingStatus.textContent = getStreamingLabel(node);
  renderNodeDetails(messageList, node.messages);
  updateFormState();
  const metrics = renderCanvas(payload.nodes, selectedNodeId, updateSelection);
  viewport.setCanvasMetrics(metrics, payload.nodes.length > 0);
}

async function handleNodeSubmit(event) {
  event.preventDefault();
  feedback.textContent = "";
  submitButton.disabled = true;
  let previewState = null;
  let assistantText = "";

  try {
    await streamJSON(
      nodeForm.dataset.nodeStreamUrl,
      {
        parent_id: isRootModeEnabled() ? null : getSelectedNode()?.id ?? null,
        title: nodeTitleInput.value,
        provider: providerInput.value,
        model_name: modelInput.value,
        prompt: promptInput.value,
      },
      csrfToken,
      {
        preview(data) {
          previewState = data;
          assistantText = "";
          renderStreamingState(previewState, assistantText);
          feedback.textContent = "Streaming response...";
        },
        delta(data) {
          assistantText += data.delta;
          if (previewState) {
            renderStreamingState(previewState, assistantText);
          }
        },
        node(data) {
          payload.nodes.push(data.node);
          nodesById.set(String(data.node.id), data.node);
          nodeTitleInput.value = "";
          promptInput.value = "";
          feedback.textContent = `Node "${data.node.title}" created.`;
          updateSelection(data.node.id);
        },
        error(data) {
          throw new Error(data.message || "Streaming request failed.");
        },
      },
    );
  } catch (error) {
    feedback.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

providerInput.addEventListener("change", syncModelOptions);
rootModeToggle.addEventListener("change", updateFormState);
nodeForm.addEventListener("submit", handleNodeSubmit);
syncModelOptions();
const initialMetrics = renderCanvas(payload.nodes, selectedNodeId, updateSelection);
viewport.setCanvasMetrics(initialMetrics, payload.nodes.length > 0);
updateSelection(selectedNodeId);
