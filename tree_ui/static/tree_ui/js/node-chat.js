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
const providerLabel = document.getElementById("chat-provider-label");
const modelLabel = document.getElementById("chat-model-label");
const routingDecisionLabel = document.getElementById("chat-routing-decision");
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

const toolInspector = document.getElementById("chat-tool-inspector");
const toolInspectorToggleButton = document.getElementById("tool-inspector-toggle-button");
const toolInspectorCloseButton = document.getElementById("chat-tool-inspector-close-button");
const toolSummary = document.getElementById("chat-tool-summary");
const toolList = document.getElementById("chat-tool-list");

const memoryInspector = document.getElementById("chat-memory-inspector");
const memoryInspectorToggleButton = document.getElementById("memory-inspector-toggle-button");
const memoryInspectorCloseButton = document.getElementById("chat-memory-list-close-button") || document.getElementById("chat-memory-inspector-close-button");
const memoryList = document.getElementById("chat-memory-list");

const PROMPT_MAX_HEIGHT = 176;
let stagedImages = [];
let selectedPreviewUrls = [];
let pendingPreviewAttachments = [];
let streamingToolInvocations = [];

function buildAttachmentFile(file) {
  if (file.name) {
    return file;
  }
  const extensionMap = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
  };
  const extension = extensionMap[file.type] || "png";
  return new File(
    [file],
    `pasted-image-${Date.now()}.${extension}`,
    {
      type: file.type || "image/png",
      lastModified: Date.now(),
    },
  );
}

function buildAttachmentPreview(file) {
  return {
    kind: file.type === "application/pdf" ? "pdf" : "image",
    name: file.name,
    url: file.type === "application/pdf" ? "" : URL.createObjectURL(file),
  };
}

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

