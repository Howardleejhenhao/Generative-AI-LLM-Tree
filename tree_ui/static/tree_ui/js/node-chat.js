import { renderChatTranscript, renderMessageEditors } from "./node-panel.js?v=20260414-message-images";
import { streamJSON } from "./streaming.js?v=20260413-image-upload";

const payload = JSON.parse(document.getElementById("node-chat-node-payload").textContent);

const chatPage = document.getElementById("chat-page");
const chatHeader = chatPage.querySelector(".chat-shell-header");
const jumpButton = document.getElementById("chat-jump-button");
const transcript = document.getElementById("chat-transcript");
const form = document.getElementById("chat-form");
const promptInput = document.getElementById("chat-prompt-input");
const attachButton = document.getElementById("chat-attach-button");
const imageInput = document.getElementById("chat-image-input");
const selectedFiles = document.getElementById("chat-selected-files");
const submitButton = document.getElementById("chat-submit-button");
const feedback = document.getElementById("chat-feedback");
const csrfToken = document.getElementById("chat-csrf-token").value;
const lightbox = document.getElementById("chat-image-lightbox");
const lightboxBackdrop = document.getElementById("chat-image-lightbox-backdrop");
const lightboxCloseButton = document.getElementById("chat-image-lightbox-close");
const lightboxImage = document.getElementById("chat-image-lightbox-image");
const lightboxCaption = document.getElementById("chat-image-lightbox-caption");
const editVariantToggleButton = document.getElementById("edit-variant-toggle-button");
const editVariantShell = document.getElementById("chat-edit-shell");
const editVariantForm = document.getElementById("edit-variant-form");
const editVariantTitleInput = document.getElementById("edit-variant-title");
const editVariantEditors = document.getElementById("edit-variant-editors");
const editVariantCancelButton = document.getElementById("edit-variant-cancel-button");
const editVariantSubmitButton = document.getElementById("edit-variant-submit-button");
const editVariantFeedback = document.getElementById("edit-variant-feedback");
const PROMPT_MAX_HEIGHT = 176;
let selectedPreviewUrls = [];
let pendingPreviewAttachments = [];

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
  for (const url of selectedPreviewUrls) {
    URL.revokeObjectURL(url);
  }
  selectedPreviewUrls = [];
  selectedFiles.innerHTML = "";
  selectedFiles.hidden = files.length === 0;
  if (!files.length) {
    return;
  }

  for (const [index, file] of files.entries()) {
    const card = document.createElement("div");
    card.className = "chat-selected-file";

    const preview = document.createElement("img");
    preview.className = "chat-selected-file-preview";
    const previewUrl = URL.createObjectURL(file);
    selectedPreviewUrls.push(previewUrl);
    preview.src = previewUrl;
    preview.alt = file.name;

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "chat-selected-file-remove";
    removeButton.setAttribute("aria-label", `Remove ${file.name}`);
    removeButton.textContent = "×";
    removeButton.addEventListener("click", () => removeSelectedFile(index));

    card.append(preview, removeButton);
    selectedFiles.append(card);
  }
}

function removeSelectedFile(removeIndex) {
  const files = Array.from(imageInput.files || []);
  const nextFiles = files.filter((_, index) => index !== removeIndex);
  const transfer = new DataTransfer();
  for (const file of nextFiles) {
    transfer.items.add(file);
  }
  imageInput.files = transfer.files;
  renderSelectedFiles();
  updateComposerState();
}

function renderAttachmentPanel() {
  document.getElementById("chat-attachment-panel")?.remove();
}

function cloneMessages(messages) {
  return messages.map((message) => ({
    role: message.role,
    content: message.content,
    order_index: message.order_index,
    attachments: message.attachments || [],
  }));
}

function openImageLightbox(src, name = "") {
  if (!src) {
    return;
  }
  lightboxImage.src = src;
  lightboxImage.alt = name || "Image preview";
  lightboxCaption.textContent = name || "";
  lightbox.hidden = false;
  document.body.classList.add("lightbox-open");
}

function closeImageLightbox() {
  lightbox.hidden = true;
  lightboxImage.removeAttribute("src");
  lightboxCaption.textContent = "";
  document.body.classList.remove("lightbox-open");
}

function resetComposer({ focus = true } = {}) {
  promptInput.value = "";
  imageInput.value = "";
  pendingPreviewAttachments = [];
  renderSelectedFiles();
  resizePromptInput();
  if (focus) {
    promptInput.focus();
  }
  updateComposerState();
}

function updateComposerState() {
  const hasPrompt = Boolean(promptInput.value.trim());
  const hasImage = Boolean((imageInput.files || []).length);
  submitButton.disabled = !hasPrompt && !hasImage;
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
  const selectedImages = Array.from(imageInput.files || []);
  const trimmedPrompt = submittedPrompt.trim();
  if (!trimmedPrompt && !selectedImages.length) {
    feedback.textContent = "Type a message or attach an image.";
    return;
  }

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
  pendingPreviewAttachments = selectedImages.map((file) => ({
    kind: "image",
    name: file.name,
    url: URL.createObjectURL(file),
  }));
  resetComposer({ focus: false });
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
              attachments: pendingPreviewAttachments,
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
              attachments: pendingPreviewAttachments,
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
          feedback.textContent = "Reply added to this node.";
          for (const attachment of pendingPreviewAttachments) {
            URL.revokeObjectURL(attachment.url);
          }
          resetComposer();
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
    for (const attachment of pendingPreviewAttachments) {
      URL.revokeObjectURL(attachment.url);
    }
    pendingPreviewAttachments = [];
    promptInput.value = submittedPrompt;
    if (selectedImages.length) {
      const transfer = new DataTransfer();
      for (const file of selectedImages) {
        transfer.items.add(file);
      }
      imageInput.files = transfer.files;
      renderSelectedFiles();
    }
    resizePromptInput();
    updateComposerState();
    feedback.textContent = error.message;
    renderTranscript();
  } finally {
    updateComposerState();
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
  if (event.key === "Enter" && !event.shiftKey) {
    form.requestSubmit();
    event.preventDefault();
  }
}

function handlePreviewClick(event) {
  const previewTrigger = event.target.closest("[data-image-src]");
  if (!previewTrigger) {
    return;
  }
  event.preventDefault();
  openImageLightbox(previewTrigger.dataset.imageSrc, previewTrigger.dataset.imageName || "");
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
promptInput.addEventListener("input", updateComposerState);
promptInput.addEventListener("keydown", handlePromptKeydown);
attachButton.addEventListener("click", () => imageInput.click());
imageInput.addEventListener("change", () => {
  renderSelectedFiles();
  updateComposerState();
  promptInput.focus();
});
transcript.addEventListener("scroll", updateJumpButton);
transcript.addEventListener("click", handlePreviewClick);
lightboxBackdrop.addEventListener("click", closeImageLightbox);
lightboxCloseButton.addEventListener("click", closeImageLightbox);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !lightbox.hidden) {
    closeImageLightbox();
  }
});
jumpButton.addEventListener("click", scrollToBottom);
form.addEventListener("submit", handleSubmit);
resizePromptInput();
renderSelectedFiles();
renderAttachmentPanel();
renderTranscript();
updateComposerState();
scrollToBottom();
