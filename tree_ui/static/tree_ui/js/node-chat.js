import { renderChatTranscript, renderMessageEditors } from "./node-panel.js?v=20260412-edit-variant-ui";
import { streamJSON } from "./streaming.js?v=20260413-image-upload";

const payload = JSON.parse(document.getElementById("node-chat-node-payload").textContent);

const chatPage = document.getElementById("chat-page");
const chatHeader = chatPage.querySelector(".chat-shell-header");
const jumpButton = document.getElementById("chat-jump-button");
const transcript = document.getElementById("chat-transcript");
const form = document.getElementById("chat-form");
const promptInput = document.getElementById("chat-prompt-input");
const imageInput = document.getElementById("chat-image-input");
const selectedFiles = document.getElementById("chat-selected-files");
const submitButton = document.getElementById("chat-submit-button");
const feedback = document.getElementById("chat-feedback");
const csrfToken = document.getElementById("chat-csrf-token").value;
const editVariantToggleButton = document.getElementById("edit-variant-toggle-button");
const editVariantShell = document.getElementById("chat-edit-shell");
const editVariantForm = document.getElementById("edit-variant-form");
const editVariantTitleInput = document.getElementById("edit-variant-title");
const editVariantEditors = document.getElementById("edit-variant-editors");
const editVariantCancelButton = document.getElementById("edit-variant-cancel-button");
const editVariantSubmitButton = document.getElementById("edit-variant-submit-button");
const editVariantFeedback = document.getElementById("edit-variant-feedback");
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

function renderSelectedFiles() {
  const files = Array.from(imageInput.files || []);
  selectedFiles.innerHTML = "";
  selectedFiles.hidden = files.length === 0;
  if (!files.length) {
    return;
  }
  for (const file of files) {
    const chip = document.createElement("span");
    chip.className = "chat-selected-file";
    chip.textContent = file.name;
    selectedFiles.append(chip);
  }
}

function renderAttachmentPanel() {
  let panel = document.getElementById("chat-attachment-panel");
  if (!payload.attachments?.length) {
    panel?.remove();
    return;
  }
  if (!panel) {
    panel = document.createElement("section");
    panel.className = "chat-attachment-panel";
    panel.id = "chat-attachment-panel";
    chatHeader.insertAdjacentElement("afterend", panel);
  }
  panel.innerHTML = "";

  const header = document.createElement("div");
  header.className = "chat-attachment-header";
  const copy = document.createElement("div");
  const kicker = document.createElement("p");
  kicker.className = "chat-edit-kicker";
  kicker.textContent = "Images";
  const title = document.createElement("h2");
  title.textContent = "Attached to this node";
  copy.append(kicker, title);

  const pill = document.createElement("span");
  pill.className = "workspace-summary-pill";
  pill.textContent = `${payload.attachments.length} image${payload.attachments.length === 1 ? "" : "s"}`;
  header.append(copy, pill);

  const grid = document.createElement("div");
  grid.className = "chat-attachment-grid";

  for (const attachment of payload.attachments) {
    const link = document.createElement("a");
    link.className = "chat-attachment-card";
    link.href = attachment.url;
    link.target = "_blank";
    link.rel = "noreferrer";

    const image = document.createElement("img");
    image.src = attachment.url;
    image.alt = attachment.name;

    const label = document.createElement("span");
    label.textContent = attachment.name;
    link.append(image, label);
    grid.append(link);
  }

  panel.append(header, grid);
}

function cloneMessages(messages) {
  return messages.map((message) => ({
    role: message.role,
    content: message.content,
    order_index: message.order_index,
  }));
}

function setEditVariantVisible(visible) {
  editVariantShell.hidden = !visible;
  editVariantToggleButton.setAttribute("aria-expanded", visible ? "true" : "false");
  if (visible) {
    editVariantFeedback.textContent = "";
    renderMessageEditors(editVariantEditors, cloneMessages(payload.messages));
    editVariantTitleInput.value = `${payload.title} (Edited)`;
    requestAnimationFrame(() => {
      editVariantShell.scrollIntoView({ behavior: "smooth", block: "nearest" });
      editVariantTitleInput.focus();
      editVariantTitleInput.select();
    });
    return;
  }
  editVariantEditors.innerHTML = "";
}

