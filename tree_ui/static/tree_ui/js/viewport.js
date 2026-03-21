const MIN_ZOOM = 0.55;
const MAX_ZOOM = 1.75;
const DEFAULT_ZOOM = 1;
const ZOOM_STEP = 0.15;
const FIT_PADDING_X = 88;
const FIT_PADDING_Y = 112;

function clampValue(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function roundZoom(value) {
  return Math.round(value * 100) / 100;
}

function normalizeBounds(bounds) {
  if (!bounds) {
    return null;
  }

  return {
    minX: bounds.minX,
    minY: bounds.minY,
    maxX: Math.max(bounds.maxX, bounds.minX + 1),
    maxY: Math.max(bounds.maxY, bounds.minY + 1),
  };
}

function getVisibleBounds(state, stage) {
  return {
    minX: (-state.panX) / state.zoom,
    minY: (-state.panY) / state.zoom,
    maxX: (stage.clientWidth - state.panX) / state.zoom,
    maxY: (stage.clientHeight - state.panY) / state.zoom,
  };
}

export function createViewportController(options = {}) {
  const { onChange } = options;

  const stage = document.getElementById("graph-stage");
  const canvas = document.getElementById("graph-canvas");
  const hint = document.getElementById("graph-hint");

  const state = {
    panX: 0,
    panY: 0,
    zoom: DEFAULT_ZOOM,
    canvasWidth: 1600,
    canvasHeight: 1200,
    contentBounds: null,
    dragging: false,
    hasAutoFit: false,
    startPanX: 0,
    startPanY: 0,
    pointerStartX: 0,
    pointerStartY: 0,
  };

  function getScaledCanvasSize() {
    return {
      width: state.canvasWidth * state.zoom,
      height: state.canvasHeight * state.zoom,
    };
  }

  function getBounds() {
    const { width, height } = getScaledCanvasSize();
    const stageWidth = stage.clientWidth;
    const stageHeight = stage.clientHeight;

    if (width <= stageWidth) {
      const centeredX = (stageWidth - width) / 2;
      if (height <= stageHeight) {
        const centeredY = (stageHeight - height) / 2;
        return { minX: centeredX, maxX: centeredX, minY: centeredY, maxY: centeredY };
      }
      return {
        minX: centeredX,
        maxX: centeredX,
        minY: stageHeight - height,
        maxY: 0,
      };
    }

    if (height <= stageHeight) {
      const centeredY = (stageHeight - height) / 2;
      return {
        minX: stageWidth - width,
        maxX: 0,
        minY: centeredY,
        maxY: centeredY,
      };
    }

    return {
      minX: stageWidth - width,
      minY: stageHeight - height,
      maxX: 0,
      maxY: 0,
    };
  }

  function publishState() {
    onChange?.({
      zoom: state.zoom,
      percent: Math.round(state.zoom * 100),
      canZoomIn: state.zoom < MAX_ZOOM,
      canZoomOut: state.zoom > MIN_ZOOM,
      canFit: Boolean(state.contentBounds),
      contentBounds: state.contentBounds,
      hasNodes: stage.dataset.hasNodes === "true",
      visibleBounds: getVisibleBounds(state, stage),
    });
  }

  function applyTransform() {
    const { minX, minY, maxX, maxY } = getBounds();
    state.panX = clampValue(state.panX, minX, maxX);
    state.panY = clampValue(state.panY, minY, maxY);
    canvas.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.zoom})`;
    stage.dataset.dragging = String(state.dragging);
    stage.dataset.zoom = String(Math.round(state.zoom * 100));
    hint.hidden = state.dragging;
    publishState();
  }

  function centerBoundsAtZoom(bounds, zoom) {
    const stageWidth = stage.clientWidth;
    const stageHeight = stage.clientHeight;
    const width = bounds.maxX - bounds.minX;
    const height = bounds.maxY - bounds.minY;

    state.zoom = clampValue(roundZoom(zoom), MIN_ZOOM, MAX_ZOOM);
    state.panX = ((stageWidth - (width * state.zoom)) / 2) - (bounds.minX * state.zoom);
    state.panY = ((stageHeight - (height * state.zoom)) / 2) - (bounds.minY * state.zoom);
    applyTransform();
  }

  function fitToBounds(bounds) {
    const resolvedBounds = normalizeBounds(bounds);
    if (!resolvedBounds) {
      applyTransform();
      return;
    }

    const stageWidth = stage.clientWidth;
    const stageHeight = stage.clientHeight;
    const width = resolvedBounds.maxX - resolvedBounds.minX;
    const height = resolvedBounds.maxY - resolvedBounds.minY;
    const availableWidth = Math.max(stageWidth - (FIT_PADDING_X * 2), 120);
    const availableHeight = Math.max(stageHeight - (FIT_PADDING_Y * 2), 120);
    const nextZoom = Math.min(availableWidth / width, availableHeight / height, MAX_ZOOM);

    centerBoundsAtZoom(resolvedBounds, Math.max(nextZoom, MIN_ZOOM));
  }

  function centerOnBounds(bounds) {
    const resolvedBounds = normalizeBounds(bounds);
    if (!resolvedBounds) {
      applyTransform();
      return;
    }

    centerBoundsAtZoom(resolvedBounds, state.zoom);
  }

  function centerOnPoint(point) {
    if (!point) {
      applyTransform();
      return;
    }

    state.panX = (stage.clientWidth / 2) - (point.x * state.zoom);
    state.panY = (stage.clientHeight / 2) - (point.y * state.zoom);
    applyTransform();
  }

  function setCanvasMetrics(metrics, hasNodes) {
    state.canvasWidth = metrics.width;
    state.canvasHeight = metrics.height;
    state.contentBounds = normalizeBounds(metrics.contentBounds);
    stage.dataset.hasNodes = String(hasNodes);

    if (!hasNodes) {
      state.hasAutoFit = false;
      applyTransform();
      return;
    }

    if (!state.hasAutoFit && state.contentBounds) {
      state.hasAutoFit = true;
      fitToBounds(state.contentBounds);
      return;
    }

    applyTransform();
  }

  function setZoom(nextZoom, anchor = null) {
    const resolvedZoom = clampValue(roundZoom(nextZoom), MIN_ZOOM, MAX_ZOOM);
    if (resolvedZoom === state.zoom) {
      applyTransform();
      return;
    }

    const anchorX = anchor?.x ?? (stage.clientWidth / 2);
    const anchorY = anchor?.y ?? (stage.clientHeight / 2);
    const worldX = (anchorX - state.panX) / state.zoom;
    const worldY = (anchorY - state.panY) / state.zoom;

    state.zoom = resolvedZoom;
    state.panX = anchorX - (worldX * state.zoom);
    state.panY = anchorY - (worldY * state.zoom);
    applyTransform();
  }

  function onPointerDown(event) {
    if (event.button !== 0) {
      return;
    }
    if (event.target.closest(".graph-node")) {
      return;
    }
    if (event.target.closest(".graph-controls")) {
      return;
    }
    if (event.target.closest(".graph-minimap")) {
      return;
    }
    if (event.target.closest(".graph-quick-create")) {
      return;
    }
    if (stage.dataset.hasNodes !== "true") {
      return;
    }

    state.dragging = true;
    state.startPanX = state.panX;
    state.startPanY = state.panY;
    state.pointerStartX = event.clientX;
    state.pointerStartY = event.clientY;
    stage.setPointerCapture(event.pointerId);
    applyTransform();
    event.preventDefault();
  }

  function onPointerMove(event) {
    if (!state.dragging) {
      return;
    }

    const deltaX = event.clientX - state.pointerStartX;
    const deltaY = event.clientY - state.pointerStartY;
    state.panX = state.startPanX + deltaX;
    state.panY = state.startPanY + deltaY;
    applyTransform();
  }

  function stopDragging(event) {
    if (!state.dragging) {
      return;
    }

    state.dragging = false;
    if (event && stage.hasPointerCapture(event.pointerId)) {
      stage.releasePointerCapture(event.pointerId);
    }
    applyTransform();
  }

  function onWheel(event) {
    if (stage.dataset.hasNodes !== "true") {
      return;
    }
    if (!event.ctrlKey && !event.metaKey) {
      return;
    }

    const rect = stage.getBoundingClientRect();
    const direction = event.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP;
    setZoom(state.zoom + direction, {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    });
    event.preventDefault();
  }

  stage.addEventListener("pointerdown", onPointerDown);
  stage.addEventListener("pointermove", onPointerMove);
  stage.addEventListener("pointerup", stopDragging);
  stage.addEventListener("pointercancel", stopDragging);
  stage.addEventListener("wheel", onWheel, { passive: false });
  window.addEventListener("resize", applyTransform);

  applyTransform();

  return {
    centerOnBounds,
    centerOnPoint,
    fitToGraph() {
      fitToBounds(state.contentBounds);
    },
    getScale() {
      return state.zoom;
    },
    refreshLayout() {
      applyTransform();
    },
    resetZoom() {
      setZoom(DEFAULT_ZOOM);
    },
    setCanvasMetrics,
    zoomIn() {
      setZoom(state.zoom + ZOOM_STEP);
    },
    zoomOut() {
      setZoom(state.zoom - ZOOM_STEP);
    },
  };
}
