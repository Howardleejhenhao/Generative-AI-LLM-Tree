import { postJSON } from "./api.js?v=20260322-graph-hint-fix";
import { setMarkdownContent } from "./markdown.js?v=20260324-markdown-rendering";
import { renderChatTranscript } from "./node-panel.js?v=20260324-markdown-rendering";
import { streamJSON } from "./streaming.js";

const nodePayload = JSON.parse(document.getElementById("node-chat-node-payload").textContent);
const memoryPayload = JSON.parse(document.getElementById("node-chat-memory-payload").textContent);

const jumpButton = document.getElementById("chat-jump-button");
const transcript = document.getElementById("chat-transcript");
const form = document.getElementById("chat-form");
const promptInput = document.getElementById("chat-prompt-input");
const submitButton = document.getElementById("chat-submit-button");
const feedback = document.getElementById("chat-feedback");
const memoryForm = document.getElementById("memory-form");
const memoryScopeInput = document.getElementById("memory-scope-input");
const memoryTypeInput = document.getElementById("memory-type-input");
const memoryTitleInput = document.getElementById("memory-title-input");
const memoryContentInput = document.getElementById("memory-content-input");
const memoryFeedback = document.getElementById("memory-feedback");
const memorySubmitButton = document.getElementById("memory-submit-button");
const memorySourceChip = document.getElementById("memory-source-chip");
const memorySourceClearButton = document.getElementById("memory-source-clear");
const workspaceMemoryList = document.getElementById("workspace-memory-list");
const branchMemoryList = document.getElementById("branch-memory-list");
const workspaceMemoryTitle = document.getElementById("workspace-memory-title");
const branchMemoryTitle = document.getElementById("branch-memory-title");
const retrievedMemoryPreview = document.getElementById("retrieved-memory-preview");
const csrfToken = document.getElementById("chat-csrf-token").value;
const PROMPT_MAX_HEIGHT = 176;

let selectedMemorySource = null;

function resizePromptInput() {
  promptInput.style.height = "auto";
  const nextHeight = Math.min(promptInput.scrollHeight, PROMPT_MAX_HEIGHT);
  promptInput.style.height = `${nextHeight}px`;
  promptInput.style.overflowY = promptInput.scrollHeight > PROMPT_MAX_HEIGHT ? "auto" : "hidden";
}

function isNearBottom() {
  return transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 80;
}

function scrollToBottom() {
  transcript.scrollTop = transcript.scrollHeight;
  updateJumpButton();
}

function updateJumpButton() {
  jumpButton.hidden = isNearBottom();
}

function updateMemorySourceState() {
  if (!selectedMemorySource) {
    memorySourceChip.textContent = "Manual note";
    memorySourceClearButton.hidden = true;
    return;
  }

  memorySourceChip.textContent = `Pinned from ${selectedMemorySource.role} message`;
  memorySourceClearButton.hidden = false;
}

function clearMemorySource() {
  selectedMemorySource = null;
  memoryTitleInput.value = "";
  memoryContentInput.value = "";
  memoryFeedback.textContent = "";
  updateMemorySourceState();
}

function loadMessageIntoMemoryForm(message) {
  selectedMemorySource = {
    messageId: message.id,
    nodeId: nodePayload.id,
    role: message.role,
  };
  memoryTitleInput.value = `${message.role} memory`;
  memoryContentInput.value = message.content;
  memoryFeedback.textContent = "Message loaded into the memory form.";
  updateMemorySourceState();
  memoryContentInput.focus();
  memoryContentInput.setSelectionRange(memoryContentInput.value.length, memoryContentInput.value.length);
}

function createMessageActionButtons(message) {
  if (!message.id) {
    return null;
  }

  const actions = document.createElement("div");
  actions.className = "chat-message-actions";

  const useButton = document.createElement("button");
  useButton.type = "button";
  useButton.className = "chat-message-action";
  useButton.textContent = "Use as memory";
  useButton.addEventListener("click", () => loadMessageIntoMemoryForm(message));

  actions.appendChild(useButton);
  return actions;
}

function renderTranscript(extraMessages = []) {
  const shouldStick = isNearBottom();
  renderChatTranscript(transcript, [...nodePayload.messages, ...extraMessages], {
    renderActions: createMessageActionButtons,
  });
  if (shouldStick) {
    scrollToBottom();
  }
  updateJumpButton();
}

