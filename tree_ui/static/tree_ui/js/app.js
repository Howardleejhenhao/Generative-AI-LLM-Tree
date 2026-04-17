import { postJSON } from "./api.js?v=20260322-graph-hint-fix";
import { getNodeBounds, renderCanvas } from "./canvas.js?v=20260413-image-badges";
import { syncModelOptions } from "./model-options.js?v=20260322-graph-hint-fix";
import { createViewportController } from "./viewport.js?v=20260322-graph-hint-fix";

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
const workspaceDeleteButton = document.getElementById("workspace-delete-button");
const nodeCompareButton = document.getElementById("node-compare-button");
const nodeRenameButton = document.getElementById("node-rename-button");
const nodeDeleteButton = document.getElementById("node-delete-button");
const fitViewButton = document.getElementById("graph-fit-view");
const zoomOutButton = document.getElementById("graph-zoom-out");
const zoomInButton = document.getElementById("graph-zoom-in");
const zoomResetButton = document.getElementById("graph-zoom-reset");
const zoomLevel = document.getElementById("graph-zoom-level");
const graphStage = document.getElementById("graph-stage");
const nodeChatUrlTemplate = document.getElementById("node-chat-url-template");
const nodeDeleteUrlTemplate = document.getElementById("node-delete-url-template");
const nodeTitleUpdateUrlTemplate = document.getElementById("node-title-update-url-template");
const compareNodesUrl = document.getElementById("compare-nodes-url").dataset.compareNodesUrl;
const compareDialog = document.getElementById("compare-dialog");
const compareDialogBackdrop = document.getElementById("compare-dialog-backdrop");
const compareDialogClose = document.getElementById("compare-dialog-close");
const compareDialogContent = document.getElementById("compare-dialog-content");
const formTarget = document.getElementById("form-target");
const feedback = document.getElementById("form-feedback");
const nodeForm = document.getElementById("node-form");
const workspaceCreateForm = document.getElementById("workspace-create-form");
const workspaceNameInput = document.getElementById("workspace-name-input");
const workspaceCreateButton = document.getElementById("workspace-create-button");
const workspaceCreateFeedback = document.getElementById("workspace-create-feedback");
const nodeTitleInput = document.getElementById("node-title-input");
const routingModeInput = document.getElementById("node-routing-mode-input");
const providerInput = document.getElementById("node-provider-input");
const modelInput = document.getElementById("node-model-input");
const modelLabel = document.getElementById("node-model-label");
const systemPromptInput = document.getElementById("node-system-prompt-input");
const temperatureInput = document.getElementById("node-temperature-input");
const topPInput = document.getElementById("node-top-p-input");
const maxOutputTokensInput = document.getElementById("node-max-output-tokens-input");
const submitButton = document.getElementById("node-submit-button");
const quickStartButtons = Array.from(document.querySelectorAll(".quick-start-button"));
const rootModeToggle = document.getElementById("root-mode-toggle");
const quickCreate = document.getElementById("graph-quick-create");
const quickCreateToggle = document.getElementById("graph-quick-create-toggle");
const quickCreatePanel = document.getElementById("graph-quick-create-panel");
const quickCreateLabel = document.getElementById("graph-quick-create-label");
const quickTitleInput = document.getElementById("quick-node-title-input");
const quickRoutingModeInput = document.getElementById("quick-node-routing-mode-input");
const quickProviderInput = document.getElementById("quick-node-provider-input");
const quickModelInput = document.getElementById("quick-node-model-input");
const quickModelLabel = document.getElementById("quick-node-model-label");
const quickSystemPromptInput = document.getElementById("quick-node-system-prompt-input");
const quickTemperatureInput = document.getElementById("quick-node-temperature-input");
const quickTopPInput = document.getElementById("quick-node-top-p-input");
const quickMaxOutputTokensInput = document.getElementById("quick-node-max-output-tokens-input");
const quickSubmitButton = document.getElementById("quick-node-submit-button");
const quickCancelButton = document.getElementById("graph-quick-create-cancel");
const quickFeedback = document.getElementById("quick-node-feedback");
const confirmDialog = document.getElementById("confirm-dialog");
const confirmDialogBackdrop = document.getElementById("confirm-dialog-backdrop");
const confirmDialogKicker = document.getElementById("confirm-dialog-kicker");
const confirmDialogTitle = document.getElementById("confirm-dialog-title");
const confirmDialogCopy = document.getElementById("confirm-dialog-copy");
const confirmDialogWarning = document.getElementById("confirm-dialog-warning");
const confirmDialogFeedback = document.getElementById("confirm-dialog-feedback");
const confirmDialogCancel = document.getElementById("confirm-dialog-cancel");
const confirmDialogConfirm = document.getElementById("confirm-dialog-confirm");
const csrfToken = document.getElementById("csrf-token").value;
let latestViewportState = null;
let activeLineageIds = new Set();
let matchedNodeIds = new Set(payload.nodes.map((node) => String(node.id)));
let pendingConfirmation = null;
let isCompareMode = false;

