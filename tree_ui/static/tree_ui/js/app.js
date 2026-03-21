import { postJSON } from "./api.js?v=20260321-quick-child";
import { getNodeBounds, renderCanvas } from "./canvas.js?v=20260321-quick-child";
import { createMinimapController } from "./minimap.js?v=20260321-quick-child";
import { syncModelOptions } from "./model-options.js?v=20260321-quick-child";
import { createViewportController } from "./viewport.js?v=20260321-quick-child";

const payload = JSON.parse(document.getElementById("graph-payload").textContent);
const workspaceName = document.getElementById("workspace-name");
const workspaceNodePill = document.getElementById("workspace-node-pill");
const workspaceSearchInput = document.getElementById("workspace-search-input");
const workspaceSearchProvider = document.getElementById("workspace-search-provider");
const workspaceSearchFeedback = document.getElementById("workspace-search-feedback");
const workspaceSearchResults = document.getElementById("workspace-search-results");
const workspaceSelectionTitle = document.getElementById("workspace-selection-title");
const workspaceSelectionSummary = document.getElementById("workspace-selection-summary");
const workspaceSelectionType = document.getElementById("workspace-selection-type");
const workspaceSelectionDepth = document.getElementById("workspace-selection-depth");
const graphStatus = document.getElementById("graph-status");
const workspaceHelpToggle = document.getElementById("workspace-help-toggle");
const workspaceHelpDialog = document.getElementById("workspace-help-dialog");
const workspaceHelpBackdrop = document.getElementById("workspace-help-backdrop");
const workspaceHelpClose = document.getElementById("workspace-help-close");
const fitViewButton = document.getElementById("graph-fit-view");
const zoomOutButton = document.getElementById("graph-zoom-out");
const zoomInButton = document.getElementById("graph-zoom-in");
const zoomResetButton = document.getElementById("graph-zoom-reset");
const zoomLevel = document.getElementById("graph-zoom-level");
const graphStage = document.getElementById("graph-stage");
const nodeChatUrlTemplate = document.getElementById("node-chat-url-template");
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
const quickStartButtons = Array.from(document.querySelectorAll(".quick-start-button"));
const rootModeToggle = document.getElementById("root-mode-toggle");
const quickCreate = document.getElementById("graph-quick-create");
const quickCreateToggle = document.getElementById("graph-quick-create-toggle");
const quickCreatePanel = document.getElementById("graph-quick-create-panel");
const quickCreateLabel = document.getElementById("graph-quick-create-label");
const quickTitleInput = document.getElementById("quick-node-title-input");
const quickProviderInput = document.getElementById("quick-node-provider-input");
const quickModelInput = document.getElementById("quick-node-model-input");
const quickSubmitButton = document.getElementById("quick-node-submit-button");
const quickCancelButton = document.getElementById("graph-quick-create-cancel");
const quickFeedback = document.getElementById("quick-node-feedback");
const csrfToken = document.getElementById("csrf-token").value;
let latestViewportState = null;
let minimap = null;
let activeLineageIds = new Set();
let matchedNodeIds = new Set(payload.nodes.map((node) => String(node.id)));

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
  updateQuickCreatePosition();
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

