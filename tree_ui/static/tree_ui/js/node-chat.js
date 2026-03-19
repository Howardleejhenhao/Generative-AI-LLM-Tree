import { syncModelOptions } from "./model-options.js";
import { renderChatTranscript } from "./node-panel.js";
import { streamJSON } from "./streaming.js";

const payload = JSON.parse(document.getElementById("node-chat-payload").textContent);

const transcript = document.getElementById("chat-transcript");
const form = document.getElementById("chat-form");
const providerInput = document.getElementById("chat-provider-input");
const modelInput = document.getElementById("chat-model-input");
const titleInput = document.getElementById("chat-title-input");
const promptInput = document.getElementById("chat-prompt-input");
const submitButton = document.getElementById("chat-submit-button");
const feedback = document.getElementById("chat-feedback");
const csrfToken = document.getElementById("chat-csrf-token").value;

function getNodeChatUrl(nodeId) {
  return form.dataset.nodeChatUrlTemplate.replace("999999", String(nodeId));
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
      form.dataset.nodeStreamUrl,
      {
        parent_id: payload.id,
        title: titleInput.value,
        provider: providerInput.value,
        model_name: modelInput.value,
        prompt: promptInput.value,
      },
      csrfToken,
      {
        preview(data) {
          previewPrompt = data.prompt;
          assistantText = "";
          feedback.textContent = "Streaming child branch...";
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
          feedback.textContent = `Branch "${data.node.title}" created.`;
          window.location.href = getNodeChatUrl(data.node.id);
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

providerInput.addEventListener("change", () => syncModelOptions(providerInput, modelInput));
form.addEventListener("submit", handleSubmit);

syncModelOptions(providerInput, modelInput);
providerInput.value = payload.provider || "openai";
syncModelOptions(providerInput, modelInput);
if (payload.model_name) {
  modelInput.value = payload.model_name;
}
renderTranscript();