function handleViewportChange(viewportState) {
  latestViewportState = viewportState;
  zoomLevel.textContent = `${viewportState.percent}%`;
  fitViewButton.disabled = !viewportState.hasNodes || !viewportState.canFit;
  zoomOutButton.disabled = !viewportState.hasNodes || !viewportState.canZoomOut;
  zoomInButton.disabled = !viewportState.hasNodes || !viewportState.canZoomIn;
  zoomResetButton.disabled = !viewportState.hasNodes || viewportState.percent === 100;
  updateQuickCreatePosition();
}

const nodesById = new Map(payload.nodes.map((node) => [String(node.id), node]));
let selectedNodeId = String(payload.nodes[0]?.id || "");

const viewport = createViewportController({ onChange: handleViewportChange });

workspaceName.textContent = payload.workspace.name;

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
    return "Select node";
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
    workspaceSearchFeedback.innerHTML = "<kbd>/</kbd>";
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

function setCompareDialogOpen(isOpen) {
  compareDialog.hidden = !isOpen;
  compareDialog.setAttribute("aria-hidden", String(!isOpen));
}

function renderComparison(data) {
  const { node_a, node_b } = data;
  compareDialogContent.innerHTML = "";

  const createColumn = (node) => {
    const col = document.createElement("div");
    col.className = "compare-col";

    const header = document.createElement("div");
    header.className = "compare-node-header";
    const title = document.createElement("h3");
    title.textContent = node.title;
    const meta = document.createElement("p");
    meta.className = "panel-kicker";
    meta.textContent = `${node.provider} / ${node.model_name}`;
    header.append(title, meta);

    const stats = document.createElement("div");
    stats.className = "compare-stats";
    const addStat = (label, value) => {
      const row = document.createElement("div");
      row.className = "compare-stat";
      const l = document.createElement("label");
      l.textContent = `${label}:`;
      const v = document.createElement("span");
      v.textContent = value || "N/A";
      row.append(l, v);
      stats.appendChild(row);
    };

    addStat("Routing", node.routing_mode);
    addStat("Decision", node.routing_decision);
    addStat("Branch Depth", node.lineage.depth);
    addStat("Total Tools", node.lineage.total_tool_count);

    const retrievedMemories = (node.memories || []).filter((memory) => memory.is_retrieved);
    addStat("Retrieved Memory", `${retrievedMemories.length} / ${(node.memories || []).length}`);

    const summary = document.createElement("div");
    summary.className = "compare-summary";
    const summaryTitle = document.createElement("h4");
    summaryTitle.textContent = "Summary";
    const summaryText = document.createElement("p");
    summaryText.textContent = node.summary || "No summary available.";
    summary.append(summaryTitle, summaryText);

    const lineage = document.createElement("div");
    lineage.className = "compare-lineage";
    const lineageTitle = document.createElement("h4");
    lineageTitle.textContent = "Branch Lineage";
    const lineageList = document.createElement("ol");
    lineageList.className = "compare-lineage-list";
    for (const titleText of node.lineage.titles || []) {
      const item = document.createElement("li");
      item.textContent = titleText;
      lineageList.appendChild(item);
    }
    if (!lineageList.children.length) {
      const item = document.createElement("li");
      item.textContent = "No lineage available.";
      lineageList.appendChild(item);
    }
    lineage.append(lineageTitle, lineageList);

    const memorySection = document.createElement("div");
    memorySection.className = "compare-memory";
    const memoryTitle = document.createElement("h4");
    memoryTitle.textContent = "Retrieved Memory";
    memorySection.appendChild(memoryTitle);

    if (retrievedMemories.length) {
      const memoryList = document.createElement("ul");
      memoryList.className = "compare-memory-list";
      for (const memory of retrievedMemories) {
        const item = document.createElement("li");
        const label = document.createElement("strong");
        label.textContent = `${memory.scope} / ${memory.memory_type}`;
        const text = document.createElement("span");
        const titlePrefix = memory.title ? `${memory.title}: ` : "";
        text.textContent = `${titlePrefix}${memory.content}`;
        item.append(label, text);
        memoryList.appendChild(item);
      }
      memorySection.appendChild(memoryList);
    } else {
      const emptyMemory = document.createElement("p");
      emptyMemory.className = "compare-empty-copy";
      emptyMemory.textContent = "No retrieved memory for this node.";
      memorySection.appendChild(emptyMemory);
    }

    const assistantMsgs = node.messages.filter(m => m.role === "assistant");
    if (assistantMsgs.length > 0) {
        const lastMsg = assistantMsgs[assistantMsgs.length - 1];
        const msgDiv = document.createElement("div");
        msgDiv.className = "compare-last-message";
        const msgTitle = document.createElement("h4");
        msgTitle.textContent = "Latest Assistant Output";
        const msgBody = document.createElement("div");
        msgBody.className = "compare-message-body";
        msgBody.textContent = lastMsg.content.slice(0, 500) + (lastMsg.content.length > 500 ? "..." : "");
        msgDiv.append(msgTitle, msgBody);
        col.append(header, stats, summary, lineage, memorySection, msgDiv);
    } else {
        col.append(header, stats, summary, lineage, memorySection);
    }

    return col;
  };

  const grid = document.createElement("div");
  grid.className = "compare-grid";
  grid.append(createColumn(node_a), createColumn(node_b));
  compareDialogContent.append(grid);
}

