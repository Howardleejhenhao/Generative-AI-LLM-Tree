import { postJSON } from "./api.js";
import { getNodeBounds, renderCanvas } from "./canvas.js";
import { createMinimapController } from "./minimap.js";
import { syncModelOptions } from "./model-options.js";
import { renderMessageEditors, renderNodeDetails } from "./node-panel.js";
import { createViewportController } from "./viewport.js";

const payload = JSON.parse(document.getElementById("graph-payload").textContent);

const DETAIL_PANEL_STORAGE_KEY = "llm-tree-detail-panel-collapsed";

const workspaceShell = document.getElementById("workspace-shell");
const workspaceName = document.getElementById("workspace-name");
const heroNodeCount = document.getElementById("hero-node-count");
const heroRootCount = document.getElementById("hero-root-count");
const heroMessageCount = document.getElementById("hero-message-count");
const workspaceNodeCount = document.getElementById("workspace-node-count");
const workspaceRootCount = document.getElementById("workspace-root-count");
const workspaceMessageCount = document.getElementById("workspace-message-count");
const workspaceSelectionTitle = document.getElementById("workspace-selection-title");
const workspaceSelectionSummary = document.getElementById("workspace-selection-summary");
const workspaceSelectionType = document.getElementById("workspace-selection-type");
const workspaceSelectionDepth = document.getElementById("workspace-selection-depth");
const graphStatus = document.getElementById("graph-status");
const detailPanelToggle = document.getElementById("detail-panel-toggle");
const detailPanelPeek = document.getElementById("detail-panel-peek");
const workspaceHelpToggle = document.getElementById("workspace-help-toggle");
const workspaceHelpDialog = document.getElementById("workspace-help-dialog");
const workspaceHelpBackdrop = document.getElementById("workspace-help-backdrop");
const workspaceHelpClose = document.getElementById("workspace-help-close");
const fitViewButton = document.getElementById("graph-fit-view");
const zoomOutButton = document.getElementById("graph-zoom-out");
const zoomInButton = document.getElementById("graph-zoom-in");
const zoomResetButton = document.getElementById("graph-zoom-reset");
const zoomLevel = document.getElementById("graph-zoom-level");
const nodeTitle = document.getElementById("node-title");
const nodeProvider = document.getElementById("node-provider");
const openChatLink = document.getElementById("open-chat-link");
const nodeModel = document.getElementById("node-model");
const nodeParent = document.getElementById("node-parent");
const nodeSummary = document.getElementById("node-summary");
const nodeModeLabel = document.getElementById("node-mode-label");
const nodeFocusCopy = document.getElementById("node-focus-copy");
const nodeMessageCount = document.getElementById("node-message-count");
const nodeLastRole = document.getElementById("node-last-role");
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
let latestViewportState = null;
let minimap = null;
let activeLineageIds = new Set();