function collectEditedMessages() {
  return Array.from(editVariantEditors.querySelectorAll("textarea")).map((textarea, index) => ({
    role: textarea.dataset.role,
    content: textarea.value.trim(),
    order_index: index,
  }));
}

async function handleSubmit(event) {
  event.preventDefault();
  feedback.textContent = "";
  const submittedPrompt = promptInput.value;
  if (!submittedPrompt.trim()) {
    feedback.textContent = "Prompt is required.";
    return;
  }

  const selectedImages = Array.from(imageInput.files || []);
  const requestPayload = (() => {
    if (!selectedImages.length) {
      return { prompt: submittedPrompt };
    }
    const formData = new FormData();
    formData.append("prompt", submittedPrompt);
    for (const file of selectedImages) {
      formData.append("images", file);
    }
    return formData;
  })();
  promptInput.value = "";
  imageInput.value = "";
  renderSelectedFiles();
  resizePromptInput();
  submitButton.disabled = true;
  let previewPrompt = "";
  let assistantText = "";

  try {
    await streamJSON(
      form.dataset.nodeMessageStreamUrl,
      requestPayload,
      csrfToken,
      {
        preview(data) {
          previewPrompt = data.prompt;
          assistantText = "";
          const imageSuffix = data.attachment_count ? ` with ${data.attachment_count} image${data.attachment_count === 1 ? "" : "s"}` : "";
          feedback.textContent = data.created_new_branch
            ? `This node already has children. Continuing in a new child branch via ${data.provider} / ${data.model_name}${imageSuffix}...`
            : `Streaming reply from ${data.provider} / ${data.model_name}${imageSuffix}...`;
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
          payload.attachments = data.node.attachments || [];
          resizePromptInput();
          feedback.textContent = "Reply added to this node.";
          renderAttachmentPanel();
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

async function handleEditVariantSubmit(event) {
  event.preventDefault();
  editVariantFeedback.textContent = "";
  const messages = collectEditedMessages();
  if (!messages.length) {
    editVariantFeedback.textContent = "This node has no messages to edit yet.";
    return;
  }
  if (messages.some((message) => !message.content)) {
    editVariantFeedback.textContent = "Every edited message needs content.";
    return;
  }

  editVariantSubmitButton.disabled = true;

  try {
    const response = await fetch(editVariantForm.dataset.editVariantUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({
        title: editVariantTitleInput.value,
        messages,
      }),
    });

    if (!response.ok) {
      throw new Error((await response.text()) || "Unable to create edited variant.");
    }

    const data = await response.json();
    if (!data.node_chat_url) {
      throw new Error("Edited variant created without a chat redirect URL.");
    }
    window.location.href = data.node_chat_url;
  } catch (error) {
    editVariantFeedback.textContent = error.message;
  } finally {
    editVariantSubmitButton.disabled = false;
  }
}

function handlePromptKeydown(event) {
  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
    form.requestSubmit();
    event.preventDefault();
  }
}

if (payload.messages.length) {
  editVariantToggleButton.hidden = false;
  editVariantToggleButton.setAttribute("aria-expanded", "false");
  editVariantToggleButton.addEventListener("click", () => setEditVariantVisible(editVariantShell.hidden));
  editVariantCancelButton.addEventListener("click", () => setEditVariantVisible(false));
  editVariantForm.addEventListener("submit", handleEditVariantSubmit);
} else {
  editVariantToggleButton.hidden = true;
}

promptInput.addEventListener("input", resizePromptInput);
promptInput.addEventListener("keydown", handlePromptKeydown);
imageInput.addEventListener("change", renderSelectedFiles);
transcript.addEventListener("scroll", updateJumpButton);
jumpButton.addEventListener("click", scrollToBottom);
form.addEventListener("submit", handleSubmit);
resizePromptInput();
renderSelectedFiles();
renderAttachmentPanel();
renderTranscript();
scrollToBottom();