function updateWorkspaceSummary() {
  const nodeCount = payload.nodes.length;
  const selectedNode = getSelectedNode();
  const lineageIds = getLineageIds(selectedNode);

  workspaceNodePill.textContent = `${nodeCount} ${nodeCount === 1 ? "node" : "nodes"}`;
  workspaceSelectionTitle.textContent = selectedNode ? selectedNode.title : "No node selected";
  workspaceSelectionSummary.textContent = getSelectionSummaryText(selectedNode);

  let selectionTypeText = "New root";
  if (selectedNode) {
    const providerLabel = getProviderLabel(selectedNode.provider);
    const routingPrefix =
      selectedNode.routing_mode && selectedNode.routing_mode !== "manual"
        ? `Auto (${selectedNode.routing_mode}) / `
        : "";
    selectionTypeText = `${routingPrefix}${providerLabel} / ${selectedNode.model_name}`;

    if (selectedNode.routing_decision) {
      workspaceSelectionSummary.textContent += ` Routing decision: ${selectedNode.routing_decision}`;
    }
  }

  workspaceSelectionType.textContent = selectionTypeText;
  workspaceSelectionDepth.textContent = `Depth ${lineageIds.length}`;
  nodeCompareButton.disabled = !selectedNode || nodeCount < 2;
  nodeRenameButton.disabled = !selectedNode;
  nodeDeleteButton.disabled = !selectedNode;
}

function getNodeChatUrl(nodeId) {
  return nodeChatUrlTemplate.dataset.nodeChatUrlTemplate.replace("999999", String(nodeId));
}

function getNodeDeleteUrl(nodeId) {
  return nodeDeleteUrlTemplate.dataset.nodeDeleteUrlTemplate.replace("999999", String(nodeId));
}

