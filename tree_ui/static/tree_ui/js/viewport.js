function clampPan(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function createViewportController() {
  const stage = document.getElementById("graph-stage");
  const canvas = document.getElementById("graph-canvas");
  const hint = document.getElementById("graph-hint");

  const state = {
    panX: 0,
    panY: 0,
    canvasWidth: 1600,
    canvasHeight: 1200,
    dragging: false,
    startPanX: 0,
    startPanY: 0,
    pointerStartX: 0,
    pointerStartY: 0,
  };

  function getBounds() {
    const minX = Math.min(0, stage.clientWidth - state.canvasWidth);
    const minY = Math.min(0, stage.clientHeight - state.canvasHeight);
    const maxX = 0;
    const maxY = 0;
    return { minX, minY, maxX, maxY };
  }

  function applyPan() {
    const { minX, minY, maxX, maxY } = getBounds();
    state.panX = clampPan(state.panX, minX, maxX);
    state.panY = clampPan(state.panY, minY, maxY);
    canvas.style.transform = `translate(${state.panX}px, ${state.panY}px)`;
    stage.dataset.dragging = String(state.dragging);
    hint.hidden = state.dragging;
  }

  function setCanvasMetrics(metrics, hasNodes) {
    state.canvasWidth = metrics.width;
    state.canvasHeight = metrics.height;
    stage.dataset.hasNodes = String(hasNodes);
    applyPan();
  }

  function onPointerDown(event) {
    if (event.button !== 0) {
      return;
    }
    if (event.target.closest(".graph-node")) {
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
    applyPan();
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
    applyPan();
  }

  function stopDragging(event) {
    if (!state.dragging) {
      return;
    }

    state.dragging = false;
    if (event) {
      stage.releasePointerCapture(event.pointerId);
    }
    applyPan();
  }

  stage.addEventListener("pointerdown", onPointerDown);
  stage.addEventListener("pointermove", onPointerMove);
  stage.addEventListener("pointerup", stopDragging);
  stage.addEventListener("pointercancel", stopDragging);
  window.addEventListener("resize", applyPan);

  applyPan();

  return {
    setCanvasMetrics,
  };
}
