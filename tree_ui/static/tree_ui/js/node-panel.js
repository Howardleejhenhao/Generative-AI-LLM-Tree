import { setMarkdownContent } from "./markdown.js?v=20260412-ordered-list-fix";

function renderMessageAttachments(container, attachments) {
  if (!attachments?.length) {
    return;
  }

  const gallery = document.createElement("div");
  gallery.className = "chat-message-attachments";

  for (const attachment of attachments) {
    if (attachment.kind === "pdf") {
      const card = attachment.url ? document.createElement("a") : document.createElement("div");
      card.className = "chat-message-file-card";

      if (attachment.url) {
        card.href = attachment.url;
        card.target = "_blank";
        card.rel = "noreferrer";
      } else {
        card.classList.add("chat-message-file-card-static");
      }

      const icon = document.createElement("span");
      icon.className = "chat-message-file-card-icon";
      icon.textContent = "PDF";

      const meta = document.createElement("div");
      meta.className = "chat-message-file-card-meta";

      const name = document.createElement("strong");
      name.textContent = attachment.name || "Attached PDF";

      const label = document.createElement("span");
      label.textContent = "PDF document";

      meta.append(name, label);
      card.append(icon, meta);
      gallery.append(card);
      continue;
    }

    if (attachment.kind !== "image" || !attachment.url) {
      continue;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "chat-message-image-button";
    button.dataset.imageSrc = attachment.url;
    button.dataset.imageName = attachment.name || "Attached image";

    const image = document.createElement("img");
    image.className = "chat-message-image";
    image.src = attachment.url;
    image.alt = attachment.name || "Attached image";
    image.loading = "lazy";

    button.append(image);
    gallery.append(button);
  }

  if (gallery.childElementCount) {
    container.append(gallery);
  }
}

function renderToolBlock(container, data, type) {
  const details = document.createElement("details");
  details.className = `chat-tool-block chat-tool-${type}`;
  const summary = document.createElement("summary");
  summary.textContent = type === "call" ? `🛠️ Tool Call: ${data.name}` : `✅ Tool Result: ${data.name}`;
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(data.args || data.result, null, 2);
  details.append(summary, pre);
  container.append(details);
}

export function renderNodeDetails(container, messages) {
  container.innerHTML = "";

  if (!messages.length) {
    const empty = document.createElement("p");
    empty.className = "chat-empty-copy";
    empty.textContent = "No messages in this node yet. Open the chat view to start the conversation.";
    container.appendChild(empty);
    return;
  }

  for (const message of messages) {
    const article = document.createElement("article");
    article.className = "message-card";
    article.dataset.role = message.role;
    const header = document.createElement("header");
    const role = document.createElement("span");
    role.className = "message-role";
    role.textContent = message.role;
    const order = document.createElement("span");
    order.className = "message-order";
    order.textContent = `#${message.order_index}`;
    header.append(role, order);

    const body = document.createElement("div");
    body.className = "message-card-body";
    setMarkdownContent(body, message.content);

    article.append(header, body);
    container.appendChild(article);
  }
}

export function renderStreamingPreview(container, prompt, assistantText) {
  renderNodeDetails(container, [
    {
      role: "user",
      content: prompt,
      order_index: 0,
    },
    {
      role: "assistant",
      content: assistantText || "Generating...",
      order_index: 1,
    },
  ]);
}

export function renderMessageEditors(container, messages) {
  container.innerHTML = "";

  for (const message of messages) {
    const label = document.createElement("label");
    label.className = "form-field";
    const title = document.createElement("span");
    title.textContent = `${message.role} message`;
    const textarea = document.createElement("textarea");
    textarea.rows = 4;
    textarea.dataset.role = message.role;
    textarea.dataset.orderIndex = String(message.order_index);
    textarea.value = message.content;
    label.append(title, textarea);
    container.appendChild(label);
  }
}

export function renderChatTranscript(container, messages, options = {}) {
  const { renderActions } = options;
  container.innerHTML = "";

  if (!messages.length) {
    return;
  }

  for (const message of messages) {
    if (message.tool_call) {
      renderToolBlock(container, message.tool_call, "call");
      continue;
    }
    if (message.tool_result) {
      renderToolBlock(container, message.tool_result, "result");
      continue;
    }

    const article = document.createElement("article");
    article.className = "chat-message";
    article.dataset.role = message.role;

    const label = document.createElement("span");
    label.className = "chat-message-role";
    label.textContent = message.role;

    const body = document.createElement("div");
    body.className = "chat-message-body";
    if (!message.content && (message.attachments || []).length) {
      body.classList.add("chat-message-body-media-only");
    }
    setMarkdownContent(body, message.content);
    renderMessageAttachments(body, message.attachments || []);

    article.append(label, body);

    if (typeof renderActions === "function") {
      const actions = renderActions(message);
      if (actions) {
        article.append(actions);
      }
    }

    container.appendChild(article);
  }
}