function getNodeTitleUpdateUrl(nodeId) {
  return nodeTitleUpdateUrlTemplate.dataset.nodeTitleUpdateUrlTemplate.replace("999999", String(nodeId));
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

function getSubtreeNodeIds(rootNodeId) {
  const subtreeIds = [];
  const stack = [String(rootNodeId)];

  while (stack.length) {
    const currentId = stack.pop();
    subtreeIds.push(currentId);

    for (const node of payload.nodes) {
      if (String(node.parent_id) === currentId) {
        stack.push(String(node.id));
      }
    }
  }

  return subtreeIds;
}

function setConfirmDialogOpen(isOpen) {
  confirmDialog.hidden = !isOpen;
  confirmDialog.setAttribute("aria-hidden", String(!isOpen));
}

function renderConfirmationDialog() {
  if (!pendingConfirmation) {
    confirmDialogFeedback.textContent = "";
    confirmDialogWarning.textContent = "";
    return;
  }

  confirmDialogKicker.textContent = pendingConfirmation.kicker;
  confirmDialogTitle.textContent = pendingConfirmation.title;
  confirmDialogCopy.textContent = pendingConfirmation.copy;
  confirmDialogWarning.textContent = pendingConfirmation.warning || "";
  confirmDialogFeedback.textContent = "";
  confirmDialogConfirm.textContent = pendingConfirmation.confirmLabel;
}

function openConfirmationDialog(config) {
  pendingConfirmation = config;
  renderConfirmationDialog();
  setWorkspaceHelpOpen(false);
  setConfirmDialogOpen(true);
}

function closeConfirmationDialog() {
  pendingConfirmation = null;
  confirmDialogFeedback.textContent = "";
  confirmDialogWarning.textContent = "";
  confirmDialogCancel.disabled = false;
  confirmDialogConfirm.disabled = false;
  setConfirmDialogOpen(false);
}

function removeNodesFromGraph(deletedNodeIds) {
  const deletedIdSet = new Set(deletedNodeIds.map((id) => String(id)));
  payload.nodes = payload.nodes.filter((node) => !deletedIdSet.has(String(node.id)));
  for (const nodeId of deletedIdSet) {
    nodesById.delete(nodeId);
  }

  activeLineageIds = new Set([...activeLineageIds].filter((id) => !deletedIdSet.has(id)));
  matchedNodeIds = new Set([...matchedNodeIds].filter((id) => !deletedIdSet.has(id)));
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
  const nodeHeight = (bounds.maxY - bounds.minY) * zoom;
  const preferredLeft = screenLeft + nodeWidth + 12;
  const panelWidth = quickCreate.dataset.open === "true" ? 320 : 58;
  const panelHeight = quickCreate.dataset.open === "true" ? 420 : 58;
  const safeLeft = preferredLeft + panelWidth > stageWidth - 16
    ? Math.max(16, screenLeft - panelWidth - 10)
    : preferredLeft;
  const safeTop = Math.min(
    Math.max(16, screenTop + (nodeHeight / 2) - (panelHeight / 2)),
    Math.max(16, stageHeight - panelHeight - 16),
  );

  quickCreate.style.left = `${safeLeft}px`;
  quickCreate.style.top = `${safeTop}px`;
}

function syncQuickCreateDefaults() {
  quickRoutingModeInput.value = routingModeInput.value;
  updateRoutingModeVisibility();
  quickProviderInput.value = providerInput.value;
  syncModelOptions(quickProviderInput, quickModelInput);
  if (modelOptionsMatchDock()) {
    quickModelInput.value = modelInput.value;
  }
  quickSystemPromptInput.value = systemPromptInput.value;
  quickTemperatureInput.value = temperatureInput.value;
  quickTopPInput.value = topPInput.value;
  quickMaxOutputTokensInput.value = maxOutputTokensInput.value;
}

function modelOptionsMatchDock() {
  return Array.from(quickModelInput.options).some((option) => option.value === modelInput.value);
}

function isRootModeEnabled() {
  return rootModeToggle.checked;
}

function readOptionalNumberValue(input, parser = Number) {
  const rawValue = input.value.trim();
  if (!rawValue) {
    return null;
  }
  return parser(rawValue);
}

function readOptionalIntegerValue(input) {
  return readOptionalNumberValue(input, Number);
}

function buildNodeConfigPayload({
  systemPromptValue,
  temperatureValue,
  topPValue,
  maxOutputTokensValue,
}) {
  return {
    system_prompt: systemPromptValue.value.trim(),
    temperature: readOptionalNumberValue(temperatureValue),
    top_p: readOptionalNumberValue(topPValue),
    max_output_tokens: readOptionalIntegerValue(maxOutputTokensValue),
  };
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
  selectedNodeId = "";
  activeLineageIds = new Set();
  quickCreate.hidden = true;
  setQuickCreateOpen(false);
  updateWorkspaceSummary();
}

function updateSelection(nodeId) {
  if (isCompareMode && selectedNodeId && String(nodeId) !== selectedNodeId) {
    performComparison(selectedNodeId, nodeId);
    return;
  }

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
    if (event.key === "Escape" && confirmDialog.hidden === false) {
      closeConfirmationDialog();
      event.preventDefault();
    }
    if (event.key === "Escape" && workspaceHelpDialog.hidden === false) {
      setWorkspaceHelpOpen(false);
      event.preventDefault();
    }
    return;
  }

  if (event.key === "Escape" && confirmDialog.hidden === false) {
    closeConfirmationDialog();
    event.preventDefault();
    return;
  }

  if (confirmDialog.hidden === false) {
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

async function createNodeRequest({
  parentId,
  title,
  provider,
  modelName,
  routingMode,
  systemPrompt,
  temperature,
  topP,
  maxOutputTokens,
}) {
  return postJSON(
    nodeForm.dataset.nodeCreateUrl,
    {
      parent_id: parentId,
      title,
      provider,
      model_name: modelName,
      routing_mode: routingMode,
      system_prompt: systemPrompt,
      temperature,
      top_p: topP,
      max_output_tokens: maxOutputTokens,
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
      routingMode: routingModeInput.value,
      ...buildNodeConfigPayload({
        systemPromptValue: systemPromptInput,
        temperatureValue: temperatureInput,
        topPValue: topPInput,
        maxOutputTokensValue: maxOutputTokensInput,
      }),
    });
    mergeNode(result.node);
    updateSearchState();
    nodeTitleInput.value = "";
    systemPromptInput.value = "";
    temperatureInput.value = "";
    topPInput.value = "";
    maxOutputTokensInput.value = "";
    syncQuickCreateDefaults();
    feedback.textContent = `Added ${result.node.title}.`;
    updateSelection(result.node.id);
    viewport.centerOnBounds(getNodeBounds(result.node));
  } catch (error) {
    feedback.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function handleWorkspaceDelete() {
  const nodeCount = payload.nodes.length;
  const nodeLabel = `${nodeCount} ${nodeCount === 1 ? "node" : "nodes"}`;
  openConfirmationDialog({
    kicker: "Delete Workspace",
    confirmLabel: "Delete workspace",
    title: `Delete ${payload.workspace.name}?`,
    copy: `This will remove the entire workspace and its ${nodeLabel}.`,
    warning: "This cannot be undone. You will be redirected after deletion.",
    onConfirm: async () => {
      const result = await postJSON(
        workspaceDeleteButton.dataset.deleteWorkspaceUrl,
        { confirm: true },
        csrfToken,
      );
      window.location.href = result.redirect_url;
    },
  });
}

async function performComparison(nodeIdA, nodeIdB) {
  graphStatus.textContent = "Comparing branches...";
  try {
    const data = await postJSON(
      compareNodesUrl,
      {
        node_id_a: nodeIdA,
        node_id_b: nodeIdB,
      },
      csrfToken,
    );
    renderComparison(data);
    setCompareDialogOpen(true);
  } catch (error) {
    graphStatus.textContent = `Comparison failed: ${error.message}`;
  } finally {
    isCompareMode = false;
    nodeCompareButton.textContent = "Compare";
    nodeCompareButton.classList.remove("detail-toggle-button-active");
    updateWorkspaceSummary();
  }
}

function handleNodeCompare() {
  if (isCompareMode) {
    isCompareMode = false;
    nodeCompareButton.textContent = "Compare";
    nodeCompareButton.classList.remove("detail-toggle-button-active");
  } else {
    const selectedNode = getSelectedNode();
    if (!selectedNode) {
      return;
    }
    isCompareMode = true;
    nodeCompareButton.textContent = "Select node to compare...";
    nodeCompareButton.classList.add("detail-toggle-button-active");
    graphStatus.textContent = "Select another node in the graph to compare with the current selection.";
  }
}

async function handleNodeRename() {
  const selectedNode = getSelectedNode();
  if (!selectedNode) {
    feedback.textContent = "Select a node first.";
    return;
  }

  const requestedTitle = window.prompt("Rename node", selectedNode.title);
  if (requestedTitle === null) {
    return;
  }

  feedback.textContent = "";
  nodeRenameButton.disabled = true;

  try {
    const result = await postJSON(
      getNodeTitleUpdateUrl(selectedNode.id),
      { title: requestedTitle },
      csrfToken,
    );
    mergeNode(result.node);
    updateSearchState();
    updateSelection(result.node.id);
    feedback.textContent = `Renamed node to ${result.node.title}.`;
  } catch (error) {
    feedback.textContent = error.message;
  } finally {
    nodeRenameButton.disabled = !getSelectedNode();
  }
}

function handleNodeDelete() {
  const selectedNode = getSelectedNode();
  if (!selectedNode) {
    feedback.textContent = "Select a node first.";
    return;
  }

  const subtreeIds = getSubtreeNodeIds(selectedNode.id);
  const descendantCount = Math.max(0, subtreeIds.length - 1);
  const subtreeLabel = `${subtreeIds.length} ${subtreeIds.length === 1 ? "node" : "nodes"}`;
  const descendantWarning = descendantCount === 0
    ? "This node is a leaf."
    : `This will also remove ${descendantCount} descendant ${descendantCount === 1 ? "node" : "nodes"}.`;

  openConfirmationDialog({
    kicker: "Delete Node",
    confirmLabel: descendantCount > 0 ? `Delete ${subtreeLabel}` : "Delete node",
    title: `Delete ${selectedNode.title}?`,
    copy: descendantCount > 0
      ? `This action will remove "${selectedNode.title}" and every branch below it.`
      : `This action will remove leaf node "${selectedNode.title}" from the current workspace.`,
    warning: `${descendantWarning} This cannot be undone.`,
    onConfirm: async () => {
      const fallbackSelectionId = selectedNode.parent_id
        ? String(selectedNode.parent_id)
        : String(payload.nodes.find((node) => !subtreeIds.includes(String(node.id)))?.id || "");
      const result = await postJSON(
        getNodeDeleteUrl(selectedNode.id),
        { confirm: true },
        csrfToken,
      );
      removeNodesFromGraph(result.deleted_node_ids);
      feedback.textContent = `Deleted ${result.deleted_count} ${result.deleted_count === 1 ? "node" : "nodes"}.`;
      updateSearchState();

      if (nodesById.has(fallbackSelectionId)) {
        updateSelection(fallbackSelectionId);
        return;
      }

      if (payload.nodes[0]) {
        updateSelection(payload.nodes[0].id);
        return;
      }

      showEmptyNodeState();
      updateFormState();
      renderGraphCanvas();
    },
  });
}

async function handleConfirmationFinal() {
  if (!pendingConfirmation) {
    return;
  }

  confirmDialogCancel.disabled = true;
  confirmDialogConfirm.disabled = true;
  confirmDialogFeedback.textContent = "";

  try {
    await pendingConfirmation.onConfirm();
    closeConfirmationDialog();
  } catch (error) {
    confirmDialogFeedback.textContent = error.message;
    confirmDialogCancel.disabled = false;
    confirmDialogSecondary.disabled = false;
    confirmDialogConfirm.disabled = false;
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
      routingMode: quickRoutingModeInput.value,
      ...buildNodeConfigPayload({
        systemPromptValue: quickSystemPromptInput,
        temperatureValue: quickTemperatureInput,
        topPValue: quickTopPInput,
        maxOutputTokensValue: quickMaxOutputTokensInput,
      }),
    });
    mergeNode(result.node);
    quickTitleInput.value = "";
    quickSystemPromptInput.value = "";
    quickTemperatureInput.value = "";
    quickTopPInput.value = "";
    quickMaxOutputTokensInput.value = "";
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
systemPromptInput.addEventListener("input", syncQuickCreateDefaults);
temperatureInput.addEventListener("input", syncQuickCreateDefaults);
topPInput.addEventListener("input", syncQuickCreateDefaults);
maxOutputTokensInput.addEventListener("input", syncQuickCreateDefaults);
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
workspaceDeleteButton.addEventListener("click", handleWorkspaceDelete);
nodeCompareButton.addEventListener("click", handleNodeCompare);
nodeRenameButton.addEventListener("click", handleNodeRename);
nodeDeleteButton.addEventListener("click", handleNodeDelete);
confirmDialogCancel.addEventListener("click", closeConfirmationDialog);
confirmDialogBackdrop.addEventListener("click", closeConfirmationDialog);
confirmDialogConfirm.addEventListener("click", handleConfirmationFinal);
compareDialogClose.addEventListener("click", () => setCompareDialogOpen(false));
compareDialogBackdrop.addEventListener("click", () => setCompareDialogOpen(false));
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
setConfirmDialogOpen(false);
updateSearchState();
updateSelection(selectedNodeId);
updateWorkspaceSummary();

function updateRoutingModeVisibility() {
  const isManual = routingModeInput.value === "manual";
  if (modelLabel) modelLabel.hidden = !isManual;

  const isQuickManual = quickRoutingModeInput.value === "manual";
  if (quickModelLabel) quickModelLabel.hidden = !isQuickManual;
}

routingModeInput.addEventListener("change", updateRoutingModeVisibility);
quickRoutingModeInput.addEventListener("change", updateRoutingModeVisibility);
updateRoutingModeVisibility();
