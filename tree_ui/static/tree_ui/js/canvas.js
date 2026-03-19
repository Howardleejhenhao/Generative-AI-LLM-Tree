const NODE_WIDTH = 264;
const NODE_FOOTPRINT_WIDTH = 320;
const NODE_FOOTPRINT_HEIGHT = 180;
const NODE_MIDPOINT_Y = 70;
const DRAG_THRESHOLD = 6;

function drawEdge(svg, fromNode, toNode) {
  const startX = fromNode.position.x + NODE_WIDTH;
  const startY = fromNode.position.y + NODE_MIDPOINT_Y;
  const endX = toNode.position.x;
  const endY = toNode.position.y + NODE_MIDPOINT_Y;
  const curveOffset = Math.max((endX - startX) / 2, 40);

  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute(
    "d",
    `M ${startX} ${startY} C ${startX + curveOffset} ${startY}, ${endX - curveOffset} ${endY}, ${endX} ${endY}`,
  );
  path.setAttribute("class", "graph-edge");
  svg.appendChild(path);
}

function buildCanvasMetrics(nodes) {
  if (nodes.length === 0) {
    return {
      width: 1600,
      height: 1200,
    };
  }

  let maxX = 0;
  let maxY = 0;
  for (const node of nodes) {
    maxX = Math.max(maxX, node.position.x + NODE_FOOTPRINT_WIDTH);
    maxY = Math.max(maxY, node.position.y + NODE_FOOTPRINT_HEIGHT);
  }

  return {
    width: Math.max(1600, maxX + 220),
    height: Math.max(1200, maxY + 220),
  };
}

function applyNodePosition(card, node) {
  card.style.left = `${node.position.x}px`;
  card.style.top = `${node.position.y}px`;
}

export function renderCanvas(nodes, selectedNodeId, handlers = {}) {
  const { onSelect, onPositionCommit, onMetricsChange } = handlers;
  const stage = document.getElementById("graph-stage");
  const canvas = document.getElementById("graph-canvas");
  const nodeLayer = document.getElementById("graph-nodes");
  const edgeLayer = document.getElementById("graph-edges");
  const emptyState = document.getElementById("graph-empty");
  const nodesById = new Map(nodes.map((node) => [String(node.id), node]));
  const cardsById = new Map();

  function syncCanvasMetrics() {
    const metrics = buildCanvasMetrics(nodes);
    canvas.style.width = `${metrics.width}px`;
    canvas.style.height = `${metrics.height}px`;
    edgeLayer.setAttribute("viewBox", `0 0 ${metrics.width} ${metrics.height}`);
    onMetricsChange?.(metrics);
    return metrics;
  }

  function redrawEdges() {
    edgeLayer.innerHTML = "";
    for (const node of nodes) {
      if (node.parent_id === null || node.parent_id === undefined) {
        continue;
      }

      const parentNode = nodesById.get(String(node.parent_id));
      if (parentNode) {
        drawEdge(edgeLayer, parentNode, node);
      }
    }
  }

  function setNodePosition(node, position) {
    node.position.x = Math.max(0, position.x);
    node.position.y = Math.max(0, position.y);

    const card = cardsById.get(String(node.id));
    if (card) {
      applyNodePosition(card, node);
    }

    syncCanvasMetrics();
    redrawEdges();
  }

  function createNodeCard(node) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "graph-node";
    button.dataset.provider = node.provider;
    button.dataset.selected = String(String(node.id) === String(selectedNodeId));
    button.dataset.suppressClick = "false";
    button.dataset.dragging = "false";
    applyNodePosition(button, node);

    const title = document.createElement("span");
    title.className = "graph-node-title";
    title.textContent = node.title;

    const meta = document.createElement("span");
    meta.className = "graph-node-meta";
    meta.textContent = `${node.provider} / ${node.model_name}`;

    const summary = document.createElement("span");
    summary.className = "graph-node-summary";
    summary.textContent = node.summary || "No summary";

    button.append(title, meta, summary);

    let dragState = null;

    button.addEventListener("click", (event) => {
      if (button.dataset.suppressClick === "true") {
        event.preventDefault();
        button.dataset.suppressClick = "false";
        return;
      }
      onSelect?.(node.id);
    });

    button.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) {
        return;
      }

      dragState = {
        pointerId: event.pointerId,
        startClientX: event.clientX,
        startClientY: event.clientY,
        startX: node.position.x,
        startY: node.position.y,
        moved: false,
      };
      button.setPointerCapture(event.pointerId);
      event.preventDefault();
    });

    button.addEventListener("pointermove", (event) => {
      if (!dragState || dragState.pointerId !== event.pointerId) {
        return;
      }

      const deltaX = event.clientX - dragState.startClientX;
      const deltaY = event.clientY - dragState.startClientY;
      if (!dragState.moved && Math.hypot(deltaX, deltaY) < DRAG_THRESHOLD) {
        return;
      }

      if (!dragState.moved) {
        dragState.moved = true;
        stage.dataset.nodeDragging = "true";
        button.dataset.dragging = "true";
        button.dataset.suppressClick = "true";
      }

      setNodePosition(node, {
        x: dragState.startX + deltaX,
        y: dragState.startY + deltaY,
      });
    });

    function finishDragging(event) {
      if (!dragState || (event && dragState.pointerId !== event.pointerId)) {
        return;
      }

      const didMove = dragState.moved;
      const pointerId = dragState.pointerId;
      dragState = null;
      stage.dataset.nodeDragging = "false";
      button.dataset.dragging = "false";

      if (button.hasPointerCapture(pointerId)) {
        button.releasePointerCapture(pointerId);
      }

      if (didMove) {
        onPositionCommit?.(node.id, {
          x: node.position.x,
          y: node.position.y,
        });
      }
    }

    button.addEventListener("pointerup", finishDragging);
    button.addEventListener("pointercancel", finishDragging);

    return button;
  }

  nodeLayer.innerHTML = "";
  edgeLayer.innerHTML = "";
  emptyState.toggleAttribute("hidden", nodes.length > 0);
  stage.dataset.nodeDragging = "false";

  for (const node of nodes) {
    const card = createNodeCard(node);
    cardsById.set(String(node.id), card);
    nodeLayer.appendChild(card);
  }

  const metrics = syncCanvasMetrics();
  redrawEdges();
  return metrics;
}
