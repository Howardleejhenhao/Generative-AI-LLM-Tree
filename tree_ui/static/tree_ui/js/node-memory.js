import { postJSON } from "./api.js?v=20260322-graph-hint-fix";
import { setMarkdownContent } from "./markdown.js?v=20260324-markdown-rendering";

const nodePayload = JSON.parse(document.getElementById("node-memory-node-payload").textContent);
const memoryPayload = JSON.parse(document.getElementById("node-memory-memory-payload").textContent);

const draftUrl = document.getElementById("node-memory-draft-url").dataset.draftUrl;
const refreshWorkspaceMemoryUrl = document.getElementById("node-workspace-memory-refresh-url").dataset.refreshUrl;
const memoryForm = document.getElementById("memory-form");
const memoryScopeInput = document.getElementById("memory-scope-input");
const memoryTypeInput = document.getElementById("memory-type-input");
const memoryTitleInput = document.getElementById("memory-title-input");
const memoryContentInput = document.getElementById("memory-content-input");
const memoryFeedback = document.getElementById("memory-feedback");
const memoryDraftFeedback = document.getElementById("memory-draft-feedback");
const memorySubmitButton = document.getElementById("memory-submit-button");
const regenerateButton = document.getElementById("memory-draft-regenerate");
const workspaceMemoryList = document.getElementById("workspace-memory-list");
const branchMemoryList = document.getElementById("branch-memory-list");
const workspaceMemoryTitle = document.getElementById("workspace-memory-title");
const branchMemoryTitle = document.getElementById("branch-memory-title");
const retrievedMemoryPreview = document.getElementById("retrieved-memory-preview");
const refreshWorkspaceMemoryButton = document.getElementById("workspace-memory-refresh");
const csrfToken = document.querySelector("#memory-form input[name='csrfmiddlewaretoken']").value;

function createMemoryCard(memory) {
  const article = document.createElement("article");
  article.className = "chat-branch-card memory-card";

  const title = document.createElement("strong");
  title.textContent = memory.title || "(Untitled memory)";

  const meta = document.createElement("span");
  meta.textContent = `${memory.scope} / ${memory.memory_type}`;

  const body = document.createElement("div");
  body.className = "memory-card-body markdown-content";
  setMarkdownContent(body, memory.content);

  article.append(title, meta, body);
  return article;
}

function renderMemoryList(container, memories, emptyText) {
  container.innerHTML = "";

  if (!memories.length) {
    const empty = document.createElement("p");
    empty.className = "chat-empty-copy";
    empty.textContent = emptyText;
    container.appendChild(empty);
    return;
  }

  for (const memory of memories) {
    container.appendChild(createMemoryCard(memory));
  }
}

function renderMemoryPanels() {
  workspaceMemoryTitle.textContent = `Workspace (${memoryPayload.workspace_memories.length})`;
  branchMemoryTitle.textContent = `Branch (${memoryPayload.branch_memories.length})`;
  renderMemoryList(workspaceMemoryList, memoryPayload.workspace_memories, "No workspace memories.");
  renderMemoryList(branchMemoryList, memoryPayload.branch_memories, "No branch memories.");
  retrievedMemoryPreview.textContent = memoryPayload.retrieved_memory_text || "No long-term memories are retrieved for this node yet.";
}

function applyDraft(draft) {
  memoryScopeInput.value = "branch";
  memoryTypeInput.value = draft.memory_type || "summary";
  memoryTitleInput.value = draft.title || "";
  memoryContentInput.value = draft.content || "";
  memoryDraftFeedback.textContent = draft.used_fallback
    ? "Draft fallback used. Adjust before saving."
    : `Draft prepared with ${nodePayload.provider} / ${nodePayload.model_name}.`;
}

async function generateDraft() {
  memoryDraftFeedback.textContent = "Generating draft...";
  regenerateButton.disabled = true;

  try {
    const result = await postJSON(draftUrl, {}, csrfToken);
    applyDraft(result.draft);
  } catch (error) {
    memoryDraftFeedback.textContent = error.message;
  } finally {
    regenerateButton.disabled = false;
  }
}

async function refreshWorkspaceMemory() {
  refreshWorkspaceMemoryButton.disabled = true;

  try {
    const result = await postJSON(refreshWorkspaceMemoryUrl, {}, csrfToken);
    memoryPayload.workspace_memories = result.memory_payload.workspace_memories;
    memoryPayload.branch_memories = result.memory_payload.branch_memories;
    memoryPayload.retrieved_memories = result.memory_payload.retrieved_memories;
    memoryPayload.retrieved_memory_text = result.memory_payload.retrieved_memory_text;
    renderMemoryPanels();
  } finally {
    refreshWorkspaceMemoryButton.disabled = false;
  }
}

async function handleMemorySubmit(event) {
  event.preventDefault();
  memoryFeedback.textContent = "";
  memorySubmitButton.disabled = true;

  try {
    const result = await postJSON(
      memoryForm.dataset.createMemoryUrl,
      {
        context_node_id: nodePayload.id,
        scope: "branch",
        memory_type: memoryTypeInput.value,
        title: memoryTitleInput.value,
        content: memoryContentInput.value,
        branch_anchor_id: nodePayload.id,
      },
      csrfToken,
    );
    memoryPayload.workspace_memories = result.memory_payload.workspace_memories;
    memoryPayload.branch_memories = result.memory_payload.branch_memories;
    memoryPayload.retrieved_memories = result.memory_payload.retrieved_memories;
    memoryPayload.retrieved_memory_text = result.memory_payload.retrieved_memory_text;
    renderMemoryPanels();
    memoryFeedback.textContent = "Memory saved.";
  } catch (error) {
    memoryFeedback.textContent = error.message;
  } finally {
    memorySubmitButton.disabled = false;
  }
}

memoryForm.addEventListener("submit", handleMemorySubmit);
regenerateButton.addEventListener("click", generateDraft);
refreshWorkspaceMemoryButton.addEventListener("click", refreshWorkspaceMemory);

renderMemoryPanels();
refreshWorkspaceMemory().then(generateDraft);