function renderToolTrace() {
  if (!toolList) return;

  const allInvocations = [...(payload.tool_invocations || []), ...streamingToolInvocations];
  const retrievedMemories = (payload.memories || []).filter((memory) => memory.is_retrieved);
  const sourceLabels = Array.from(
    new Set(
      allInvocations
        .map((inv) => inv.source_id || inv.tool_call?.source_id || "")
        .filter(Boolean),
    ),
  );
  const successCount = allInvocations.filter((inv) => {
    const success = inv.success ?? inv.tool_result?.success ?? (inv.tool_result ? !inv.tool_result.is_error : false);
    return Boolean(success);
  }).length;
  const failureCount = allInvocations.filter((inv) => {
    if (!("success" in inv) && !inv.tool_result) {
      return false;
    }
    const success = inv.success ?? inv.tool_result?.success ?? !inv.tool_result?.is_error;
    return !success;
  }).length;

  if (toolSummary) {
    toolSummary.innerHTML = "";

    const summaryCard = document.createElement("div");
    summaryCard.className = "tool-trace-summary-card";

    const title = document.createElement("strong");
    title.className = "tool-trace-summary-title";
    title.textContent = "Context Snapshot";

    const copy = document.createElement("p");
    copy.className = "tool-trace-summary-copy";
    copy.textContent = `This node currently exposes ${retrievedMemories.length} retrieved memor${retrievedMemories.length === 1 ? "y" : "ies"} and ${allInvocations.length} tool invocation${allInvocations.length === 1 ? "" : "s"}.`;

    const stats = document.createElement("div");
    stats.className = "tool-trace-summary-stats";

    const statValues = [
      `Retrieved memory ${retrievedMemories.length}`,
      `Success ${successCount}`,
      `Failed ${failureCount}`,
    ];
    for (const text of statValues) {
      const pill = document.createElement("span");
      pill.className = "tool-trace-summary-pill";
      pill.textContent = text;
      stats.appendChild(pill);
    }

    summaryCard.append(title, copy, stats);

    if (sourceLabels.length) {
      const sourceRow = document.createElement("div");
      sourceRow.className = "tool-trace-summary-sources";
      const sourceLabel = document.createElement("span");
      sourceLabel.className = "tool-trace-summary-label";
      sourceLabel.textContent = "Active sources";
      sourceRow.appendChild(sourceLabel);

      for (const sourceId of sourceLabels) {
        const sourcePill = document.createElement("span");
        sourcePill.className = "tool-trace-summary-pill tool-trace-summary-pill-source";
        sourcePill.textContent = sourceId;
        sourceRow.appendChild(sourcePill);
      }

      summaryCard.appendChild(sourceRow);
    }

    toolSummary.appendChild(summaryCard);
  }

  toolList.innerHTML = "";

  if (allInvocations.length === 0) {
    const empty = document.createElement("div");
    empty.className = "chat-inspector-empty";
    empty.textContent = "No tool invocations for this node.";
    toolList.appendChild(empty);
    return;
  }

  for (const inv of allInvocations) {
    const isStreaming = !inv.id;
    const name = inv.name || inv.tool_call?.name || "Unknown Tool";
    const args = inv.args || inv.tool_call?.args;
    const result = inv.result || inv.tool_result?.result;
    const success = inv.success ?? (inv.tool_result ? !inv.tool_result.is_error : true);
    const toolType = inv.tool_type || (inv.tool_call ? "streaming" : "unknown");
    const sourceId = inv.source_id || inv.tool_result?.source_id || "";
    const createdAt = inv.created_at;

    const card = document.createElement("div");
    card.className = `tool-trace-card ${success ? 'tool-trace-success' : 'tool-trace-failure'} ${isStreaming ? 'tool-trace-streaming' : ''}`;

    const header = document.createElement("header");
    header.className = "tool-trace-header";

    const meta = document.createElement("div");
    meta.className = "tool-trace-meta";
    
    const nameSpan = document.createElement("span");
    nameSpan.className = "tool-trace-name";
    nameSpan.textContent = name;
    
    const typeBadge = document.createElement("span");
    typeBadge.className = "tool-trace-type-badge";
    typeBadge.textContent = toolType;
    
    meta.append(nameSpan, typeBadge);
    
    if (sourceId) {
      const sourceSpan = document.createElement("span");
      sourceSpan.className = "tool-trace-source";
      sourceSpan.textContent = `@ ${sourceId}`;
      meta.appendChild(sourceSpan);
    }

    const statusDiv = document.createElement("div");
    statusDiv.className = "tool-trace-status";
    
    const statusLabel = document.createElement("span");
    statusLabel.className = success ? 'status-success' : 'status-danger';
    statusLabel.textContent = success ? 'Success' : 'Failed';
    
    statusDiv.appendChild(statusLabel);
    
    if (createdAt) {
      const timeSpan = document.createElement("span");
      timeSpan.className = "tool-trace-time";
      timeSpan.textContent = new Date(createdAt).toLocaleTimeString();
      statusDiv.appendChild(timeSpan);
    }

    header.append(meta, statusDiv);

    const body = document.createElement("div");
    body.className = "tool-trace-body";

    // Args details
    const argsDetails = document.createElement("details");
    argsDetails.className = "tool-trace-details";
    if (args) argsDetails.open = true;
    const argsSummary = document.createElement("summary");
    argsSummary.textContent = "Arguments";
    const argsPre = document.createElement("pre");
    const argsCode = document.createElement("code");
    argsCode.textContent = JSON.stringify(args || {}, null, 2);
    argsPre.appendChild(argsCode);
    argsDetails.append(argsSummary, argsPre);

    // Result details
    const resDetails = document.createElement("details");
    resDetails.className = "tool-trace-details";
    if (result) resDetails.open = true;
    const resSummary = document.createElement("summary");
    resSummary.textContent = "Result";
    const resPre = document.createElement("pre");
    const resCode = document.createElement("code");
    
    let resText = "No result yet.";
    if (result) {
      resText = JSON.stringify(result, null, 2);
    } else if (isStreaming && !inv.tool_result) {
      resText = "Waiting for result...";
    }
    resCode.textContent = resText;
    
    resPre.appendChild(resCode);
    resDetails.append(resSummary, resPre);

    body.append(argsDetails, resDetails);
    card.append(header, body);
    toolList.appendChild(card);
  }
}

