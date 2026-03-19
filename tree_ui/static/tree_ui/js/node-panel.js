export function renderNodeDetails(container, messages) {
  container.innerHTML = "";

  for (const message of messages) {
    const article = document.createElement("article");
    article.className = "message-card";
    article.dataset.role = message.role;
    article.innerHTML = `
      <header>
        <span class="message-role">${message.role}</span>
        <span class="message-order">#${message.order_index}</span>
      </header>
      <p>${message.content}</p>
    `;
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
