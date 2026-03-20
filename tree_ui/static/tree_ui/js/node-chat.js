import { renderChatTranscript } from "./node-panel.js";
import { streamJSON } from "./streaming.js";

const payload = JSON.parse(document.getElementById("node-chat-payload").textContent);
const CHAT_CONTEXT_STORAGE_KEY = "llm-tree-chat-context-collapsed";

const chatPage = document.getElementById("chat-page");
const chatContextToggle = document.getElementById("chat-context-toggle");
const jumpButton = document.getElementById("chat-jump-button");
const transcript = document.getElementById("chat-transcript");
const form = document.getElementById("chat-form");
const promptInput = document.getElementById("chat-prompt-input");
const submitButton = document.getElementById("chat-submit-button");
const feedback = document.getElementById("chat-feedback");
const csrfToken = document.getElementById("chat-csrf-token").value;
const PROMPT_MAX_HEIGHT = 176;

function resizePromptInput() {
  promptInput.style.height = "auto";
  const nextHeight = Math.min(promptInput.scrollHeight, PROMPT_MAX_HEIGHT);
  promptInput.style.height = `${nextHeight}px`;
  promptInput.style.overflowY = promptInput.scrollHeight > PROMPT_MAX_HEIGHT ? "auto" : "hidden";
}

function readStoredContextState() {
  try {
    return window.localStorage.getItem(CHAT_CONTEXT_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function writeStoredContextState(isCollapsed) {
  try {
    window.localStorage.setItem(CHAT_CONTEXT_STORAGE_KEY, String(isCollapsed));
  } catch {
    // Ignore storage failures and keep the UI state in-memory only.
  }
}

function setContextCollapsed(isCollapsed) {
  chatPage.dataset.contextCollapsed = String(isCollapsed);
  chatContextToggle.textContent = isCollapsed ? "Show context" : "Hide context";
  chatContextToggle.setAttribute("aria-expanded", String(!isCollapsed));
  writeStoredContextState(isCollapsed);
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

function renderTranscript(extraMessages = []) {
  const shouldStick = isNearBottom();
  renderChatTranscript(transcript, [...payload.messages, ...extraMessages]);
  if (shouldStick) {
    scrollToBottom();
  }
  updateJumpButton();
}

async function handleSubmit(event) {
  event.preventDefault();
  feedback.textContent = "";
  submitButton.disabled = true;
  let previewPrompt = "";
  let assistantText = "";

  try {
    await streamJSON(
      form.dataset.nodeMessageStreamUrl,
      {
        prompt: promptInput.value,
      },
      csrfToken,
      {
        preview(data) {
          previewPrompt = data.prompt;
          assistantText = "";
          feedback.textContent = `Streaming reply from ${data.provider} / ${data.model_name}...`;
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
          payload.messages = data.node.messages;
          promptInput.value = "";
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

function handleWindowKeydown(event) {
  const isTyping = event.target === promptInput;

  if (event.key === "d" || event.key === "D") {
    if (!isTyping) {
      setContextCollapsed(chatPage.dataset.contextCollapsed !== "true");
      event.preventDefault();
    }
  }
}

promptInput.addEventListener("input", resizePromptInput);
promptInput.addEventListener("keydown", handlePromptKeydown);
transcript.addEventListener("scroll", updateJumpButton);
jumpButton.addEventListener("click", scrollToBottom);
chatContextToggle.addEventListener("click", () => {
  setContextCollapsed(chatPage.dataset.contextCollapsed !== "true");
});
window.addEventListener("keydown", handleWindowKeydown);
form.addEventListener("submit", handleSubmit);
setContextCollapsed(readStoredContextState());
resizePromptInput();
renderTranscript();
scrollToBottom();
