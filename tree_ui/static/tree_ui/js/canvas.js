const NODE_WIDTH = 264;
const NODE_FOOTPRINT_WIDTH = 320;
const NODE_FOOTPRINT_HEIGHT = 180;
const NODE_MIDPOINT_Y = 70;
const DRAG_THRESHOLD = 6;

export function getNodeBounds(node) {
  return {
    minX: node.position.x,
    minY: node.position.y,
    maxX: node.position.x + NODE_FOOTPRINT_WIDTH,
    maxY: node.position.y + NODE_FOOTPRINT_HEIGHT,
  };
}

function drawEdge(svg, fromNode, toNode, isActive = false) {
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
  path.dataset.active = String(isActive);
  svg.appendChild(path);
}

function buildCanvasMetrics(nodes) {
  if (nodes.length === 0) {
    return {
      contentBounds: null,
      width: 1600,
      height: 1200,
    };
  }

  let minX = Number.POSITIVE_INFINITY;
  let minY = Number.POSITIVE_INFINITY;
  let maxX = 0;
  let maxY = 0;
  for (const node of nodes) {
    const bounds = getNodeBounds(node);
    minX = Math.min(minX, bounds.minX);
    minY = Math.min(minY, bounds.minY);
    maxX = Math.max(maxX, bounds.maxX);
    maxY = Math.max(maxY, bounds.maxY);
  }

  return {
    contentBounds: {
      minX,
      minY,
      maxX,
      maxY,
    },
    width: Math.max(1600, maxX + 220),
    height: Math.max(1200, maxY + 220),
  };
}

function applyNodePosition(card, node) {
  card.style.left = `${node.position.x}px`;
  card.style.top = `${node.position.y}px`;
}

export function renderCanvas(nodes, selectedNodeId, handlers = {}) {
  const {
    activeLineageIds = new Set(),
    matchedNodeIds = new Set(),
    onSelect,
    onOpenChat,
    onPositionCommit,
    onMetricsChange,
    getViewportScale,
  } = handlers;
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
        drawEdge(
          edgeLayer,
          parentNode,
          node,
          activeLineageIds.has(String(parentNode.id)) && activeLineageIds.has(String(node.id)),
        );
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
    button.dataset.lineage = String(activeLineageIds.has(String(node.id)));
    button.dataset.match = String(matchedNodeIds.has(String(node.id)));
    button.dataset.dragging = "false";
    applyNodePosition(button, node);

    const topLine = document.createElement("span");
    topLine.className = "graph-node-topline";

    const providerBadge = document.createElement("span");
    providerBadge.className = "graph-node-provider";
    providerBadge.textContent = node.provider;

    const badgesContainer = document.createElement("div");
    badgesContainer.className = "graph-node-badges";

    // Add message count as a standard badge
    const msgBadge = document.createElement("span");
    msgBadge.className = "graph-node-count";
    msgBadge.textContent = `${node.messages.length} ${node.messages.length === 1 ? "msg" : "msgs"}`;
    badgesContainer.appendChild(msgBadge);

    if (node.attachments.length > 0) {
      const imgBadge = document.createElement("span");
      imgBadge.className = "graph-node-count";
      imgBadge.textContent = `${node.attachments.length} img`;
      badgesContainer.appendChild(imgBadge);
    }

    // Add status badges from payload
    if (node.status_badges) {
      for (const badgeData of node.status_badges) {
        const badge = document.createElement("span");
        badge.className = `graph-node-badge badge-${badgeData.type}`;
        badge.textContent = badgeData.label;
        badgesContainer.appendChild(badge);
      }
    }

    const title = document.createElement("span");
    title.className = "graph-node-title";
    title.textContent = node.title;

    const meta = document.createElement("span");
    meta.className = "graph-node-meta";
    meta.textContent = node.model_name;

    const summary = document.createElement("span");
    summary.className = "graph-node-summary";
    summary.textContent = node.summary || "No summary";

    const footer = document.createElement("span");
    footer.className = "graph-node-footer";

    const state = document.createElement("span");
    state.className = "graph-node-state";
    if (node.edited_from_id) {
      state.textContent = `Edited from ${node.edited_from_id}`;
    } else if (node.parent_id) {
      state.textContent = `Child of ${node.parent_id}`;
    } else {
      state.textContent = "Root conversation";
    }

    topLine.append(providerBadge, badgesContainer);
    footer.append(state);
    button.append(topLine, title, meta, summary, footer);

    let dragState = null;

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
      }

      const scale = Math.max(getViewportScale?.() || 1, 0.01);
      setNodePosition(node, {
        x: dragState.startX + (deltaX / scale),
        y: dragState.startY + (deltaY / scale),
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

      if (!didMove) {
        onSelect?.(node.id);
        onOpenChat?.(node.id);
        return;
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