function renderMemoryInspector() {
  if (!memoryList) return;

  const memories = payload.memories || [];
  memoryList.innerHTML = "";

  if (memories.length === 0) {
    const empty = document.createElement("div");
    empty.className = "chat-inspector-empty";
    empty.textContent = "No long-term memories for this context.";
    memoryList.appendChild(empty);
    return;
  }

  // Sort: Retrieved first, then Pinned, then by update time
  const sorted = [...memories].sort((a, b) => {
    if (a.is_retrieved !== b.is_retrieved) return b.is_retrieved ? 1 : -1;
    if (a.is_pinned !== b.is_pinned) return b.is_pinned ? 1 : -1;
    return new Date(b.updated_at) - new Date(a.updated_at);
  });

  for (const mem of sorted) {
    const card = document.createElement("div");
    card.className = `memory-trace-card ${mem.is_retrieved ? 'memory-trace-retrieved' : ''}`;
    if (mem.is_pinned) card.classList.add('memory-trace-pinned');

    const header = document.createElement("header");
    header.className = "memory-trace-header";

    const meta = document.createElement("div");
    meta.className = "memory-trace-meta";
    
    const titleSpan = document.createElement("span");
    titleSpan.className = "memory-trace-title";
    titleSpan.textContent = mem.title;
    
    const tagsDiv = document.createElement("div");
    tagsDiv.className = "memory-trace-tags";
    
    const scopeBadge = document.createElement("span");
    scopeBadge.className = `badge memory-scope-badge scope-${mem.scope}`;
    scopeBadge.textContent = mem.scope;

    const typeBadge = document.createElement("span");
    typeBadge.className = `badge memory-type-badge type-${mem.memory_type}`;
    typeBadge.textContent = mem.memory_type;
    
    tagsDiv.append(scopeBadge, typeBadge);

    if (mem.is_pinned) {
      const pinnedBadge = document.createElement("span");
      pinnedBadge.className = "badge memory-pinned-badge";
      pinnedBadge.textContent = "Pinned";
      tagsDiv.appendChild(pinnedBadge);
    }
    meta.append(titleSpan, tagsDiv);

    const statusDiv = document.createElement("div");
    statusDiv.className = "memory-trace-status";
    
    if (mem.is_retrieved) {
      const retrievedLabel = document.createElement("span");
      retrievedLabel.className = "status-info";
      retrievedLabel.textContent = "Retrieved";
      statusDiv.appendChild(retrievedLabel);
    }
    
    if (mem.updated_at) {
      const timeSpan = document.createElement("span");
      timeSpan.className = "memory-trace-time";
      timeSpan.textContent = new Date(mem.updated_at).toLocaleDateString();
      statusDiv.appendChild(timeSpan);
    }

    header.append(meta, statusDiv);

    const body = document.createElement("div");
    body.className = "memory-trace-body";
    body.textContent = mem.content;

    card.append(header, body);

    if (mem.retrieval_reason) {
      const provenance = document.createElement("div");
      provenance.className = "memory-trace-provenance";
      provenance.textContent = mem.retrieval_reason;
      card.appendChild(provenance);
    }

    if (mem.branch_anchor_title) {
      const anchor = document.createElement("div");
      anchor.className = "memory-trace-source";
      anchor.append("Branch anchor: ");

      if (mem.branch_anchor_url) {
        const anchorLink = document.createElement("a");
        anchorLink.href = mem.branch_anchor_url;
        anchorLink.textContent = mem.branch_anchor_title;
        anchor.appendChild(anchorLink);
      } else {
        const anchorLabel = document.createElement("span");
        anchorLabel.textContent = mem.branch_anchor_title;
        anchor.appendChild(anchorLabel);
      }

      card.appendChild(anchor);
    }

    if (mem.source_node_title) {
      const source = document.createElement("div");
      source.className = "memory-trace-source";
      source.append("Source node: ");

      if (mem.source_node_url) {
        const sourceLink = document.createElement("a");
        sourceLink.href = mem.source_node_url;
        sourceLink.textContent = mem.source_node_title;
        source.appendChild(sourceLink);
      } else {
        const sourceLabel = document.createElement("span");
        sourceLabel.textContent = mem.source_node_title;
        source.appendChild(sourceLabel);
      }

      card.appendChild(source);
    }

    memoryList.appendChild(card);
  }
}

function renderTranscript(extraMessages = []) {
  const shouldStick = isNearBottom();

  const historicalItems = [...payload.messages];
  if (payload.tool_invocations) {
    for (const inv of payload.tool_invocations) {
      historicalItems.push({ tool_call: { name: inv.name, args: inv.args } });
      historicalItems.push({ tool_result: { name: inv.name, result: inv.result } });
    }
  }

  renderChatTranscript(transcript, [...historicalItems, ...extraMessages]);
  if (shouldStick) {
    scrollToBottom();
  }
  updateJumpButton();
}