function readStoredDetailPanelState() {
  try {
    return window.localStorage.getItem(DETAIL_PANEL_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function writeStoredDetailPanelState(isCollapsed) {
  try {
    window.localStorage.setItem(DETAIL_PANEL_STORAGE_KEY, String(isCollapsed));
  } catch {
    // Ignore storage failures and keep the UI state in-memory only.
  }
}

function setDetailPanelCollapsed(isCollapsed) {
  workspaceShell.dataset.detailPanelCollapsed = String(isCollapsed);
  detailPanelToggle.textContent = isCollapsed ? "Show inspector" : "Hide inspector";
  detailPanelToggle.setAttribute("aria-expanded", String(!isCollapsed));
  detailPanelPeek.hidden = !isCollapsed;
  writeStoredDetailPanelState(isCollapsed);
  viewport.refreshLayout();
}

function syncMinimap() {
  if (!minimap) {
    return;
  }

  minimap.update({
    nodes: payload.nodes,
    viewportState: latestViewportState,
  });
}

function handleViewportChange(viewportState) {
  latestViewportState = viewportState;
  zoomLevel.textContent = `${viewportState.percent}%`;
  fitViewButton.disabled = !viewportState.hasNodes || !viewportState.canFit;
  zoomOutButton.disabled = !viewportState.hasNodes || !viewportState.canZoomOut;
  zoomInButton.disabled = !viewportState.hasNodes || !viewportState.canZoomIn;
  zoomResetButton.disabled = !viewportState.hasNodes || viewportState.percent === 100;
  syncMinimap();
}

const viewport = createViewportController({ onChange: handleViewportChange });
minimap = createMinimapController({
  onNavigate: (point) => viewport.centerOnPoint(point),
});

workspaceName.textContent = payload.workspace.name;

const nodesById = new Map(payload.nodes.map((node) => [String(node.id), node]));
let selectedNodeId = String(payload.nodes[0]?.id || "");

function getSelectedNode() {
  return nodesById.get(selectedNodeId) || null;
}

function getLineageIds(node) {
  const ids = [];
  let currentNode = node;

  while (currentNode) {
    ids.push(String(currentNode.id));
    if (!currentNode.parent_id) {
      break;
    }
    currentNode = nodesById.get(String(currentNode.parent_id)) || null;
  }

  return ids.reverse();
}

function getRootNodeCount() {
  return payload.nodes.filter((node) => node.parent_id === null || node.parent_id === undefined).length;
}

function getTotalMessageCount() {
  return payload.nodes.reduce((total, node) => total + node.messages.length, 0);
}

function getLastMessage(node) {
  if (!node || !node.messages.length) {
    return null;
  }

  return node.messages[node.messages.length - 1];
}

function getNodeMode(node) {
  if (!node) {
    return "Waiting for selection";
  }

  if (node.edited_from_id) {
    return "Edited variant";
  }

  if (node.parent_id) {
    return "Branch conversation";
  }

  return "Root conversation";
}

function getSelectionSummaryText(node) {
  if (!node) {
    return "Choose a node to inspect details, open chat, or branch from that exact point in the tree.";
  }

  const messageCount = node.messages.length;
  const messageText = `${messageCount} ${messageCount === 1 ? "message" : "messages"} in this container.`;
  const lineageText = node.parent_id ? ` Branched from node ${node.parent_id}.` : " Top-level conversation.";
  const editText = node.edited_from_id ? ` Variant derived from node ${node.edited_from_id}.` : "";

  return `${messageText}${lineageText}${editText}`;
}

function isTypingTarget(element) {
  if (!element) {
    return false;
  }

  const tagName = element.tagName?.toLowerCase();
  return tagName === "input" || tagName === "textarea" || tagName === "select" || element.isContentEditable;
}

function setWorkspaceHelpOpen(isOpen) {
  workspaceHelpDialog.hidden = !isOpen;
  workspaceHelpDialog.setAttribute("aria-hidden", String(!isOpen));
  workspaceHelpToggle.setAttribute("aria-expanded", String(isOpen));
}

function updateWorkspaceSummary() {
  const nodeCount = payload.nodes.length;
  const rootCount = getRootNodeCount();
  const messageCount = getTotalMessageCount();
  const selectedNode = getSelectedNode();
  const lineageIds = getLineageIds(selectedNode);

  heroNodeCount.textContent = `${nodeCount} ${nodeCount === 1 ? "node" : "nodes"}`;
  heroRootCount.textContent = `${rootCount} ${rootCount === 1 ? "thread" : "threads"}`;
  heroMessageCount.textContent = `${messageCount} ${messageCount === 1 ? "message" : "messages"}`;
  workspaceNodeCount.textContent = String(nodeCount);
  workspaceRootCount.textContent = String(rootCount);
  workspaceMessageCount.textContent = String(messageCount);
  workspaceSelectionTitle.textContent = selectedNode ? selectedNode.title : "No node selected";
  workspaceSelectionSummary.textContent = getSelectionSummaryText(selectedNode);
  workspaceSelectionType.textContent = selectedNode ? getNodeMode(selectedNode) : "No active path";
  workspaceSelectionDepth.textContent = `Lineage depth ${lineageIds.length}`;
}

function getNodeChatUrl(nodeId) {
  return openChatLink.dataset.nodeChatUrlTemplate.replace("999999", String(nodeId));
}

function getNodePositionUrl(nodeId) {
  return graphStatus.dataset.nodePositionUrlTemplate.replace("999999", String(nodeId));
}

function isRootModeEnabled() {
  return rootModeToggle.checked;
}

function mergeNode(nextNode) {
  const nodeId = String(nextNode.id);
  const existingNode = nodesById.get(nodeId);

  if (existingNode) {
    Object.assign(existingNode, nextNode);
    existingNode.position = { ...nextNode.position };
    existingNode.messages = nextNode.messages;
    return existingNode;
  }

  payload.nodes.push(nextNode);
  nodesById.set(nodeId, nextNode);
  return nextNode;
}

function handleCanvasMetricsChange(metrics) {
  viewport.setCanvasMetrics(metrics, payload.nodes.length > 0);
  syncMinimap();
}

async function handleNodePositionCommit(nodeId, position) {
  const node = nodesById.get(String(nodeId));
  if (!node) {
    return;
  }

  const previousPosition = { ...node.position };
  graphStatus.textContent = `Saving layout for "${node.title}"...`;

  try {
    const result = await postJSON(
      getNodePositionUrl(nodeId),
      {
        position_x: position.x,
        position_y: position.y,
      },
      csrfToken,
    );
    const updatedNode = mergeNode(result.node);
    graphStatus.textContent = `Layout saved for "${updatedNode.title}".`;
  } catch (error) {
    node.position = previousPosition;
    graphStatus.textContent = error.message;
    renderGraphCanvas();
  }
}

function renderGraphCanvas() {
  return renderCanvas(payload.nodes, selectedNodeId, {
    activeLineageIds,
    onSelect: updateSelection,
    onPositionCommit: handleNodePositionCommit,
    onMetricsChange: handleCanvasMetricsChange,
    getViewportScale: () => viewport.getScale(),
  });
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
  activeLineageIds = new Set();
  nodeTitle.textContent = "No node selected";
  nodeProvider.textContent = "Waiting";
  delete nodeProvider.dataset.provider;
  openChatLink.hidden = true;
  nodeModel.textContent = "-";
  nodeParent.textContent = "Root";
  nodeSummary.textContent = "Create a root conversation node to begin the workspace.";
  nodeModeLabel.textContent = "Waiting for selection";
  nodeFocusCopy.textContent = "Pick a node to inspect its recent messages and branch from it safely.";
  nodeMessageCount.textContent = "0";
  nodeLastRole.textContent = "Empty";
  messageList.innerHTML = "";
  editBox.hidden = true;
  updateWorkspaceSummary();
}

function updateSelection(nodeId) {
  selectedNodeId = String(nodeId);
  const node = getSelectedNode();

  if (!node) {
    showEmptyNodeState();
    updateFormState();
    renderGraphCanvas();
    return;
  }

  activeLineageIds = new Set(getLineageIds(node));
  nodeTitle.textContent = node.title;
  nodeProvider.textContent = node.provider;
  nodeProvider.dataset.provider = node.provider;
  openChatLink.hidden = false;
  openChatLink.href = getNodeChatUrl(node.id);
  nodeModel.textContent = node.model_name;
  nodeParent.textContent = node.parent_id ? `Node ${node.parent_id}` : "Root";
  nodeSummary.textContent = node.summary || "Open this node to continue the conversation.";
  nodeModeLabel.textContent = getNodeMode(node);
  nodeFocusCopy.textContent = getSelectionSummaryText(node);
  nodeMessageCount.textContent = String(node.messages.length);
  nodeLastRole.textContent = getLastMessage(node)?.role || "Empty";
  renderNodeDetails(messageList, node.messages.slice(-2));
  editBox.hidden = false;
  editTitleInput.value = `${node.title} (Edited)`;
  editFeedback.textContent = "";
  renderMessageEditors(editMessageList, node.messages);
  updateFormState();
  updateWorkspaceSummary();
  renderGraphCanvas();
}

function toggleDetailPanel() {
  setDetailPanelCollapsed(workspaceShell.dataset.detailPanelCollapsed !== "true");
}

function handleWorkspaceKeydown(event) {
  if (isTypingTarget(event.target)) {
    if (event.key === "Escape" && workspaceHelpDialog.hidden === false) {
      setWorkspaceHelpOpen(false);
      event.preventDefault();
    }
    return;
  }

  if (event.key === "Escape" && workspaceHelpDialog.hidden === false) {
    setWorkspaceHelpOpen(false);
    event.preventDefault();
    return;
  }

  if (event.key === "?") {
    setWorkspaceHelpOpen(workspaceHelpDialog.hidden);
    event.preventDefault();
    return;
  }

  if (event.key === "i" || event.key === "I") {
    toggleDetailPanel();
    event.preventDefault();
    return;
  }

  if (event.key === "f" || event.key === "F") {
    viewport.fitToGraph();
    event.preventDefault();
    return;
  }

  if (event.key === "0") {
    viewport.resetZoom();
    event.preventDefault();
    return;
  }

  if (event.key === "+" || event.key === "=") {
    viewport.zoomIn();
    event.preventDefault();
    return;
  }

  if (event.key === "-") {
    viewport.zoomOut();
    event.preventDefault();
    return;
  }

  if ((event.key === "c" || event.key === "C") && !openChatLink.hidden && openChatLink.href) {
    window.location.href = openChatLink.href;
    event.preventDefault();
  }
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
    mergeNode(result.node);
    editFeedback.textContent = `Edited variant "${result.node.title}" created.`;
    updateSelection(result.node.id);
    viewport.centerOnBounds(getNodeBounds(result.node));
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
    mergeNode(result.node);
    nodeTitleInput.value = "";
    feedback.textContent = `Conversation node "${result.node.title}" created. Open it to chat.`;
    updateSelection(result.node.id);
    viewport.centerOnBounds(getNodeBounds(result.node));
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
detailPanelToggle.addEventListener("click", toggleDetailPanel);
detailPanelPeek.addEventListener("click", () => setDetailPanelCollapsed(false));
workspaceHelpToggle.addEventListener("click", () => setWorkspaceHelpOpen(workspaceHelpDialog.hidden));
workspaceHelpClose.addEventListener("click", () => setWorkspaceHelpOpen(false));
workspaceHelpBackdrop.addEventListener("click", () => setWorkspaceHelpOpen(false));
fitViewButton.addEventListener("click", () => viewport.fitToGraph());
zoomOutButton.addEventListener("click", () => viewport.zoomOut());
zoomInButton.addEventListener("click", () => viewport.zoomIn());
zoomResetButton.addEventListener("click", () => viewport.resetZoom());
window.addEventListener("keydown", handleWorkspaceKeydown);
syncModelOptions(providerInput, modelInput);
setWorkspaceHelpOpen(false);
setDetailPanelCollapsed(readStoredDetailPanelState());
renderGraphCanvas();
updateSelection(selectedNodeId);
updateWorkspaceSummary();
