import { postJSON } from "./api.js";
import { renderChatTranscript, renderMessageEditors } from "./node-panel.js";
import { streamJSON } from "./streaming.js";

const payload = JSON.parse(document.getElementById("node-chat-payload").textContent);

const jumpButton = document.getElementById("chat-jump-button");
const transcript = document.getElementById("chat-transcript");
const form = document.getElementById("chat-form");
const promptInput = document.getElementById("chat-prompt-input");
const submitButton = document.getElementById("chat-submit-button");
const feedback = document.getElementById("chat-feedback");
const variantToggle = document.getElementById("chat-variant-toggle");
const variantForm = document.getElementById("chat-variant-form");
const variantTitleInput = document.getElementById("chat-variant-title-input");
const variantMessageList = document.getElementById("chat-variant-message-list");
const variantFeedback = document.getElementById("chat-variant-feedback");
const variantSubmitButton = document.getElementById("chat-variant-submit-button");
const csrfToken = document.getElementById("chat-csrf-token").value;
const PROMPT_MAX_HEIGHT = 176;

function resizePromptInput() {
  promptInput.style.height = "auto";
  const nextHeight = Math.min(promptInput.scrollHeight, PROMPT_MAX_HEIGHT);
  promptInput.style.height = `${nextHeight}px`;
  promptInput.style.overflowY = promptInput.scrollHeight > PROMPT_MAX_HEIGHT ? "auto" : "hidden";
}

function setVariantEditorOpen(isOpen) {
  variantForm.hidden = !isOpen;
  variantToggle.textContent = isOpen ? "Hide editor" : "Show editor";
  variantToggle.setAttribute("aria-expanded", String(isOpen));
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

function renderVariantEditor() {
  renderMessageEditors(variantMessageList, payload.messages);
  const hasMessages = payload.messages.length > 0;
  variantSubmitButton.disabled = !hasMessages;
  if (!hasMessages) {
    variantFeedback.textContent = "Add at least one message before creating a variant.";
  } else if (variantFeedback.textContent === "Add at least one message before creating a variant.") {
    variantFeedback.textContent = "";
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
          renderVariantEditor();
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

async function handleVariantSubmit(event) {
  event.preventDefault();
  if (!payload.messages.length) {
    variantFeedback.textContent = "Add at least one message before creating a variant.";
    return;
  }

  variantFeedback.textContent = "";
  variantSubmitButton.disabled = true;

  try {
    const messages = Array.from(variantMessageList.querySelectorAll("textarea")).map(
      (textarea, index) => ({
        role: textarea.dataset.role,
        content: textarea.value,
        order_index: index,
      }),
    );
    const result = await postJSON(
      variantForm.dataset.nodeEditUrl,
      {
        title: variantTitleInput.value,
        messages,
      },
      csrfToken,
    );
    variantFeedback.textContent = `Variant "${result.node.title}" created.`;
    window.location.href = result.node_chat_url;
  } catch (error) {
    variantFeedback.textContent = error.message;
  } finally {
    variantSubmitButton.disabled = false;
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
variantToggle.addEventListener("click", () => {
  setVariantEditorOpen(variantForm.hidden);
});
form.addEventListener("submit", handleSubmit);
variantForm.addEventListener("submit", handleVariantSubmit);
setVariantEditorOpen(false);
resizePromptInput();
renderTranscript();
renderVariantEditor();
scrollToBottom();