function renderSelectedFiles() {
  for (const url of selectedPreviewUrls) {
    URL.revokeObjectURL(url);
  }
  selectedPreviewUrls = [];
  selectedFiles.innerHTML = "";
  selectedFiles.hidden = stagedImages.length === 0;
  if (!stagedImages.length) {
    return;
  }

  for (const [index, file] of stagedImages.entries()) {
    const card = document.createElement("div");
    card.className = "chat-selected-file";

    if (file.type === "application/pdf") {
      card.classList.add("chat-selected-file-document");
      const pdfCard = document.createElement("div");
      pdfCard.className = "chat-selected-file-pdf";

      const pdfIcon = document.createElement("span");
      pdfIcon.className = "chat-selected-file-pdf-icon";
      pdfIcon.textContent = "PDF";

      const pdfMeta = document.createElement("div");
      pdfMeta.className = "chat-selected-file-pdf-meta";

      const pdfName = document.createElement("strong");
      pdfName.textContent = file.name;

      const pdfLabel = document.createElement("span");
      pdfLabel.textContent = "Document";

      pdfMeta.append(pdfName, pdfLabel);
      pdfCard.append(pdfIcon, pdfMeta);
      card.append(pdfCard);
    } else {
      const preview = document.createElement("img");
      preview.className = "chat-selected-file-preview";
      const previewUrl = URL.createObjectURL(file);
      selectedPreviewUrls.push(previewUrl);
      preview.src = previewUrl;
      preview.alt = file.name;
      card.append(preview);
    }

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "chat-selected-file-remove";
    removeButton.setAttribute("aria-label", `Remove ${file.name}`);
    removeButton.textContent = "×";
    removeButton.addEventListener("click", () => removeSelectedFile(index));

    card.append(removeButton);
    selectedFiles.append(card);
  }
}

