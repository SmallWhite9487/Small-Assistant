(function () {
  "use strict";

  const state = { items: [], current: null, dirty: false, mode: "write" };

  const $ = (id) => document.getElementById(id);
  const text = $("note-text");
  const title = $("note-title");

  /* ---- markdown preview ------------------------------------------------- */

  const INLINE = /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(~~[^~\n]+~~)|(\[[^\]\n]*\]\([^)\n]*\))|(\*[^*\n]+\*)|(_[^_\n]+_)/g;

  function safeUrl(url) {
    const trimmed = url.trim();
    return /^(https?:\/\/|mailto:)/i.test(trimmed) ? trimmed : null;
  }

  function appendInline(parent, source) {
    let last = 0;
    let match;
    INLINE.lastIndex = 0;
    while ((match = INLINE.exec(source))) {
      if (match.index > last) parent.append(document.createTextNode(source.slice(last, match.index)));
      const token = match[0];
      if (token.startsWith("`")) {
        const code = document.createElement("code");
        code.textContent = token.slice(1, -1);
        parent.append(code);
      } else if (token.startsWith("**")) {
        const strong = document.createElement("strong");
        strong.textContent = token.slice(2, -2);
        parent.append(strong);
      } else if (token.startsWith("~~")) {
        const del = document.createElement("del");
        del.textContent = token.slice(2, -2);
        parent.append(del);
      } else if (token.startsWith("[")) {
        const link = /^\[([^\]]*)\]\((.*)\)$/.exec(token);
        const url = link ? safeUrl(link[2]) : null;
        if (link && url) {
          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.textContent = link[1];
          anchor.target = "_blank";
          anchor.rel = "noopener noreferrer";
          parent.append(anchor);
        } else {
          parent.append(document.createTextNode(token));
        }
      } else {
        const em = document.createElement("em");
        em.textContent = token.slice(1, -1);
        parent.append(em);
      }
      last = match.index + token.length;
    }
    if (last < source.length) parent.append(document.createTextNode(source.slice(last)));
  }

  function renderMarkdown(source) {
    const fragment = document.createDocumentFragment();
    const lines = source.replace(/\r\n?/g, "\n").split("\n");
    let index = 0;

    const isBlockStart = (line) => (
      /^\s*$/.test(line)
      || /^```/.test(line)
      || /^#{1,3}\s+/.test(line)
      || /^>\s?/.test(line)
      || /^\s*(?:[-*+]|\d+\.)\s+/.test(line)
      || /^\s*([-*_])(\s*\1){2,}\s*$/.test(line)
    );

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
        const pre = document.createElement("pre");
        const code = document.createElement("code");
        code.textContent = codeLines.join("\n");
        pre.append(code);
        fragment.append(pre);
        continue;
      }

      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
        fragment.append(document.createElement("hr"));
        index += 1;
        continue;
      }

      const heading = /^(#{1,3})\s+(.*)$/.exec(line);
      if (heading) {
        const element = document.createElement("h" + heading[1].length);
        appendInline(element, heading[2]);
        fragment.append(element);
        index += 1;
        continue;
      }

      if (/^>\s?/.test(line)) {
        const quote = document.createElement("blockquote");
        const parts = [];
        while (index < lines.length && /^>\s?/.test(lines[index])) {
          parts.push(lines[index].replace(/^>\s?/, ""));
          index += 1;
        }
        const paragraph = document.createElement("p");
        appendInline(paragraph, parts.join(" "));
        quote.append(paragraph);
        fragment.append(quote);
        continue;
      }

      if (/^\s*- \[[ xX]\]\s+/.test(line)) {
        const list = document.createElement("ul");
        while (index < lines.length) {
          const task = /^\s*- \[([ xX])\]\s+(.*)$/.exec(lines[index]);
          if (!task) break;
          const item = document.createElement("li");
          item.className = "task";
          const box = document.createElement("input");
          box.type = "checkbox";
          box.disabled = true;
          box.checked = task[1].toLowerCase() === "x";
          const label = document.createElement("span");
          appendInline(label, task[2]);
          item.append(box, label);
          list.append(item);
          index += 1;
        }
        fragment.append(list);
        continue;
      }

      const bullet = /^\s*(?:[-*+]|\d+\.)\s+(.*)$/;
      if (bullet.test(line)) {
        const ordered = /^\s*\d+\.\s+/.test(line);
        const pattern = ordered ? /^\s*\d+\.\s+(.*)$/ : /^\s*[-*+]\s+(.*)$/;
        const list = document.createElement(ordered ? "ol" : "ul");
        while (index < lines.length) {
          if (/^\s*- \[[ xX]\]\s+/.test(lines[index])) break;
          const item = pattern.exec(lines[index]);
          if (!item) break;
          const li = document.createElement("li");
          appendInline(li, item[1]);
          list.append(li);
          index += 1;
        }
        fragment.append(list);
        continue;
      }

      const paragraphLines = [];
      while (index < lines.length && !isBlockStart(lines[index])) {
        paragraphLines.push(lines[index]);
        index += 1;
      }
      if (paragraphLines.length === 0) { index += 1; continue; }
      const paragraph = document.createElement("p");
      appendInline(paragraph, paragraphLines.join(" "));
      fragment.append(paragraph);
    }
    return fragment;
  }

  /* ---- list ------------------------------------------------------------- */

  function setStatus(message, dirty) {
    const status = $("note-status");
    status.textContent = message;
    status.classList.toggle("dirty", Boolean(dirty));
  }

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
    text.value = note ? note.content : "";
    setStatus(note ? "Saved" : "", false);
    if (state.mode === "preview") renderPreview();
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

  function markDirty() {
    state.dirty = true;
    setStatus("Unsaved changes", true);
    if (state.mode === "preview") renderPreview();
  }

  /* ---- preview and editor ---------------------------------------------- */

  function renderPreview() {
    $("note-preview").replaceChildren(renderMarkdown(text.value));
  }

  function setMode(mode) {
    state.mode = mode;
    for (const button of $("note-mode").querySelectorAll("[data-mode]")) {
      button.classList.toggle("active", button.dataset.mode === mode);
    }
    const preview = mode === "preview";
    text.hidden = preview;
    $("note-preview").hidden = !preview;
    if (preview) renderPreview();
    else text.focus();
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
    text.focus();
    markDirty();
  }

  function toggleLinePrefix(prefix) {
    const value = text.value;
    const selectionStart = text.selectionStart;
    const selectionEnd = text.selectionEnd;
    const blockStart = value.lastIndexOf("\n", selectionStart - 1) + 1;
    let blockEnd = value.indexOf("\n", selectionEnd);
    if (blockEnd === -1) blockEnd = value.length;
    if (selectionEnd > selectionStart && value[selectionEnd - 1] === "\n") blockEnd -= 1;

    const block = value.slice(blockStart, blockEnd);
    const lines = block.split("\n");
    const allHave = lines.every((line) => line.startsWith(prefix));
    const isHeading = /^#{1,3} /.test(prefix);
    const nextLines = lines.map((line) => {
      if (allHave) return line.slice(prefix.length);
      if (line.startsWith(prefix)) return line;
      const base = isHeading ? line.replace(/^#{1,3} /, "") : line;
      return prefix + base;
    });
    const replacement = nextLines.join("\n");
    text.value = value.slice(0, blockStart) + replacement + value.slice(blockEnd);
    text.setSelectionRange(blockStart, blockStart + replacement.length);
    text.focus();
    markDirty();
  }

  function insertLink() {
    const start = text.selectionStart;
    const end = text.selectionEnd;
    const value = text.value;
    const label = value.slice(start, end) || "text";
    const insert = "[" + label + "](https://)";
    text.value = value.slice(0, start) + insert + value.slice(end);
    const urlStart = start + label.length + 3;
    text.setSelectionRange(urlStart, urlStart + "https://".length);
    text.focus();
    markDirty();
  }

  function insertRule() {
    const start = text.selectionStart;
    const value = text.value;
    const insert = (start > 0 && value[start - 1] !== "\n" ? "\n" : "") + "---\n";
    text.value = value.slice(0, start) + insert + value.slice(start);
    text.setSelectionRange(start + insert.length, start + insert.length);
    text.focus();
    markDirty();
  }

  const TOOLS = {
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
    link: insertLink,
    rule: insertRule,
  };

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
        body: { title: noteTitle, content: text.value, old_name: state.current },
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

  text.addEventListener("input", markDirty);
  title.addEventListener("input", markDirty);
  $("new-note").addEventListener("click", newNote);
  $("note-save").addEventListener("click", save);
  $("note-delete").addEventListener("click", removeNote);

  $("note-toolbar").addEventListener("click", (event) => {
    const button = event.target.closest("[data-tool]");
    if (!button || state.mode === "preview") return;
    const tool = TOOLS[button.dataset.tool];
    if (tool) tool();
  });

  $("note-mode").addEventListener("click", (event) => {
    const button = event.target.closest("[data-mode]");
    if (!button || button.dataset.mode === state.mode) return;
    setMode(button.dataset.mode);
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
