function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#96;");
}

function createPlaceholder(store, html) {
  const token = `@@MDPLACEHOLDER${store.length}@@`;
  store.push(html);
  return token;
}

function restorePlaceholders(value, placeholders) {
  let restored = value;

  placeholders.forEach((html, index) => {
    restored = restored.replaceAll(`@@MDPLACEHOLDER${index}@@`, html);
  });

  return restored;
}

function sanitizeUrl(rawUrl) {
  const url = String(rawUrl ?? "").trim().replace(/^<|>$/g, "");

  if (!url) {
    return null;
  }

  const normalized = url.toLowerCase();
  if (
    normalized.startsWith("http://")
    || normalized.startsWith("https://")
    || normalized.startsWith("mailto:")
    || normalized.startsWith("/")
    || normalized.startsWith("#")
  ) {
    return url;
  }

  return null;
}

function renderInlineMarkdown(text) {
  const placeholders = [];
  let html = escapeHtml(text);

  html = html.replace(/`([^`\n]+)`/g, (_, code) => {
    return createPlaceholder(placeholders, `<code>${code}</code>`);
  });

  html = html.replace(/\[([^\]\n]+)\]\(([^)\n]+)\)/g, (_, label, url) => {
    const safeUrl = sanitizeUrl(url);
    if (!safeUrl) {
      return label;
    }
    return createPlaceholder(
      placeholders,
      `<a href="${escapeAttribute(safeUrl)}" target="_blank" rel="noopener noreferrer">${label}</a>`,
    );
  });

  html = html.replace(/(\*\*|__)(.+?)\1/g, "<strong>$2</strong>");
  html = html.replace(/(~~)(.+?)\1/g, "<del>$2</del>");
  html = html.replace(/(\*|_)([^*_][\s\S]*?)\1/g, "<em>$2</em>");
  html = html.replace(/\n/g, "<br>");

  return restorePlaceholders(html, placeholders);
}

function isUnorderedListItem(line) {
  return /^\s*[-+*]\s+/.test(line);
}

function isOrderedListItem(line) {
  return /^\s*\d+\.\s+/.test(line);
}

function isHeading(line) {
  return /^(#{1,6})\s+/.test(line);
}

function isHorizontalRule(line) {
  return /^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/.test(line);
}

function isCodeFence(line) {
  return /^\s*```/.test(line);
}

function isBlockQuote(line) {
  return /^\s*>\s?/.test(line);
}

function startsBlock(line) {
  return isCodeFence(line) || isHeading(line) || isHorizontalRule(line) || isBlockQuote(line) || isUnorderedListItem(line) || isOrderedListItem(line);
}

function renderParagraph(lines) {
  return `<p>${renderInlineMarkdown(lines.join("\n"))}</p>`;
}

function renderListItemContent(lines) {
  const rendered = renderMarkdown(lines.join("\n"));
  if (!rendered) {
    return "";
  }
  return rendered.replace(/^<p>([\s\S]*)<\/p>$/, "$1");
}

function consumeListItems(lines, startIndex, ordered) {
  const itemPattern = ordered ? /^\s*\d+\.\s+(.*)$/ : /^\s*[-+*]\s+(.*)$/;
  const items = [];
  let index = startIndex;

  while (index < lines.length) {
    const line = lines[index];
    if (!(ordered ? isOrderedListItem(line) : isUnorderedListItem(line))) {
      break;
    }

    const itemLines = [line.match(itemPattern)?.[1] ?? ""];
    index += 1;

    while (index < lines.length) {
      const nextLine = lines[index];
      if (ordered ? isOrderedListItem(nextLine) : isUnorderedListItem(nextLine)) {
        break;
      }
      if (isHeading(nextLine) || isHorizontalRule(nextLine) || isCodeFence(nextLine) || isBlockQuote(nextLine)) {
        break;
      }
      if (!nextLine.trim()) {
        const lookahead = lines[index + 1] ?? "";
        if (ordered ? isOrderedListItem(lookahead) : isUnorderedListItem(lookahead)) {
          index += 1;
          break;
        }
      }
      itemLines.push(nextLine);
      index += 1;
    }

    items.push(itemLines);
  }

  return { items, nextIndex: index };
}

function renderList(items, ordered) {
  const tagName = ordered ? "ol" : "ul";
  const body = items
    .map((itemLines) => `<li>${renderListItemContent(itemLines)}</li>`)
    .join("");
  return `<${tagName}>${body}</${tagName}>`;
}

function renderBlockQuote(lines) {
  const innerMarkdown = lines
    .map((line) => line.replace(/^\s*>\s?/, ""))
    .join("\n");
  return `<blockquote>${renderMarkdown(innerMarkdown)}</blockquote>`;
}

function renderCodeBlock(lines) {
  const firstLine = lines[0] ?? "";
  const language = firstLine.replace(/^\s*```/, "").trim();
  const hasClosingFence = lines.length > 1 && isCodeFence(lines[lines.length - 1]);
  const code = (hasClosingFence ? lines.slice(1, -1) : lines.slice(1)).join("\n");
  const languageClass = language ? ` class="language-${escapeAttribute(language)}"` : "";
  return `<pre><code${languageClass}>${escapeHtml(code)}</code></pre>`;
}

export function renderMarkdown(source) {
  const normalized = String(source ?? "").replace(/\r\n?/g, "\n");

  if (!normalized.trim()) {
    return "";
  }

  const lines = normalized.split("\n");
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (isCodeFence(line)) {
      const codeLines = [line];
      index += 1;

      while (index < lines.length) {
        codeLines.push(lines[index]);
        if (isCodeFence(lines[index])) {
          index += 1;
          break;
        }
        index += 1;
      }

      blocks.push(renderCodeBlock(codeLines));
      continue;
    }

    if (isHeading(line)) {
      const [, hashes, content] = line.match(/^(#{1,6})\s+(.*)$/) ?? [];
      const level = hashes.length;
      blocks.push(`<h${level}>${renderInlineMarkdown(content)}</h${level}>`);
      index += 1;
      continue;
    }

    if (isHorizontalRule(line)) {
      blocks.push("<hr>");
      index += 1;
      continue;
    }

    if (isBlockQuote(line)) {
      const quoteLines = [];
      while (index < lines.length && isBlockQuote(lines[index])) {
        quoteLines.push(lines[index]);
        index += 1;
      }
      blocks.push(renderBlockQuote(quoteLines));
      continue;
    }

    if (isUnorderedListItem(line)) {
      const { items, nextIndex } = consumeListItems(lines, index, false);
      index = nextIndex;
      blocks.push(renderList(items, false));
      continue;
    }

    if (isOrderedListItem(line)) {
      const { items, nextIndex } = consumeListItems(lines, index, true);
      index = nextIndex;
      blocks.push(renderList(items, true));
      continue;
    }

    const paragraphLines = [];
    while (index < lines.length && lines[index].trim() && !startsBlock(lines[index])) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    blocks.push(renderParagraph(paragraphLines));
  }

  return blocks.join("");
}

export function setMarkdownContent(element, source) {
  element.classList.add("markdown-content");
  element.innerHTML = renderMarkdown(source);
}