function removeSelectedFile(removeIndex) {
  stagedImages = stagedImages.filter((_, index) => index !== removeIndex);
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

function resetComposer({ focus = true, clearPendingAttachments = true } = {}) {
  promptInput.value = "";
  imageInput.value = "";
  stagedImages = [];
  if (clearPendingAttachments) {
    pendingPreviewAttachments = [];
  }
  renderSelectedFiles();
  resizePromptInput();
  if (focus) {
    promptInput.focus();
  }
  updateComposerState();
}

function updateComposerState() {
  const hasPrompt = Boolean(promptInput.value.trim());
  const hasImage = stagedImages.length > 0;
  submitButton.disabled = !hasPrompt && !hasImage;
}

function mergeSelectedImages(files) {
  if (!files.length) {
    return;
  }
  const existingKeys = new Set(
    stagedImages.map((file) => `${file.name}:${file.size}:${file.lastModified}`),
  );
  for (const rawFile of files) {
    const file = buildAttachmentFile(rawFile);
    const fileKey = `${file.name}:${file.size}:${file.lastModified}`;
    if (existingKeys.has(fileKey)) {
      continue;
    }
    stagedImages.push(file);
    existingKeys.add(fileKey);
  }
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
  const selectedImages = stagedImages.slice();
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
  pendingPreviewAttachments = selectedImages.map((file) => buildAttachmentPreview(file));
  resetComposer({ focus: false, clearPendingAttachments: false });
  submitButton.disabled = true;
  streamingToolInvocations = [];
  renderToolTrace();
  let previewPrompt = "";
  let assistantText = "";
  let extraStreamingMessages = [];

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
          
          extraStreamingMessages = [
            {
              role: "user",
              content: previewPrompt,
              attachments: pendingPreviewAttachments,
            },
            {
              role: "assistant",
              content: "Generating...",
            },
          ];
          renderTranscript(extraStreamingMessages);
          scrollToBottom();
        },
        delta(data) {
          assistantText += data.delta;
          const assistantMsg = extraStreamingMessages.find(m => m.role === "assistant");
          if (assistantMsg) {
            assistantMsg.content = assistantText;
          }
          renderTranscript(extraStreamingMessages);
          if (isNearBottom()) {
            scrollToBottom();
          }
        },
        tool_call(data) {
          extraStreamingMessages.push({ tool_call: data });
          streamingToolInvocations.push({ tool_call: data, name: data.name, args: data.args, tool_type: data.tool_type, source_id: data.source_id, created_at: new Date().toISOString() });
          renderTranscript(extraStreamingMessages);
          renderToolTrace();
          scrollToBottom();
        },
        tool_result(data) {
          extraStreamingMessages.push({ tool_result: data });
          const inv = streamingToolInvocations.find(i => (
            i.name === data.name ||
            (i.tool_call && i.tool_call.name === data.name) ||
            (i.tool_call && i.tool_call.id === data.id)
          ) && !i.tool_result);
          if (inv) {
            inv.tool_result = data;
            inv.result = data.result;
            inv.success = data.success ?? !data.is_error;
            inv.source_id = data.source_id || inv.source_id;
            inv.tool_type = data.tool_type || inv.tool_type;
          }
          renderTranscript(extraStreamingMessages);
          renderToolTrace();
          scrollToBottom();
        },
        node(data) {
          if (data.created_new_branch && data.node_chat_url) {
            window.location.href = data.node_chat_url;
            return;
          }
          payload.messages = data.node.messages;
          payload.attachments = data.node.attachments || [];
          payload.memories = data.node.memories || [];
          payload.tool_invocations = data.node.tool_invocations || [];
          streamingToolInvocations = [];

          if (providerLabel) {
            providerLabel.textContent = data.node.provider.charAt(0).toUpperCase() + data.node.provider.slice(1);
          }
          if (modelLabel) {
            modelLabel.textContent = data.node.model_name;
          }
          if (routingDecisionLabel && data.node.routing_decision) {
            routingDecisionLabel.textContent = `Routing decision: ${data.node.routing_decision}`;
            routingDecisionLabel.hidden = false;
          }

          feedback.textContent = "Reply added to this node.";
          for (const attachment of pendingPreviewAttachments) {
            if (attachment.url) {
              URL.revokeObjectURL(attachment.url);
            }
          }
          resetComposer();
          renderAttachmentPanel();
          renderTranscript();
          renderToolTrace();
          scrollToBottom();
        },
        error(data) {
          throw new Error(data.message || "Streaming request failed.");
        },
      },
    );
  } catch (error) {
    for (const attachment of pendingPreviewAttachments) {
      if (attachment.url) {
        URL.revokeObjectURL(attachment.url);
      }
    }
    pendingPreviewAttachments = [];
    promptInput.value = submittedPrompt;
    if (selectedImages.length) {
      stagedImages = selectedImages.slice();
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

function handlePromptPaste(event) {
  const clipboardItems = Array.from(event.clipboardData?.items || []);
  const imageFiles = clipboardItems
    .filter((item) => item.type?.startsWith("image/"))
    .map((item) => item.getAsFile())
    .filter(Boolean);

  if (!imageFiles.length) {
    return;
  }

  event.preventDefault();
  mergeSelectedImages(imageFiles);
  renderSelectedFiles();
  updateComposerState();
}

const inspectorRegistry = [
  {
    panel: toolInspector,
    toggleButton: toolInspectorToggleButton,
    closeButton: toolInspectorCloseButton,
    render: renderToolTrace,
  },
  {
    panel: memoryInspector,
    toggleButton: memoryInspectorToggleButton,
    closeButton: memoryInspectorCloseButton,
    render: renderMemoryInspector,
  },
];

function syncInspectorState(targetPanel, isOpen) {
  const entry = inspectorRegistry.find(({ panel }) => panel === targetPanel);
  if (!entry) {
    return;
  }

  entry.panel.hidden = !isOpen;
  entry.toggleButton.classList.toggle("chat-shell-action-active", isOpen);
  entry.toggleButton.setAttribute("aria-expanded", isOpen ? "true" : "false");

  if (isOpen) {
    entry.render();
  }
}

function closeAllInspectors() {
  for (const entry of inspectorRegistry) {
    syncInspectorState(entry.panel, false);
  }
}

function toggleInspector(targetPanel) {
  const shouldOpen = targetPanel.hidden;
  closeAllInspectors();
  if (shouldOpen) {
    syncInspectorState(targetPanel, true);
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

toolInspectorToggleButton.addEventListener("click", () => toggleInspector(toolInspector));
toolInspectorCloseButton.addEventListener("click", () => syncInspectorState(toolInspector, false));
memoryInspectorToggleButton.addEventListener("click", () => toggleInspector(memoryInspector));
memoryInspectorCloseButton.addEventListener("click", () => syncInspectorState(memoryInspector, false));

promptInput.addEventListener("input", resizePromptInput);
promptInput.addEventListener("input", updateComposerState);
promptInput.addEventListener("keydown", handlePromptKeydown);
promptInput.addEventListener("paste", handlePromptPaste);
attachButton.addEventListener("click", () => imageInput.click());
imageInput.addEventListener("change", () => {
  mergeSelectedImages(Array.from(imageInput.files || []));
  imageInput.value = "";
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
    return;
  }
  if (event.key === "Escape") {
    closeAllInspectors();
  }
});
jumpButton.addEventListener("click", scrollToBottom);
form.addEventListener("submit", handleSubmit);
resizePromptInput();
renderSelectedFiles();
renderAttachmentPanel();
renderTranscript();
renderToolTrace();
renderMemoryInspector();
updateComposerState();
scrollToBottom();