function getNodeSearchText(node) {
  return [
    node.title,
    node.summary,
    node.provider,
    node.model_name,
    ...node.messages.map((message) => `${message.role} ${message.content}`),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function isSearchActive() {
  return workspaceSearchInput.value.trim() !== "" || workspaceSearchProvider.value !== "all";
}

function getRootNodeCount() {
  return payload.nodes.filter((node) => node.parent_id === null || node.parent_id === undefined).length;
}

function getTotalMessageCount() {
  return payload.nodes.reduce((total, node) => total + node.messages.length, 0);
}

function getNodeTitleById(nodeId) {
  if (!nodeId) {
    return "";
  }

  return nodesById.get(String(nodeId))?.title || `Node ${nodeId}`;
}

function getProviderLabel(provider) {
  if (provider === "openai") {
    return "OpenAI";
  }
  if (provider === "gemini") {
    return "Gemini";
  }
  return provider || "Unknown";
}

function getSelectionSummaryText(node) {
  if (!node) {
    return "Select a node or start a root.";
  }

  if (node.edited_from_id) {
    return `Edited from ${getNodeTitleById(node.edited_from_id)}.`;
  }
  if (node.parent_id) {
    return `Child of ${getNodeTitleById(node.parent_id)}.`;
  }
  return "Root conversation.";
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

function buildSearchMatches() {
  const query = workspaceSearchInput.value.trim().toLowerCase();
  const provider = workspaceSearchProvider.value;

  return payload.nodes.filter((node) => {
    const providerMatches = provider === "all" || node.provider === provider;
    if (!providerMatches) {
      return false;
    }
    if (!query) {
      return true;
    }
    return getNodeSearchText(node).includes(query);
  });
}

function renderSearchResults(matches) {
  workspaceSearchResults.innerHTML = "";

  if (!isSearchActive()) {
    workspaceSearchResults.hidden = true;
    workspaceSearchFeedback.innerHTML = "<kbd>/</kbd> search";
    return;
  }

  workspaceSearchResults.hidden = false;

  if (!matches.length) {
    workspaceSearchFeedback.textContent = "No nodes match the current search.";
    return;
  }

  workspaceSearchFeedback.textContent = `${matches.length} matching ${matches.length === 1 ? "node" : "nodes"}.`;

  for (const node of matches.slice(0, 6)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "workspace-search-result";

    const title = document.createElement("span");
    title.className = "workspace-search-result-title";
    title.textContent = node.title;

    const meta = document.createElement("span");
    meta.className = "workspace-search-result-meta";
    meta.textContent = `${node.provider} / ${node.model_name}`;

    button.append(title, meta);
    button.addEventListener("click", () => {
      updateSelection(node.id);
      viewport.centerOnBounds(getNodeBounds(node));
    });
    workspaceSearchResults.appendChild(button);
  }
}

function updateSearchState() {
  const matches = buildSearchMatches();
  matchedNodeIds = new Set(matches.map((node) => String(node.id)));
  renderSearchResults(matches);
  renderGraphCanvas();
}

function updateWorkspaceSummary() {
  const nodeCount = payload.nodes.length;
  const selectedNode = getSelectedNode();
  const lineageIds = getLineageIds(selectedNode);

  workspaceNodePill.textContent = `${nodeCount} ${nodeCount === 1 ? "node" : "nodes"}`;
  workspaceSelectionTitle.textContent = selectedNode ? selectedNode.title : "No node selected";
  workspaceSelectionSummary.textContent = getSelectionSummaryText(selectedNode);
  workspaceSelectionType.textContent = selectedNode
    ? `${getProviderLabel(selectedNode.provider)} / ${selectedNode.model_name}`
    : "New root";
  workspaceSelectionDepth.textContent = `Depth ${lineageIds.length}`;
}

function getNodeChatUrl(nodeId) {
  return nodeChatUrlTemplate.dataset.nodeChatUrlTemplate.replace("999999", String(nodeId));
}

function openNodeChat(nodeId) {
  if (!nodeId) {
    return;
  }
  window.location.href = getNodeChatUrl(nodeId);
}

function getNodePositionUrl(nodeId) {
  return graphStatus.dataset.nodePositionUrlTemplate.replace("999999", String(nodeId));
}

function setQuickCreateOpen(isOpen) {
  const selectedNode = getSelectedNode();
  const shouldOpen = Boolean(isOpen && selectedNode);
  quickCreate.dataset.open = String(shouldOpen);
  quickCreatePanel.hidden = !shouldOpen;
  quickCreateToggle.setAttribute("aria-expanded", String(shouldOpen));
  quickFeedback.textContent = "";
  if (shouldOpen) {
    quickCreateLabel.textContent = `Child of ${selectedNode.title}`;
    window.requestAnimationFrame(() => quickTitleInput.focus());
  }
}

function updateQuickCreatePosition() {
  const selectedNode = getSelectedNode();
  if (!selectedNode || !latestViewportState?.hasNodes) {
    quickCreate.hidden = true;
    setQuickCreateOpen(false);
    return;
  }

  quickCreate.hidden = false;
  const stageWidth = graphStage.clientWidth;
  const stageHeight = graphStage.clientHeight;
  const bounds = getNodeBounds(selectedNode);
  const zoom = latestViewportState.zoom || 1;
  const screenLeft = (bounds.minX - latestViewportState.visibleBounds.minX) * zoom;
  const screenTop = (bounds.minY - latestViewportState.visibleBounds.minY) * zoom;
  const nodeWidth = (bounds.maxX - bounds.minX) * zoom;
  const preferredLeft = screenLeft + nodeWidth + 18;
  const panelWidth = quickCreate.dataset.open === "true" ? 304 : 52;
  const safeLeft = preferredLeft + panelWidth > stageWidth - 16
    ? Math.max(16, screenLeft - panelWidth - 18)
    : preferredLeft;
  const safeTop = Math.min(
    Math.max(16, screenTop + (22 * zoom)),
    Math.max(16, stageHeight - (quickCreate.dataset.open === "true" ? 220 : 72)),
  );

  quickCreate.style.left = `${safeLeft}px`;
  quickCreate.style.top = `${safeTop}px`;
}

function syncQuickCreateDefaults() {
  quickProviderInput.value = providerInput.value;
  syncModelOptions(quickProviderInput, quickModelInput);
  if (modelOptionsMatchDock()) {
    quickModelInput.value = modelInput.value;
  }
}

function modelOptionsMatchDock() {
  return Array.from(quickModelInput.options).some((option) => option.value === modelInput.value);
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
  updateQuickCreatePosition();
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
    matchedNodeIds,
    onSelect: updateSelection,
    onOpenChat: openNodeChat,
    onPositionCommit: handleNodePositionCommit,
    onMetricsChange: handleCanvasMetricsChange,
    getViewportScale: () => viewport.getScale(),
  });
}

function updateFormState() {
  const selectedNode = getSelectedNode();
  if (isRootModeEnabled() || !selectedNode) {
    formTarget.textContent = "Root";
    submitButton.textContent = "Add root";
    return;
  }

  formTarget.textContent = `Child of ${selectedNode.title}`;
  submitButton.textContent = "Add child";
}

function showEmptyNodeState() {
  activeLineageIds = new Set();
  quickCreate.hidden = true;
  setQuickCreateOpen(false);
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
  setQuickCreateOpen(false);
  syncQuickCreateDefaults();
  updateFormState();
  updateWorkspaceSummary();
  renderGraphCanvas();
  updateQuickCreatePosition();
}

function applyQuickStart(button) {
  const { modelName, provider, rootMode, title } = button.dataset;
  nodeTitleInput.value = title || "";
  providerInput.value = provider || providerInput.value;
  syncModelOptions(providerInput, modelInput);
  if (modelName) {
    modelInput.value = modelName;
  }
  rootModeToggle.checked = rootMode === "true";
  updateFormState();
  feedback.textContent = title
    ? `Loaded ${title}.`
    : "Preset loaded.";
  nodeTitleInput.focus();
  nodeTitleInput.select();
}

function handleWorkspaceKeydown(event) {
  if (isTypingTarget(event.target)) {
    if (event.key === "Escape" && workspaceHelpDialog.hidden === false) {
      setWorkspaceHelpOpen(false);
      event.preventDefault();
    }
    return;
  }

  if (event.key === "/") {
    workspaceSearchInput.focus();
    workspaceSearchInput.select();
    event.preventDefault();
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

  if ((event.key === "c" || event.key === "C") && getSelectedNode()) {
    openNodeChat(getSelectedNode()?.id);
    event.preventDefault();
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

async function createNodeRequest({ parentId, title, provider, modelName }) {
  return postJSON(
    nodeForm.dataset.nodeCreateUrl,
    {
      parent_id: parentId,
      title,
      provider,
      model_name: modelName,
    },
    csrfToken,
  );
}

async function handleNodeSubmit(event) {
  event.preventDefault();
  feedback.textContent = "";
  submitButton.disabled = true;

  try {
    const result = await createNodeRequest({
      parentId: isRootModeEnabled() ? null : getSelectedNode()?.id ?? null,
      title: nodeTitleInput.value,
      provider: providerInput.value,
      modelName: modelInput.value,
    });
    mergeNode(result.node);
    updateSearchState();
    nodeTitleInput.value = "";
    feedback.textContent = `Added ${result.node.title}.`;
    updateSelection(result.node.id);
    viewport.centerOnBounds(getNodeBounds(result.node));
  } catch (error) {
    feedback.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function toggleQuickCreate() {
  setQuickCreateOpen(quickCreate.dataset.open !== "true");
  updateQuickCreatePosition();
}

async function handleQuickCreateSubmit(event) {
  event.preventDefault();
  const selectedNode = getSelectedNode();
  if (!selectedNode) {
    quickFeedback.textContent = "Select a node first.";
    return;
  }

  quickFeedback.textContent = "";
  quickSubmitButton.disabled = true;

  try {
    const result = await createNodeRequest({
      parentId: selectedNode.id,
      title: quickTitleInput.value,
      provider: quickProviderInput.value,
      modelName: quickModelInput.value,
    });
    mergeNode(result.node);
    quickTitleInput.value = "";
    setQuickCreateOpen(false);
    updateSearchState();
    feedback.textContent = `Added ${result.node.title}.`;
    updateSelection(result.node.id);
    viewport.centerOnBounds(getNodeBounds(result.node));
  } catch (error) {
    quickFeedback.textContent = error.message;
  } finally {
    quickSubmitButton.disabled = false;
  }
}

providerInput.addEventListener("change", () => syncModelOptions(providerInput, modelInput));
providerInput.addEventListener("change", syncQuickCreateDefaults);
modelInput.addEventListener("change", syncQuickCreateDefaults);
quickProviderInput.addEventListener("change", () => syncModelOptions(quickProviderInput, quickModelInput));
rootModeToggle.addEventListener("change", updateFormState);
nodeForm.addEventListener("submit", handleNodeSubmit);
quickCreateToggle.addEventListener("click", toggleQuickCreate);
quickCreatePanel.addEventListener("submit", handleQuickCreateSubmit);
quickCancelButton.addEventListener("click", () => setQuickCreateOpen(false));
workspaceCreateForm.addEventListener("submit", handleWorkspaceCreateSubmit);
workspaceHelpToggle.addEventListener("click", () => setWorkspaceHelpOpen(workspaceHelpDialog.hidden));
workspaceHelpClose.addEventListener("click", () => setWorkspaceHelpOpen(false));
workspaceHelpBackdrop.addEventListener("click", () => setWorkspaceHelpOpen(false));
fitViewButton.addEventListener("click", () => viewport.fitToGraph());
zoomOutButton.addEventListener("click", () => viewport.zoomOut());
zoomInButton.addEventListener("click", () => viewport.zoomIn());
zoomResetButton.addEventListener("click", () => viewport.resetZoom());
workspaceSearchInput.addEventListener("input", updateSearchState);
workspaceSearchProvider.addEventListener("change", updateSearchState);
for (const button of quickStartButtons) {
  button.addEventListener("click", () => applyQuickStart(button));
}
window.addEventListener("keydown", handleWorkspaceKeydown);
syncModelOptions(providerInput, modelInput);
syncQuickCreateDefaults();
setWorkspaceHelpOpen(false);
updateSearchState();
updateSelection(selectedNodeId);
updateWorkspaceSummary();
