import { renderChatTranscript } from "./node-panel.js";
import { streamJSON } from "./streaming.js";

const payload = JSON.parse(document.getElementById("node-chat-payload").textContent);

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

function renderTranscript(extraMessages = []) {
  renderChatTranscript(transcript, [...payload.messages, ...extraMessages]);
  transcript.scrollTop = transcript.scrollHeight;
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
        },
        node(data) {
          payload.messages = data.node.messages;
          promptInput.value = "";
          resizePromptInput();
          feedback.textContent = "Reply added to this node.";
          renderTranscript();
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

promptInput.addEventListener("input", resizePromptInput);
form.addEventListener("submit", handleSubmit);
resizePromptInput();
renderTranscript();
