function createNodeCard(node, isSelected, onSelect) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "graph-node";
  button.dataset.provider = node.provider;
  button.dataset.selected = String(isSelected);
  button.style.left = `${node.position.x}px`;
  button.style.top = `${node.position.y}px`;
  button.innerHTML = `
    <span class="graph-node-title">${node.title}</span>
    <span class="graph-node-meta">${node.provider} / ${node.model_name}</span>
    <span class="graph-node-summary">${node.summary || "No summary"}</span>
  `;
  button.addEventListener("click", () => onSelect(node.id));
  return button;
}

function drawEdge(svg, fromNode, toNode) {
  const startX = fromNode.position.x + 264;
  const startY = fromNode.position.y + 70;
  const endX = toNode.position.x;
  const endY = toNode.position.y + 70;
  const curveOffset = Math.max((endX - startX) / 2, 40);

  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute(
    "d",
    `M ${startX} ${startY} C ${startX + curveOffset} ${startY}, ${endX - curveOffset} ${endY}, ${endX} ${endY}`,
  );
  path.setAttribute("class", "graph-edge");
  svg.appendChild(path);
}

export function renderCanvas(nodes, selectedNodeId, onSelect) {
  const nodeLayer = document.getElementById("graph-nodes");
  const edgeLayer = document.getElementById("graph-edges");
  const emptyState = document.getElementById("graph-empty");
  nodeLayer.innerHTML = "";
  edgeLayer.innerHTML = "";
  emptyState.hidden = nodes.length > 0;

  const nodesById = new Map(nodes.map((node) => [String(node.id), node]));
  for (const node of nodes) {
    const card = createNodeCard(node, String(node.id) === String(selectedNodeId), onSelect);
    nodeLayer.appendChild(card);

    if (node.parent_id !== null && node.parent_id !== undefined) {
      const parentNode = nodesById.get(String(node.parent_id));
      if (parentNode) {
        drawEdge(edgeLayer, parentNode, node);
      }
    }
  }
}
