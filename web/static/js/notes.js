(function () {
  "use strict";

  const state = { items: [], current: null, dirty: false, mode: "rich" };

  const $ = (id) => document.getElementById(id);
  const text = $("note-text");
  const editor = $("note-editor");
  const title = $("note-title");

  /* ========================================================================
     Markdown -> DOM (built with createElement/textContent only, never HTML)
     ===================================================================== */

  const INLINE_SOURCE = [
    "(`+)([^`\\n]+?)\\1",
    "\\\\([\\\\`*~\\[\\]#>+\\-.!_])",
    "\\*\\*\\*(?=\\S)([^\\n]+?)(?<=\\S)\\*\\*\\*",
    "\\*\\*(?=\\S)([^\\n]+?)(?<=\\S)\\*\\*",
    "~~(?=\\S)([^\\n]+?)(?<=\\S)~~",
    "\\[([^\\]\\n]*)\\]\\(([^)\\s\\n]*)\\)",
    "\\*(?=[^\\s*])([^\\n]*?)(?<=[^\\s*])\\*",
  ].join("|");

  function safeUrl(url) {
    const trimmed = url.trim();
    return /^(https?:\/\/|mailto:)/i.test(trimmed) ? trimmed : null;
  }

  function el(tag, className) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    return node;
  }

  function appendInline(parent, source) {
    let last = 0;
    let match;
    // A fresh regex per call: recursion would otherwise reset a shared lastIndex and loop forever.
    const INLINE = new RegExp(INLINE_SOURCE, "g");
    while ((match = INLINE.exec(source))) {
      if (match.index > last) parent.append(source.slice(last, match.index));
      if (match[1]) {
        const code = el("code");
        code.textContent = match[2];
        parent.append(code);
      } else if (match[3]) {
        parent.append(match[3]);
      } else if (match[4] !== undefined) {
        const strong = el("strong");
        const em = el("em");
        appendInline(em, match[4]);
        strong.append(em);
        parent.append(strong);
      } else if (match[5] !== undefined) {
        const strong = el("strong");
        appendInline(strong, match[5]);
        parent.append(strong);
      } else if (match[6] !== undefined) {
        const del = el("del");
        appendInline(del, match[6]);
        parent.append(del);
      } else if (match[7] !== undefined) {
        const url = safeUrl(match[8]);
        if (url) {
          const anchor = el("a");
          anchor.href = url;
          anchor.target = "_blank";
          anchor.rel = "noopener noreferrer";
          appendInline(anchor, match[7]);
          parent.append(anchor);
        } else {
          parent.append(match[0]);
        }
      } else {
        const em = el("em");
        appendInline(em, match[9]);
        parent.append(em);
      }
      last = match.index + match[0].length;
    }
    if (last < source.length) parent.append(source.slice(last));
  }

  const LIST_RE = /^(\s*)([-*+]|\d+\.)\s+(.*)$/;
  const HR_RE = /^\s*([-*_])(\s*\1){2,}\s*$/;
  const HEADING_RE = /^(#{1,6})\s+(.*)$/;

  function isBlockStart(line) {
    return /^\s*$/.test(line)
      || /^```/.test(line)
      || HEADING_RE.test(line)
      || /^>\s?/.test(line)
      || LIST_RE.test(line)
      || HR_RE.test(line);
  }

  function parseList(lines, start) {
    const first = LIST_RE.exec(lines[start]);
    const base = first[1].length;
    const ordered = /^\d/.test(first[2]);
    const list = el(ordered ? "ol" : "ul");
    let index = start;
    let lastItem = null;
    while (index < lines.length) {
      const match = LIST_RE.exec(lines[index]);
      if (!match || HR_RE.test(lines[index])) break;
      const indent = match[1].length;
      if (indent < base) break;
      if (indent > base && lastItem) {
        const nested = parseList(lines, index);
        lastItem.append(nested.list);
        index = nested.next;
        continue;
      }
      if (/^\d/.test(match[2]) !== ordered) break;

      const item = el("li");
      const task = /^\[([ xX])\]\s+(.*)$/.exec(match[3]);
      if (task) {
        item.className = "task";
        const box = el("input");
        box.type = "checkbox";
        box.checked = task[1].toLowerCase() === "x";
        box.contentEditable = "false";
        const label = el("span", "task-text");
        appendInline(label, task[2]);
        item.append(box, label);
      } else {
        appendInline(item, match[3]);
      }
      list.append(item);
      lastItem = item;
      index += 1;
    }
    return { list, next: Math.max(index, start + 1) };
  }

  function renderBlocks(lines) {
    const fragment = document.createDocumentFragment();
    let index = 0;
    while (index < lines.length) {
      const line = lines[index];
      if (/^\s*$/.test(line)) { index += 1; continue; }

      if (/^```/.test(line)) {
        const codeLines = [];
        index += 1;
        while (index < lines.length && !/^```/.test(lines[index])) {
          codeLines.push(lines[index]);
          index += 1;
        }
        index += 1;
        const pre = el("pre");
        pre.textContent = codeLines.join("\n");
        if (!pre.textContent) pre.append(el("br"));
        fragment.append(pre);
        continue;
      }

      if (HR_RE.test(line)) {
        fragment.append(el("hr"));
        index += 1;
        continue;
      }

      const heading = HEADING_RE.exec(line);
      if (heading) {
        const node = el("h" + Math.min(3, heading[1].length));
        appendInline(node, heading[2].trim());
        if (!node.firstChild) node.append(el("br"));
        fragment.append(node);
        index += 1;
        continue;
      }

      if (/^>\s?/.test(line)) {
        const inner = [];
        while (index < lines.length && /^>\s?/.test(lines[index])) {
          inner.push(lines[index].replace(/^>\s?/, ""));
          index += 1;
        }
        const quote = el("blockquote");
        quote.append(renderBlocks(inner));
        fragment.append(quote);
        continue;
      }

      if (LIST_RE.test(line)) {
        const result = parseList(lines, index);
        fragment.append(result.list);
        index = result.next;
        continue;
      }

      const paragraph = el("p");
      let first = true;
      while (index < lines.length && !isBlockStart(lines[index])) {
        if (!first) paragraph.append(el("br"));
        appendInline(paragraph, lines[index].replace(/\s+$/, ""));
        first = false;
        index += 1;
      }
      if (first) { index += 1; continue; }
      fragment.append(paragraph);
    }
    return fragment;
  }

  function renderMarkdown(source) {
    const lines = source.replace(/\r\n?/g, "\n").replace(/\t/g, "  ").split("\n");
    return renderBlocks(lines);
  }

  /* ========================================================================
     DOM -> Markdown (only known tags are emitted, so pasted junk is dropped)
     ===================================================================== */

  const BLOCK_TAGS = new Set(["P", "DIV", "H1", "H2", "H3", "H4", "H5", "H6", "UL", "OL", "BLOCKQUOTE", "PRE", "HR", "LI"]);

  function escapeText(value) {
    return value.replace(/([\\`*~[\]])/g, "\\$1");
  }

  function escapeLineStart(line) {
    return line
      .replace(/^(\s*)([#>+-])/, "$1\\$2")
      .replace(/^(\s*\d+)\./, "$1\\.");
  }

  function wrapMarker(marker, inner) {
    const parts = /^(\s*)([\s\S]*?)(\s*)$/.exec(inner);
    return parts[2] ? parts[1] + marker + parts[2] + marker + parts[3] : inner;
  }

  function inlineNodes(nodes) {
    let out = "";
    for (const node of nodes) {
      if (node.nodeType === 3) {
        out += escapeText(node.nodeValue.replace(/\u200b/g, ""));
        continue;
      }
      if (node.nodeType !== 1) continue;
      const tag = node.tagName;
      if (tag === "BR") { out += "\n"; continue; }
      if (tag === "INPUT" || tag === "UL" || tag === "OL") continue;
      if (tag === "CODE") {
        const raw = node.textContent.replace(/\u200b/g, "");
        out += raw.trim() ? "`" + raw + "`" : raw;
        continue;
      }
      const inner = inlineNodes(node.childNodes);
      if (tag === "STRONG" || tag === "B") out += wrapMarker("**", inner);
      else if (tag === "EM" || tag === "I") out += wrapMarker("*", inner);
      else if (tag === "DEL" || tag === "S" || tag === "STRIKE") out += wrapMarker("~~", inner);
      else if (tag === "A") {
        const url = safeUrl(node.getAttribute("href") || "");
        out += url && inner.trim() ? "[" + inner + "](" + url + ")" : inner;
      } else out += inner;
    }
    return out;
  }

  function paragraphMd(nodes) {
    const value = inlineNodes(nodes).replace(/^\n+|\n+$/g, "");
    if (!value.trim()) return "";
    return value.split("\n").map((line) => escapeLineStart(line.replace(/\s+$/, ""))).join("\n");
  }

  function preText(node) {
    let out = "";
    for (const child of node.childNodes) {
      if (child.nodeType === 3) out += child.nodeValue.replace(/\u200b/g, "");
      else if (child.nodeType === 1) {
        if (child.tagName === "BR") out += "\n";
        else {
          const inner = preText(child);
          out += BLOCK_TAGS.has(child.tagName) && out && !out.endsWith("\n") ? "\n" + inner : inner;
        }
      }
    }
    return out;
  }

  function listMd(list, depth) {
    const ordered = list.tagName === "OL";
    const lines = [];
    let number = 1;
    for (const item of list.children) {
      if (item.tagName !== "LI") continue;
      const box = item.querySelector(":scope > input[type=checkbox]");
      const isTask = item.classList.contains("task") || Boolean(box);
      const content = [...item.childNodes].filter((n) => !(n.nodeType === 1 && ["UL", "OL", "INPUT"].includes(n.tagName)));
      const value = inlineNodes(content).replace(/\n+/g, " ").trim();
      let marker = ordered ? number + ". " : "- ";
      if (isTask) marker += box && box.checked ? "[x] " : "[ ] ";
      lines.push("  ".repeat(depth) + marker + value);
      number += 1;
      for (const child of item.children) {
        if (child.tagName === "UL" || child.tagName === "OL") lines.push(...listMd(child, depth + 1));
      }
    }
    return lines;
  }

  function blockMd(node) {
    const tag = node.tagName;
    if (/^H[1-6]$/.test(tag)) {
      const value = inlineNodes(node.childNodes).replace(/\n+/g, " ").trim();
      return value ? "#".repeat(Math.min(3, Number(tag[1]))) + " " + value : "";
    }
    if (tag === "UL" || tag === "OL") return listMd(node, 0).join("\n");
    if (tag === "BLOCKQUOTE") {
      const inner = blocksMd(node).join("\n\n");
      return inner ? inner.split("\n").map((line) => (line ? "> " + line : ">")).join("\n") : "";
    }
    if (tag === "PRE") return "```\n" + preText(node).replace(/\n$/, "") + "\n```";
    if (tag === "HR") return "---";
    if ([...node.children].some((child) => BLOCK_TAGS.has(child.tagName))) return blocksMd(node).join("\n\n");
    return paragraphMd(node.childNodes);
  }

  function blocksMd(container) {
    const out = [];
    let run = [];
    const flush = () => {
      const value = paragraphMd(run);
      run = [];
      if (value) out.push(value);
    };
    for (const child of container.childNodes) {
      if (child.nodeType === 1 && BLOCK_TAGS.has(child.tagName)) {
        flush();
        const value = blockMd(child);
        if (value) out.push(value);
      } else run.push(child);
    }
    flush();
    return out;
  }

  function serializeEditor() {
    return blocksMd(editor).join("\n\n");
  }

  /* ========================================================================
     Editor state helpers
     ===================================================================== */

  function getMarkdown() {
    return state.mode === "rich" ? serializeEditor() : text.value;
  }

  function ensureTrailingParagraph() {
    const last = editor.lastElementChild;
    if (!last || !["P", "H1", "H2", "H3"].includes(last.tagName)) {
      const p = el("p");
      p.append(el("br"));
      editor.append(p);
    }
  }

  function setEditorContent(markdown) {
    editor.replaceChildren(renderMarkdown(markdown));
    if (!editor.firstChild) {
      const p = el("p");
      p.append(el("br"));
      editor.append(p);
    }
    ensureTrailingParagraph();
  }

  function setStatus(message, dirty) {
    const status = $("note-status");
    status.textContent = message;
    status.classList.toggle("dirty", Boolean(dirty));
  }

  function markDirty() {
    state.dirty = true;
    setStatus("Unsaved changes", true);
  }

  /* ---- selection helpers ------------------------------------------------ */

  function selectionInEditor() {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return null;
    return editor.contains(selection.anchorNode) ? selection : null;
  }

  function closestIn(node, selector) {
    let current = node && node.nodeType === 3 ? node.parentElement : node;
    while (current && current !== editor) {
      if (current.matches && current.matches(selector)) return current;
      current = current.parentElement;
    }
    return null;
  }

  function currentBlock(selection) {
    return closestIn(selection.anchorNode, "p, div, h1, h2, h3, li, blockquote, pre");
  }

  function placeCaret(node, offset) {
    const range = document.createRange();
    range.setStart(node, offset);
    range.collapse(true);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function caretToStart(node) {
    placeCaret(node, 0);
  }

  /* ---- rich commands ---------------------------------------------------- */

  function command(name, value) {
    editor.focus();
    document.execCommand(name, false, value);
  }

  function toggleBlock(tag) {
    const selection = selectionInEditor();
    if (!selection) return;
    const block = closestIn(selection.anchorNode, "h1, h2, h3");
    command("formatBlock", block && block.tagName.toLowerCase() === tag ? "<p>" : "<" + tag + ">");
  }

  function toTask(item) {
    if (item.classList.contains("task")) {
      item.classList.remove("task");
      const label = item.querySelector(":scope > .task-text");
      item.querySelector(":scope > input")?.remove();
      if (label) label.replaceWith(...label.childNodes);
      return;
    }
    item.classList.add("task");
    const box = el("input");
    box.type = "checkbox";
    box.contentEditable = "false";
    const label = el("span", "task-text");
    const nested = [...item.children].filter((child) => child.tagName === "UL" || child.tagName === "OL");
    while (item.firstChild && !nested.includes(item.firstChild)) label.append(item.firstChild);
    clearBlock(label);
    item.prepend(box, label);
  }

  const TEXT_BLOCKS = new Set(["P", "DIV", "H1", "H2", "H3"]);

  function selectedTopBlocks(selection) {
    const range = selection.getRangeAt(0);
    return [...editor.children].filter((child) => range.intersectsNode(child));
  }

  // Run a DOM restructuring while keeping the caret in the same text node.
  function keepCaret(selection, fallback, work) {
    const node = selection.anchorNode;
    const offset = selection.anchorOffset;
    const result = work();
    if (node && node.nodeType === 3 && editor.contains(node)) placeCaret(node, offset);
    else if (fallback) {
      const target = typeof fallback === "function" ? fallback(result) : fallback;
      if (target) caretToStart(target);
    }
    markDirty();
    return result;
  }

  function listFromBlocks(tag, blocks) {
    const list = el(tag.toLowerCase());
    blocks.forEach((block) => {
      const item = el("li");
      if (block.tagName === "UL" || block.tagName === "OL") return;
      while (block.firstChild) item.append(block.firstChild);
      if (!item.firstChild) item.append(el("br"));
      list.append(item);
    });
    blocks[0].before(list);
    blocks.forEach((block) => block.remove());
    return list;
  }

  function listToParagraphs(list) {
    const pieces = [];
    for (const item of list.children) {
      const p = el("p");
      for (const child of [...item.childNodes]) {
        if (child.nodeType === 1 && (child.tagName === "UL" || child.tagName === "OL")) continue;
        if (child.nodeType === 1 && child.tagName === "INPUT") continue;
        if (child.nodeType === 1 && child.classList.contains("task-text")) p.append(...child.childNodes);
        else p.append(child);
      }
      if (!p.firstChild) p.append(el("br"));
      pieces.push(p);
    }
    list.replaceWith(...pieces);
    return pieces[0];
  }

  function toggleList(tag) {
    const selection = selectionInEditor();
    if (!selection) { editor.focus(); return null; }
    const blocks = selectedTopBlocks(selection);
    if (blocks.length === 0) return null;
    const first = blocks[0];

    if (first.tagName === "UL" || first.tagName === "OL") {
      return keepCaret(selection, (r) => r, () => {
        if (first.tagName === tag) return listToParagraphs(first);
        const swapped = el(tag.toLowerCase());
        swapped.append(...first.childNodes);
        first.replaceWith(swapped);
        return swapped.firstElementChild;
      });
    }
    const convertible = blocks.filter((block) => TEXT_BLOCKS.has(block.tagName));
    if (convertible.length === 0) return null;
    return keepCaret(selection, (list) => list.firstElementChild, () => listFromBlocks(tag, convertible)).firstElementChild;
  }

  function toggleTask() {
    const selection = selectionInEditor();
    if (!selection) { editor.focus(); return; }
    let item = closestIn(selection.anchorNode, "li");
    if (!item) item = toggleList("UL");
    if (!item) return;
    toTask(item);
    caretToStart(item.querySelector(":scope > .task-text") || item);
    markDirty();
  }

  function toggleQuote() {
    const selection = selectionInEditor();
    if (!selection) { editor.focus(); return; }
    const blocks = selectedTopBlocks(selection);
    if (blocks.length === 0) return;
    const first = blocks[0];
    if (first.tagName === "BLOCKQUOTE") {
      keepCaret(selection, first.firstElementChild, () => {
        const children = [...first.childNodes];
        const loose = children.every((child) => child.nodeType === 3 || !BLOCK_TAGS.has(child.tagName));
        if (loose) {
          const p = el("p");
          p.append(...first.childNodes);
          if (!p.firstChild) p.append(el("br"));
          first.replaceWith(p);
        } else first.replaceWith(...first.childNodes);
      });
      return;
    }
    const wrappable = blocks.filter((block) => TEXT_BLOCKS.has(block.tagName) || block.tagName === "UL" || block.tagName === "OL");
    if (wrappable.length === 0) return;
    keepCaret(selection, wrappable[0], () => {
      const quote = el("blockquote");
      wrappable[0].before(quote);
      wrappable.forEach((block) => quote.append(block));
    });
  }

  function toggleCode() {
    const selection = selectionInEditor();
    if (!selection) { editor.focus(); return; }
    const existing = closestIn(selection.anchorNode, "code");
    if (existing) {
      existing.replaceWith(...existing.childNodes);
      markDirty();
      return;
    }
    if (selection.isCollapsed) return;
    const range = selection.getRangeAt(0);
    const code = el("code");
    code.textContent = range.toString();
    range.deleteContents();
    range.insertNode(code);
    const tail = document.createTextNode("\u200b");
    code.after(tail);
    placeCaret(tail, 1);
    markDirty();
  }

  function insertLinkRich() {
    const selection = selectionInEditor();
    if (!selection || selection.isCollapsed) {
      SA.toast("Select some text first, then add a link.", "error");
      editor.focus();
      return;
    }
    const existing = closestIn(selection.anchorNode, "a");
    const range = selection.getRangeAt(0).cloneRange();
    const answer = window.prompt("Link address", existing ? existing.getAttribute("href") : "https://");
    if (answer === null) return;
    editor.focus();
    selection.removeAllRanges();
    selection.addRange(range);
    if (!answer.trim()) {
      command("unlink");
      return;
    }
    const url = safeUrl(answer);
    if (!url) {
      SA.toast("Links must start with http://, https:// or mailto:", "error");
      return;
    }
    command("createLink", url);
  }

  function insertRuleRich() {
    command("insertHorizontalRule");
    ensureTrailingParagraph();
    markDirty();
  }

  const RICH_TOOLS = {
    bold: () => command("bold"),
    italic: () => command("italic"),
    strike: () => command("strikeThrough"),
    code: toggleCode,
    h1: () => toggleBlock("h1"),
    h2: () => toggleBlock("h2"),
    h3: () => toggleBlock("h3"),
    bullet: () => toggleList("UL"),
    ordered: () => toggleList("OL"),
    task: toggleTask,
    quote: toggleQuote,
    link: insertLinkRich,
    rule: insertRuleRich,
  };

  /* ---- Markdown source-mode commands (textarea) ------------------------- */

  function sourceInput() {
    text.focus();
    markDirty();
  }

  function wrapSelection(marker) {
    const start = text.selectionStart;
    const end = text.selectionEnd;
    const value = text.value;
    const before = value.slice(Math.max(0, start - marker.length), start);
    const after = value.slice(end, end + marker.length);
    if (end > start && before === marker && after === marker) {
      text.value = value.slice(0, start - marker.length) + value.slice(start, end) + value.slice(end + marker.length);
      text.setSelectionRange(start - marker.length, end - marker.length);
    } else {
      text.value = value.slice(0, start) + marker + value.slice(start, end) + marker + value.slice(end);
      text.setSelectionRange(start + marker.length, end + marker.length);
    }
    sourceInput();
  }

  function toggleLinePrefix(prefix) {
    const value = text.value;
    const selectionStart = text.selectionStart;
    const selectionEnd = text.selectionEnd;
    const blockStart = value.lastIndexOf("\n", selectionStart - 1) + 1;
    let blockEnd = value.indexOf("\n", selectionEnd);
    if (blockEnd === -1) blockEnd = value.length;
    if (selectionEnd > selectionStart && value[selectionEnd - 1] === "\n") blockEnd -= 1;
    const lines = value.slice(blockStart, blockEnd).split("\n");
    const allHave = lines.every((line) => line.startsWith(prefix));
    const isHeading = /^#{1,3} /.test(prefix);
    const replacement = lines.map((line) => {
      if (allHave) return line.slice(prefix.length);
      if (line.startsWith(prefix)) return line;
      return prefix + (isHeading ? line.replace(/^#{1,3} /, "") : line);
    }).join("\n");
    text.value = value.slice(0, blockStart) + replacement + value.slice(blockEnd);
    text.setSelectionRange(blockStart, blockStart + replacement.length);
    sourceInput();
  }

  function insertLinkSource() {
    const start = text.selectionStart;
    const end = text.selectionEnd;
    const value = text.value;
    const label = value.slice(start, end) || "text";
    text.value = value.slice(0, start) + "[" + label + "](https://)" + value.slice(end);
    const urlStart = start + label.length + 3;
    text.setSelectionRange(urlStart, urlStart + "https://".length);
    sourceInput();
  }

  function insertRuleSource() {
    const start = text.selectionStart;
    const value = text.value;
    const insert = (start > 0 && value[start - 1] !== "\n" ? "\n" : "") + "---\n";
    text.value = value.slice(0, start) + insert + value.slice(start);
    text.setSelectionRange(start + insert.length, start + insert.length);
    sourceInput();
  }

  const SOURCE_TOOLS = {
    bold: () => wrapSelection("**"),
    italic: () => wrapSelection("*"),
    strike: () => wrapSelection("~~"),
    code: () => wrapSelection("`"),
    h1: () => toggleLinePrefix("# "),
    h2: () => toggleLinePrefix("## "),
    h3: () => toggleLinePrefix("### "),
    bullet: () => toggleLinePrefix("- "),
    ordered: () => toggleLinePrefix("1. "),
    task: () => toggleLinePrefix("- [ ] "),
    quote: () => toggleLinePrefix("> "),
    link: insertLinkSource,
    rule: insertRuleSource,
  };

  /* ---- Markdown shortcuts while typing --------------------------------- */

  function textBeforeCaret(block, selection) {
    const range = document.createRange();
    range.selectNodeContents(block);
    range.setEnd(selection.anchorNode, selection.anchorOffset);
    return range;
  }

  // An element with no visible content needs a <br> or the caret cannot sit in it.
  function clearBlock(block) {
    if (!block.textContent.replace(/\u200b/g, "") && !block.querySelector("br")) {
      block.replaceChildren(el("br"));
    }
  }

  function blockShortcut() {
    const selection = selectionInEditor();
    if (!selection || !selection.isCollapsed) return false;
    const block = currentBlock(selection);
    if (!block || block.tagName === "PRE") return false;
    const range = textBeforeCaret(block, selection);
    const marker = range.toString().replace(/\u200b/g, "");
    const inList = block.tagName === "LI";

    let action = null;
    if (!inList && /^#{1,3}$/.test(marker)) action = () => command("formatBlock", "<h" + marker.length + ">");
    else if (!inList && /^[-*+]$/.test(marker)) action = () => toggleList("UL");
    else if (!inList && /^\d+\.$/.test(marker)) action = () => toggleList("OL");
    else if (!inList && marker === ">") action = toggleQuote;
    else if (inList && /^\[[ xX]?\]$/.test(marker) && !block.classList.contains("task")) {
      const checked = /x/i.test(marker);
      action = () => {
        toTask(block);
        const box = block.querySelector(":scope > input");
        if (box) box.checked = checked;
        caretToStart(block.querySelector(":scope > .task-text") || block);
        markDirty();
      };
    }
    if (!action) return false;

    range.deleteContents();
    clearBlock(block);
    caretToStart(block);
    action();
    return true;
  }

  function ruleShortcut() {
    const selection = selectionInEditor();
    if (!selection || !selection.isCollapsed) return false;
    const block = currentBlock(selection);
    if (!block || block.tagName !== "P" || !/^(---|___)$/.test(block.textContent.trim())) return false;
    const next = el("p");
    next.append(el("br"));
    block.replaceWith(el("hr"), next);
    caretToStart(next);
    markDirty();
    return true;
  }

  function codeFenceShortcut() {
    const selection = selectionInEditor();
    if (!selection || !selection.isCollapsed) return false;
    const block = currentBlock(selection);
    if (!block || block.tagName !== "P" || block.textContent.trim() !== "```") return false;
    const pre = el("pre");
    pre.append(el("br"));
    block.replaceWith(pre);
    ensureTrailingParagraph();
    caretToStart(pre);
    markDirty();
    return true;
  }

  const INLINE_TYPED = /(?<![*\\])(\*\*\*|\*\*|~~|`|\*)([^\s*~`](?:[^*~`]*[^\s*~`])?)\1$/;

  function inlineShortcut() {
    const selection = selectionInEditor();
    if (!selection || !selection.isCollapsed || selection.anchorNode.nodeType !== 3) return;
    const node = selection.anchorNode;
    if (closestIn(node, "code, pre")) return;
    const before = node.nodeValue.slice(0, selection.anchorOffset);
    const match = INLINE_TYPED.exec(before);
    if (!match) return;

    const marker = match[1];
    const body = match[2].replace(/\u200b/g, "");
    const middle = node.splitText(selection.anchorOffset - match[0].length);
    const tail = middle.splitText(match[0].length);
    middle.remove();

    let element;
    if (marker === "`") {
      element = el("code");
      element.textContent = body;
    } else if (marker === "~~") {
      element = el("del");
      element.textContent = body;
    } else if (marker === "*") {
      element = el("em");
      element.textContent = body;
    } else {
      element = el("strong");
      if (marker === "***") {
        const inner = el("em");
        inner.textContent = body;
        element.append(inner);
      } else element.textContent = body;
    }
    tail.before(element);
    if (!tail.nodeValue) tail.nodeValue = "\u200b";
    placeCaret(tail, tail.nodeValue === "\u200b" ? 1 : 0);
    markDirty();
  }

  function newTaskItem(current) {
    const label = current.querySelector(":scope > .task-text");
    const next = el("li", "task");
    const box = el("input");
    box.type = "checkbox";
    box.contentEditable = "false";
    const nextLabel = el("span", "task-text");
    const selection = selectionInEditor();
    if (selection && label && label.contains(selection.anchorNode)) {
      const range = document.createRange();
      range.setStart(selection.anchorNode, selection.anchorOffset);
      range.setEnd(label, label.childNodes.length);
      nextLabel.append(range.extractContents());
    }
    clearBlock(nextLabel);
    if (label) clearBlock(label);
    next.append(box, nextLabel);
    current.after(next);
    caretToStart(nextLabel);
  }

  function handleEnter(event) {
    const selection = selectionInEditor();
    if (!selection) return;
    if (!event.shiftKey && !event.isComposing && (codeFenceShortcut() || ruleShortcut())) {
      event.preventDefault();
      return;
    }
    const item = closestIn(selection.anchorNode, "li.task");
    if (!item || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    const label = item.querySelector(":scope > .task-text");
    const empty = !label || label.textContent.replace(/\u200b/g, "").trim() === "";
    if (empty) {
      const list = item.parentElement;
      const p = el("p");
      p.append(el("br"));
      if (list.children.length === 1) list.replaceWith(p);
      else {
        item.remove();
        list.after(p);
      }
      caretToStart(p);
    } else {
      newTaskItem(item);
    }
    markDirty();
  }

  /* ---- toolbar state ---------------------------------------------------- */

  function refreshToolbar() {
    const buttons = $("note-toolbar").querySelectorAll("[data-tool]");
    const selection = state.mode === "rich" ? selectionInEditor() : null;
    const active = new Set();
    if (selection) {
      const query = (name) => { try { return document.queryCommandState(name); } catch (error) { return false; } };
      if (query("bold")) active.add("bold");
      if (query("italic")) active.add("italic");
      if (query("strikeThrough")) active.add("strike");
      const node = selection.anchorNode;
      if (closestIn(node, "code")) active.add("code");
      for (const level of [1, 2, 3]) if (closestIn(node, "h" + level)) active.add("h" + level);
      if (closestIn(node, "ul:not(:has(li.task)) li")) active.add("bullet");
      if (closestIn(node, "ol li")) active.add("ordered");
      if (closestIn(node, "li.task")) active.add("task");
      if (closestIn(node, "blockquote")) active.add("quote");
      if (closestIn(node, "a")) active.add("link");
    }
    for (const button of buttons) button.classList.toggle("active", active.has(button.dataset.tool));
  }

  /* ---- list / modes ------------------------------------------------------ */

  function renderList() {
    const list = $("note-list");
    list.replaceChildren();
    $("note-count").textContent = state.items.length;
    if (state.items.length === 0) {
      const empty = document.createElement("p");
      empty.className = "placeholder-text";
      empty.style.padding = "10px 12px";
      empty.textContent = "No notes yet. Create one to start writing.";
      list.append(empty);
      return;
    }
    for (const item of state.items) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "note-item" + (item.name === state.current ? " active" : "");
      const name = document.createElement("strong");
      name.textContent = item.title;
      const date = document.createElement("span");
      date.textContent = item.date || "—";
      button.append(name, date);
      button.addEventListener("click", () => openNote(item.name));
      list.append(button);
    }
  }

  async function loadList() {
    const data = await SA.api("/api/notes");
    state.items = data.notes;
    renderList();
  }

  async function confirmDiscard() {
    if (!state.dirty) return true;
    return SA.confirm({
      title: "Discard unsaved changes?",
      message: "This note has changes that have not been saved.",
      confirmText: "Discard",
    });
  }

  function applyNote(note) {
    state.current = note ? note.name : null;
    state.dirty = false;
    title.value = note ? note.title : "";
    const content = note ? note.content : "";
    text.value = content;
    setEditorContent(content);
    setStatus(note ? "Saved" : "", false);
    renderList();
  }

  async function openNote(name) {
    if (name === state.current && !state.dirty) return;
    if (!(await confirmDiscard())) return;
    try {
      const data = await SA.api("/api/notes/" + encodeURIComponent(name));
      applyNote(data.note);
    } catch (error) {
      SA.toast(error.message, "error");
    }
  }

  async function newNote() {
    if (!(await confirmDiscard())) return;
    applyNote(null);
    title.focus();
  }

  function setMode(mode) {
    if (mode === state.mode) return;
    if (mode === "source") text.value = serializeEditor();
    else setEditorContent(text.value);
    state.mode = mode;
    for (const button of $("note-mode").querySelectorAll("[data-mode]")) {
      button.classList.toggle("active", button.dataset.mode === mode);
    }
    text.hidden = mode !== "source";
    editor.hidden = mode !== "rich";
    if (mode === "source") text.focus();
    else editor.focus();
    refreshToolbar();
  }

  /* ---- save / delete ---------------------------------------------------- */

  async function save() {
    const noteTitle = title.value.trim();
    if (!noteTitle) {
      SA.toast("Please enter a title for the note.", "error");
      title.focus();
      return;
    }
    const button = $("note-save");
    SA.setBusy(button, true, "Saving…");
    try {
      const data = await SA.api("/api/notes", {
        method: "POST",
        body: { title: noteTitle, content: getMarkdown(), old_name: state.current },
      });
      state.current = data.note.name;
      state.dirty = false;
      setStatus("Saved", false);
      await loadList();
      SA.toast("Saved “" + data.note.title + "”");
    } catch (error) {
      SA.toast(error.message, "error");
    } finally {
      SA.setBusy(button, false);
    }
  }

  async function removeNote() {
    if (!state.current) {
      SA.toast("Choose a note first.", "error");
      return;
    }
    const ok = await SA.confirm({
      title: "Delete this note?",
      message: "The note file will be removed from the Notes folder.",
      confirmText: "Delete note",
    });
    if (!ok) return;
    try {
      await SA.api("/api/notes/" + encodeURIComponent(state.current), { method: "DELETE" });
      state.current = null;
      state.dirty = false;
      applyNote(null);
      await loadList();
      SA.toast("Note deleted");
    } catch (error) {
      SA.toast(error.message, "error");
    }
  }

  /* ---- wiring ----------------------------------------------------------- */

  document.execCommand("defaultParagraphSeparator", false, "p");
  document.execCommand("styleWithCSS", false, false);

  text.addEventListener("input", markDirty);
  title.addEventListener("input", markDirty);
  $("new-note").addEventListener("click", newNote);
  $("note-save").addEventListener("click", save);
  $("note-delete").addEventListener("click", removeNote);

  editor.addEventListener("input", (event) => {
    if (!editor.firstChild) setEditorContent("");
    markDirty();
    if (event.inputType === "insertText" && event.data && "*~`".includes(event.data)) inlineShortcut();
  });

  editor.addEventListener("change", (event) => {
    if (event.target.matches("input[type=checkbox]")) markDirty();
  });

  editor.addEventListener("keydown", (event) => {
    if (event.isComposing) return;
    if (event.key === " " && !event.metaKey && !event.ctrlKey && !event.altKey && blockShortcut()) {
      event.preventDefault();
      return;
    }
    if (event.key === "Enter") handleEnter(event);
    if (event.key === "Tab") {
      const selection = selectionInEditor();
      if (selection && closestIn(selection.anchorNode, "li")) {
        event.preventDefault();
        command(event.shiftKey ? "outdent" : "indent");
      }
    }
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      insertLinkRich();
    }
  });

  editor.addEventListener("paste", (event) => {
    event.preventDefault();
    const pasted = (event.clipboardData || window.clipboardData).getData("text/plain").replace(/\r\n?/g, "\n");
    if (!pasted) return;
    if (!pasted.includes("\n") && !/[*`~#>[-]/.test(pasted)) {
      command("insertText", pasted);
      return;
    }
    const holder = el("div");
    holder.append(renderMarkdown(pasted));
    command("insertHTML", holder.innerHTML);
  });

  editor.addEventListener("drop", (event) => event.preventDefault());

  editor.addEventListener("click", (event) => {
    const anchor = event.target.closest("a");
    if (anchor && (event.metaKey || event.ctrlKey)) window.open(anchor.href, "_blank", "noopener,noreferrer");
  });

  editor.addEventListener("beforeinput", (event) => {
    if (event.inputType === "insertParagraph" || event.inputType === "insertLineBreak") ensureTrailingParagraph();
  });

  document.addEventListener("selectionchange", refreshToolbar);

  $("note-toolbar").addEventListener("mousedown", (event) => {
    if (event.target.closest("[data-tool]") && state.mode === "rich") event.preventDefault();
  });

  $("note-toolbar").addEventListener("click", (event) => {
    const button = event.target.closest("[data-tool]");
    if (!button) return;
    const tools = state.mode === "rich" ? RICH_TOOLS : SOURCE_TOOLS;
    const tool = tools[button.dataset.tool];
    if (!tool) return;
    tool();
    if (state.mode === "rich") {
      if (!editor.firstChild) setEditorContent("");
      markDirty();
      refreshToolbar();
    }
  });

  $("note-mode").addEventListener("click", (event) => {
    const button = event.target.closest("[data-mode]");
    if (button) setMode(button.dataset.mode);
  });

  document.addEventListener("keydown", (event) => {
    if (!(event.metaKey || event.ctrlKey)) return;
    if (event.key.toLowerCase() !== "s") return;
    event.preventDefault();
    save();
  });

  window.addEventListener("beforeunload", (event) => {
    if (!state.dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  async function init() {
    try {
      await loadList();
      if (state.items.length > 0) await openNote(state.items[0].name);
      else applyNote(null);
    } catch (error) {
      SA.toast(error.message, "error");
    }
  }

  init();
})();
