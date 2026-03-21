import { getNodeBounds } from "./canvas.js?v=20260321-toolbar-quick-create";

const MINIMAP_WIDTH = 220;
const MINIMAP_HEIGHT = 148;
const MINIMAP_PADDING = 10;

function clampValue(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function getLayout(bounds) {
  if (!bounds) {
    return null;
  }

  const width = Math.max(bounds.maxX - bounds.minX, 1);
  const height = Math.max(bounds.maxY - bounds.minY, 1);
  const scale = Math.min(
    (MINIMAP_WIDTH - (MINIMAP_PADDING * 2)) / width,
    (MINIMAP_HEIGHT - (MINIMAP_PADDING * 2)) / height,
  );

  return {
    bounds,
    scale,
    offsetX: (MINIMAP_WIDTH - (width * scale)) / 2,
    offsetY: (MINIMAP_HEIGHT - (height * scale)) / 2,
  };
}

function toMapRect(bounds, layout) {
  const width = Math.max((bounds.maxX - bounds.minX) * layout.scale, 4);
  const height = Math.max((bounds.maxY - bounds.minY) * layout.scale, 4);
  const x = layout.offsetX + ((bounds.minX - layout.bounds.minX) * layout.scale);
  const y = layout.offsetY + ((bounds.minY - layout.bounds.minY) * layout.scale);

  return {
    x,
    y,
    width,
    height,
  };
}

export function createMinimapController(options = {}) {
  const { onNavigate } = options;

  const shell = document.getElementById("graph-minimap");
  const svg = document.getElementById("graph-minimap-svg");

  const state = {
    layout: null,
    nodes: [],
    viewportState: null,
  };

  function drawViewport(layout, viewportBounds) {
    if (!viewportBounds) {
      return;
    }

    const rect = toMapRect(viewportBounds, layout);
    const viewport = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    viewport.setAttribute("x", rect.x);
    viewport.setAttribute("y", rect.y);
    viewport.setAttribute("width", clampValue(rect.width, 12, MINIMAP_WIDTH));
    viewport.setAttribute("height", clampValue(rect.height, 12, MINIMAP_HEIGHT));
    viewport.setAttribute("class", "graph-minimap-viewport");
    svg.appendChild(viewport);
  }

  function render() {
    const contentBounds = state.viewportState?.contentBounds;
    const visibleBounds = state.viewportState?.visibleBounds;
    const layout = getLayout(contentBounds);
    state.layout = layout;

    svg.innerHTML = "";
    shell.hidden = !layout || state.nodes.length === 0;
    if (!layout || state.nodes.length === 0) {
      return;
    }

    const surface = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    surface.setAttribute("x", 0);
    surface.setAttribute("y", 0);
    surface.setAttribute("width", MINIMAP_WIDTH);
    surface.setAttribute("height", MINIMAP_HEIGHT);
    surface.setAttribute("rx", 14);
    surface.setAttribute("class", "graph-minimap-surface");
    svg.appendChild(surface);

    for (const node of state.nodes) {
      const bounds = getNodeBounds(node);
      const rect = toMapRect(bounds, layout);
      const nodeMarker = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      nodeMarker.setAttribute("x", rect.x);
      nodeMarker.setAttribute("y", rect.y);
      nodeMarker.setAttribute("width", rect.width);
      nodeMarker.setAttribute("height", rect.height);
      nodeMarker.setAttribute("rx", 4);
      nodeMarker.setAttribute("class", "graph-minimap-node");
      nodeMarker.dataset.provider = node.provider;
      svg.appendChild(nodeMarker);
    }

    drawViewport(layout, visibleBounds);
  }

  function onPointerDown(event) {
    if (!state.layout) {
      return;
    }

    const rect = svg.getBoundingClientRect();
    const mapX = clampValue(event.clientX - rect.left, 0, rect.width);
    const mapY = clampValue(event.clientY - rect.top, 0, rect.height);
    const scaledX = mapX * (MINIMAP_WIDTH / rect.width);
    const scaledY = mapY * (MINIMAP_HEIGHT / rect.height);

    onNavigate?.({
      x: ((scaledX - state.layout.offsetX) / state.layout.scale) + state.layout.bounds.minX,
      y: ((scaledY - state.layout.offsetY) / state.layout.scale) + state.layout.bounds.minY,
    });
    event.stopPropagation();
    event.preventDefault();
  }

  svg.addEventListener("pointerdown", onPointerDown);

  return {
    update({ nodes, viewportState }) {
      state.nodes = nodes;
      state.viewportState = viewportState;
      render();
    },
  };
}
