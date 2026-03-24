import { setMarkdownContent } from "./markdown.js?v=20260324-markdown-rendering";

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

export function renderChatTranscript(container, messages) {
  container.innerHTML = "";

  if (!messages.length) {
    const empty = document.createElement("p");
    empty.className = "chat-empty-copy";
    empty.textContent = "This conversation has not started yet. Send the first message below.";
    container.appendChild(empty);
    return;
  }

  for (const message of messages) {
    const article = document.createElement("article");
    article.className = "chat-message";
    article.dataset.role = message.role;

    const label = document.createElement("span");
    label.className = "chat-message-role";
    label.textContent = message.role;

    const body = document.createElement("div");
    body.className = "chat-message-body";
    setMarkdownContent(body, message.content);

    article.append(label, body);
    container.appendChild(article);
  }
}
