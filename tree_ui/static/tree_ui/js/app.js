import { renderCanvas } from "./canvas.js";
import { renderNodeDetails } from "./node-panel.js";
import { getStreamingLabel } from "./streaming.js";

const payload = JSON.parse(document.getElementById("graph-payload").textContent);

const workspaceName = document.getElementById("workspace-name");
const nodeTitle = document.getElementById("node-title");
const nodeProvider = document.getElementById("node-provider");
const nodeModel = document.getElementById("node-model");
const nodeParent = document.getElementById("node-parent");
const nodeSummary = document.getElementById("node-summary");
const messageList = document.getElementById("message-list");
const streamingStatus = document.getElementById("streaming-status");

workspaceName.textContent = payload.workspace.name;

const nodesById = new Map(payload.nodes.map((node) => [String(node.id), node]));
let selectedNodeId = String(payload.nodes[0]?.id || "");

function updateSelection(nodeId) {
  selectedNodeId = String(nodeId);
  const node = nodesById.get(selectedNodeId);

  if (!node) {
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
  renderCanvas(payload.nodes, selectedNodeId, updateSelection);
}

renderCanvas(payload.nodes, selectedNodeId, updateSelection);
updateSelection(selectedNodeId);
