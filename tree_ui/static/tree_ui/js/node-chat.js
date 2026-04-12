import { renderChatTranscript } from "./node-panel.js?v=20260412-ordered-list-fix";
import { streamJSON } from "./streaming.js";

const payload = JSON.parse(document.getElementById("node-chat-node-payload").textContent);

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
          payload.messages = data.node.messages;
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
resizePromptInput();
renderTranscript();
scrollToBottom();
