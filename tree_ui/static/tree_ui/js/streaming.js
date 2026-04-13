export function getStreamingLabel(node) {
  return `Streaming transport is ready for ${node.provider} / ${node.model_name}. New generations will appear incrementally in the detail panel.`;
}

function parseEventBlock(block) {
  const lines = block.split("\n");
  let eventName = "message";
  const dataLines = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  return {
    event: eventName,
    data: dataLines.length ? JSON.parse(dataLines.join("\n")) : {},
  };
}

export async function streamJSON(url, payload, csrfToken, handlers) {
  const isFormData = payload instanceof FormData;
  const headers = {
    "X-CSRFToken": csrfToken,
    Accept: "text/event-stream",
  };
  if (!isFormData) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(url, {
    method: "POST",
    headers,
    body: isFormData ? payload : JSON.stringify(payload),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      if (!block.trim()) {
        continue;
      }
      const parsed = parseEventBlock(block);
      const handler = handlers[parsed.event];
      if (handler) {
        handler(parsed.data);
      }
    }
  }

  if (buffer.trim()) {
    const parsed = parseEventBlock(buffer);
    const handler = handlers[parsed.event];
    if (handler) {
      handler(parsed.data);
    }
  }
}
