(function () {
  "use strict";

  const state = { mode: "verb", request: 0 };

  const $ = (id) => document.getElementById(id);
  const input = $("conv-input");
  const meta = $("conv-meta");
  const groups = $("conv-groups");

  const EXAMPLES = {
    verb: "Try 食べる, 書く or 勉強する.",
    adjective: "Try 高い, 静かな or 学生.",
  };

  function setMeta(content, error) {
    meta.replaceChildren();
    meta.classList.toggle("error", Boolean(error));
    if (typeof content === "string") {
      meta.textContent = content;
    } else if (content) {
      meta.append(content);
    }
  }

  function paintMode() {
    for (const button of $("mode-group").querySelectorAll("[data-mode]")) {
      button.classList.toggle("active", button.dataset.mode === state.mode);
    }
  }

  function showPlaceholder() {
    const empty = document.createElement("div");
    empty.className = "empty";
    const icon = document.createElement("span");
    icon.className = "empty-icon";
    icon.innerHTML = '<svg class="icon"><use href="#i-swap"/></svg>';
    const heading = document.createElement("h3");
    heading.textContent = state.mode === "verb" ? "Type a verb" : "Type an adjective or noun";
    const copy = document.createElement("p");
    copy.textContent = EXAMPLES[state.mode];
    empty.append(icon, heading, copy);
    groups.replaceChildren(empty);
  }

  function copyTile(tile, value) {
    if (!value || value === "—") return;
    SA.copy(value).then((ok) => {
      if (!ok) {
        SA.toast("Could not copy to the clipboard.", "error");
        return;
      }
      tile.classList.add("is-copied");
      window.setTimeout(() => tile.classList.remove("is-copied"), 700);
      SA.toast("Copied " + value);
    });
  }

  function buildTile(form) {
    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = "conv-tile" + (form.name === "原形" ? " base" : "");

    const head = document.createElement("span");
    head.className = "conv-tile-head";
    const name = document.createElement("span");
    name.className = "conv-name";
    name.textContent = form.name;
    head.append(name);

    const value = document.createElement("span");
    value.className = "conv-value";
    value.textContent = form.value || "—";
    tile.append(head, value);
    if (form.help) {
      const help = document.createElement("span");
      help.className = "conv-help";
      help.textContent = form.help;
      tile.append(help);
    }
    tile.addEventListener("click", () => copyTile(tile, form.value));
    return tile;
  }

  function render(data) {
    if (!data.recognized) {
      const text = input.value.trim();
      if (!text) {
        showPlaceholder();
        setMeta("");
      } else {
        groups.replaceChildren();
        setMeta(state.mode === "verb" ? "Not recognised as a verb." : "Not recognised as an adjective or noun.", true);
      }
      return;
    }
    const line = document.createDocumentFragment();
    const base = document.createElement("span");
    base.append("Dictionary form: ");
    const strong = document.createElement("strong");
    strong.textContent = data.base;
    base.append(strong);
    line.append(base);
    if (data.kind) {
      line.append(" · " + data.kind);
    }
    line.append(" · click a form to copy");
    setMeta(line, false);

    groups.replaceChildren();
    for (const group of data.groups) {
      const section = document.createElement("section");
      section.className = "conv-group";
      const title = document.createElement("h2");
      title.className = "conv-group-title";
      title.textContent = group.title;
      const grid = document.createElement("div");
      grid.className = "conv-grid";
      for (const form of group.forms) grid.append(buildTile(form));
      section.append(title, grid);
      groups.append(section);
    }
  }

  const lookup = SA.debounce(async () => {
    const text = input.value.trim();
    if (!text) {
      showPlaceholder();
      setMeta("");
      return;
    }
    const token = ++state.request;
    try {
      const data = await SA.api("/api/conjugation?text=" + encodeURIComponent(text) + "&mode=" + (state.mode === "verb" ? "0" : "1"));
      if (token === state.request) render(data);
    } catch (error) {
      if (token === state.request) {
        groups.replaceChildren();
        setMeta(error.message, true);
      }
    }
  }, 170);

  input.addEventListener("input", lookup);

  $("mode-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-mode]");
    if (!button || button.dataset.mode === state.mode) return;
    state.mode = button.dataset.mode;
    paintMode();
    lookup();
  });

  const params = new URLSearchParams(location.search);
  const initial = params.get("word");
  if (params.get("mode") === "adjective") {
    state.mode = "adjective";
    paintMode();
  }
  if (initial) {
    input.value = initial;
    lookup();
  } else {
    showPlaceholder();
  }
  input.focus();
})();