function createMemoryCard(memory) {
  const article = document.createElement("article");
  article.className = "chat-branch-card memory-card";

  const title = document.createElement("strong");
  title.textContent = memory.title || "(Untitled memory)";

  const meta = document.createElement("span");
  const pinnedLabel = memory.is_pinned ? "Pinned" : "Saved";
  meta.textContent = `${pinnedLabel} · ${memory.scope} / ${memory.memory_type}`;

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
  workspaceMemoryTitle.textContent = `Shared across this workspace (${memoryPayload.workspace_memories.length})`;
  branchMemoryTitle.textContent = `Visible only on this lineage (${memoryPayload.branch_memories.length})`;
  renderMemoryList(
    workspaceMemoryList,
    memoryPayload.workspace_memories,
    "No workspace memories saved yet.",
  );
  renderMemoryList(
    branchMemoryList,
    memoryPayload.branch_memories,
    "No branch memories saved on this lineage yet.",
  );
  if (memoryPayload.retrieved_memory_text) {
    retrievedMemoryPreview.textContent = memoryPayload.retrieved_memory_text;
  } else {
    retrievedMemoryPreview.textContent = "No long-term memories are retrieved for this node yet.";
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
        scope: memoryScopeInput.value,
        memory_type: memoryTypeInput.value,
        title: memoryTitleInput.value,
        content: memoryContentInput.value,
        branch_anchor_id: memoryScopeInput.value === "branch" ? nodePayload.id : null,
        source_node_id: selectedMemorySource?.nodeId || null,
        source_message_id: selectedMemorySource?.messageId || null,
      },
      csrfToken,
    );
    memoryPayload.workspace_memories = result.memory_payload.workspace_memories;
    memoryPayload.branch_memories = result.memory_payload.branch_memories;
    memoryPayload.retrieved_memories = result.memory_payload.retrieved_memories;
    memoryPayload.retrieved_memory_text = result.memory_payload.retrieved_memory_text;
    renderMemoryPanels();
    memoryFeedback.textContent = selectedMemorySource
      ? "Message pinned into long-term memory."
      : "Memory saved.";
    clearMemorySource();
  } catch (error) {
    memoryFeedback.textContent = error.message;
  } finally {
    memorySubmitButton.disabled = false;
  }
}

async function handleSubmit(event) {
  event.preventDefault();
  feedback.textContent = "";
  const submittedPrompt = promptInput.value;
  if (!submittedPrompt.trim()) {
    feedback.textContent = "Prompt is required.";
    return;
  }

  promptInput.value = "";
  resizePromptInput();
  submitButton.disabled = true;
  let previewPrompt = "";
  let assistantText = "";

  try {
    await streamJSON(
      form.dataset.nodeMessageStreamUrl,
      {
        prompt: submittedPrompt,
      },
      csrfToken,
      {
        preview(data) {
          previewPrompt = data.prompt;
          assistantText = "";
          feedback.textContent = data.created_new_branch
            ? `This node already has children. Continuing in a new child branch via ${data.provider} / ${data.model_name}...`
            : `Streaming reply from ${data.provider} / ${data.model_name}...`;
          renderTranscript([
            {
              role: "user",
              content: previewPrompt,
            },
            {
              role: "assistant",
              content: "Generating...",
            },
          ]);
          scrollToBottom();
        },
        delta(data) {
          assistantText += data.delta;
          renderTranscript([
            {
              role: "user",
              content: previewPrompt,
            },
            {
              role: "assistant",
              content: assistantText || "Generating...",
            },
          ]);
          if (isNearBottom()) {
            scrollToBottom();
          }
        },
        node(data) {
          if (data.created_new_branch && data.node_chat_url) {
            window.location.href = data.node_chat_url;
            return;
          }
          nodePayload.messages = data.node.messages;
          resizePromptInput();
          feedback.textContent = "Reply added to this node.";
          renderTranscript();
          scrollToBottom();
        },
        error(data) {
          throw new Error(data.message || "Streaming request failed.");
        },
      },
    );
  } catch (error) {
    if (!previewPrompt) {
      promptInput.value = submittedPrompt;
      resizePromptInput();
    }
    feedback.textContent = error.message;
    renderTranscript();
  } finally {
    submitButton.disabled = false;
  }
}

function handlePromptKeydown(event) {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    form.requestSubmit();
    event.preventDefault();
  }
}

promptInput.addEventListener("input", resizePromptInput);
promptInput.addEventListener("keydown", handlePromptKeydown);
transcript.addEventListener("scroll", updateJumpButton);
jumpButton.addEventListener("click", scrollToBottom);
form.addEventListener("submit", handleSubmit);
memoryForm.addEventListener("submit", handleMemorySubmit);
memorySourceClearButton.addEventListener("click", clearMemorySource);

updateMemorySourceState();
resizePromptInput();
renderMemoryPanels();
renderTranscript();
scrollToBottom();
