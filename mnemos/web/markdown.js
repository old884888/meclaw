function renderMarkdown(text, options = {}) {
  if (!text) return "";
  const wikiLinks = options.wikiLinks !== false;
  let src = String(text).replace(/\r\n/g, "\n");

  const blocks = [];
  src = src.replace(/```([\s\S]*?)```/g, (_, code) => {
    const key = `@@BLOCK${blocks.length}@@`;
    blocks.push(`<pre class="md-pre"><code>${escapeHtml(code.trim())}</code></pre>`);
    return key;
  });

  const lines = src.split("\n");
  const out = [];
  let inUl = false;
  let inOl = false;

  const closeLists = () => {
    if (inUl) {
      out.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      out.push("</ol>");
      inOl = false;
    }
  };

  const inline = (line) => {
    let html = escapeHtml(line);
    html = html.replace(/`([^`\n]+)`/g, "<code class=\"md-code\">$1</code>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    if (wikiLinks) {
      html = html.replace(/\[\[([^\]]+)\]\]/g, (_, title) => {
        const label = title.trim();
        return `<a href="#" class="wiki-link" data-wiki-title="${encodeURIComponent(label)}">${escapeHtml(label)}</a>`;
      });
    }
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, url) => {
      const href = String(url).trim();
      if (!/^https?:\/\//i.test(href)) return escapeHtml(`[${label}](${url})`);
      return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
    });
    return html;
  };

  const isTableRow = (line) => {
    const trimmed = String(line || "").trim();
    return trimmed.startsWith("|") && trimmed.endsWith("|") && trimmed.length > 2;
  };

  const isTableSeparator = (line) => /^\|[\s:|-]+\|$/.test(String(line || "").trim());

  const parseTableCells = (line) =>
    String(line || "")
      .trim()
      .slice(1, -1)
      .split("|")
      .map((cell) => cell.trim());

  const renderTable = (headerCells, bodyRows) => {
    const head = headerCells.map((cell) => `<th>${inline(cell)}</th>`).join("");
    const body = bodyRows
      .map((row) => `<tr>${row.map((cell) => `<td>${inline(cell)}</td>`).join("")}</tr>`)
      .join("");
    return `<div class="md-table-wrap"><table class="md-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  };

  const continuesListAfterBlank = (startIndex) => {
    for (let j = startIndex + 1; j < lines.length; j++) {
      const next = lines[j].trimEnd();
      if (!next.trim()) continue;
      if (inUl) return /^[-*]\s+/.test(next);
      if (inOl) return /^\d+\.\s+/.test(next);
      return false;
    }
    return false;
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const line = rawLine.trimEnd();
    if (!line.trim()) {
      if ((inUl || inOl) && continuesListAfterBlank(i)) continue;
      closeLists();
      continue;
    }
    if (isTableRow(line) && i + 1 < lines.length && isTableSeparator(lines[i + 1])) {
      closeLists();
      const headerCells = parseTableCells(line);
      i += 1;
      const bodyRows = [];
      while (i + 1 < lines.length && isTableRow(lines[i + 1])) {
        i += 1;
        bodyRows.push(parseTableCells(lines[i]));
      }
      out.push(renderTable(headerCells, bodyRows));
      continue;
    }
    if (/^---+$/.test(line.trim())) {
      closeLists();
      out.push('<hr class="md-hr">');
      continue;
    }
    if (/^#{1,3}\s+/.test(line)) {
      closeLists();
      const level = line.match(/^#+/)[0].length;
      const tag = level === 1 ? "h1" : level === 2 ? "h2" : "h3";
      out.push(`<${tag} class="md-heading">${inline(line.replace(/^#+\s+/, ""))}</${tag}>`);
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      if (!inUl) {
        closeLists();
        out.push("<ul class=\"md-list\">");
        inUl = true;
      }
      out.push(`<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`);
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      if (!inOl) {
        closeLists();
        out.push("<ol class=\"md-list\">");
        inOl = true;
      }
      out.push(`<li>${inline(line.replace(/^\d+\.\s+/, ""))}</li>`);
      continue;
    }
    closeLists();
    out.push(`<p class="md-p">${inline(line)}</p>`);
  }
  closeLists();

  let html = out.join("");
  blocks.forEach((block, idx) => {
    html = html.replace(`@@BLOCK${idx}@@`, block);
  });
  return html;
}

function wikiSlug(name) {
  return String(name || "page")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^\w\u4e00-\u9fff-]+/g, "-")
    .replace(/^-+|-+$/g, "") || "page";
}

function bindWikiLinks(container, onNavigate) {
  if (!container || !onNavigate) return;
  container.querySelectorAll(".wiki-link").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const title = decodeURIComponent(link.dataset.wikiTitle || link.textContent || "");
      onNavigate(wikiSlug(title));
    });
  });
}
