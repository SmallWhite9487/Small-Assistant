(function () {
  "use strict";

  const state = {
    all: [],
    queue: [],
    index: 0,
    revealed: false,
    scope: "today",
    order: "random",
  };

  const $ = (id) => document.getElementById(id);

  function readSettings() {
    try {
      const scope = localStorage.getItem("sa.review.scope");
      const order = localStorage.getItem("sa.review.order");
      if (scope === "all" || scope === "today") state.scope = scope;
      if (order === "random" || order === "original") state.order = order;
    } catch (error) { /* storage may be blocked */ }
    const fromUrl = new URLSearchParams(location.search).get("scope");
    if (fromUrl === "all" || fromUrl === "today") state.scope = fromUrl;
  }

  function saveSettings() {
    try {
      localStorage.setItem("sa.review.scope", state.scope);
      localStorage.setItem("sa.review.order", state.order);
    } catch (error) { /* ignore */ }
  }

  function paintSettings() {
    for (const button of $("scope-group").querySelectorAll("[data-scope]")) {
      button.classList.toggle("active", button.dataset.scope === state.scope);
    }
    for (const button of $("order-group").querySelectorAll("[data-order]")) {
      button.classList.toggle("active", button.dataset.order === state.order);
    }
  }

  function shuffle(items) {
    for (let index = items.length - 1; index > 0; index -= 1) {
      const swap = Math.floor(Math.random() * (index + 1));
      [items[index], items[swap]] = [items[swap], items[index]];
    }
    return items;
  }

  function buildQueue() {
    const today = SA.todayISO();
    const source = state.scope === "all"
      ? state.all.slice()
      : state.all.filter((word) => word.added_on === today);
    state.queue = state.order === "random" ? shuffle(source) : source;
    state.index = 0;
    state.revealed = false;
  }

  function renderEmpty() {
    $("review-view").hidden = true;
    const empty = $("review-empty");
    empty.hidden = false;
    const action = $("review-empty-action");
    if (state.scope === "today" && state.all.length > 0) {
      $("review-empty-title").textContent = "No words added today";
      $("review-empty-copy").textContent = "Words you add today will appear here for review.";
      action.hidden = false;
      action.textContent = "Review all words instead";
      action.dataset.action = "all";
    } else if (state.all.length === 0) {
      $("review-empty-title").textContent = "No words saved yet";
      $("review-empty-copy").textContent = "Add a few words first, then come back to review them.";
      action.hidden = false;
      action.textContent = "Add your first word";
      action.dataset.action = "add";
    } else {
      $("review-empty-title").textContent = "Nothing to review";
      $("review-empty-copy").textContent = "Your list is empty for this scope.";
      action.hidden = true;
    }
    $("review-counter").textContent = "";
    $("review-progress").style.width = "0%";
  }

  function render() {
    if (state.queue.length === 0) {
      renderEmpty();
      return;
    }
    $("review-empty").hidden = true;
    $("review-view").hidden = false;

    const word = state.queue[state.index];
    $("flash-word").textContent = word.word;
    $("flash-reading").textContent = word.reading || "—";
    $("flash-meaning").textContent = word.meaning;
    $("flash-notes").textContent = word.notes || "";
    $("flash-notes").hidden = !word.notes;
    $("flash-hint-text").textContent = state.revealed ? "Answer shown — press" : "Click or press";

    const card = $("flash-card");
    card.classList.toggle("revealed", state.revealed);
    card.setAttribute("aria-label", state.revealed
      ? word.word + ". Answer shown. Press Space to hide."
      : word.word + ". Press Space to reveal the answer.");

    const conjugator = $("flash-conjugate");
    conjugator.href = "/conjugation?word=" + encodeURIComponent(word.word);

    $("review-counter").textContent = (state.index + 1) + " / " + state.queue.length;
    $("review-progress").style.width = ((state.index + 1) / state.queue.length * 100) + "%";
  }

  function toggleReveal() {
    if (state.queue.length === 0) return;
    state.revealed = !state.revealed;
    render();
  }

  function move(amount) {
    if (state.queue.length === 0) return;
    state.index = (state.index + amount + state.queue.length) % state.queue.length;
    state.revealed = false;
    render();
  }

  function rebuild() {
    buildQueue();
    paintSettings();
    render();
  }

  async function load() {
    try {
      const data = await SA.api("/api/words");
      state.all = data.words;
      rebuild();
    } catch (error) {
      SA.toast(error.message, "error");
    }
  }

  $("scope-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-scope]");
    if (!button || button.dataset.scope === state.scope) return;
    state.scope = button.dataset.scope;
    saveSettings();
    const url = new URL(location.href);
    if (state.scope === "today") url.searchParams.delete("scope");
    else url.searchParams.set("scope", state.scope);
    history.replaceState(null, "", url);
    rebuild();
  });

  $("order-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-order]");
    if (!button || button.dataset.order === state.order) return;
    state.order = button.dataset.order;
    saveSettings();
    rebuild();
  });

  $("flash-card").addEventListener("click", (event) => {
    if (event.target.closest("a")) return;
    toggleReveal();
  });

  $("review-prev").addEventListener("click", () => move(-1));
  $("review-next").addEventListener("click", () => move(1));

  $("review-empty-action").addEventListener("click", (event) => {
    if (event.target.dataset.action === "all") {
      state.scope = "all";
      saveSettings();
      rebuild();
    } else if (event.target.dataset.action === "add") {
      location.href = "/";
    }
  });

  document.addEventListener("keydown", (event) => {
    const tag = (event.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || event.target.isContentEditable) return;
    if (document.querySelector("dialog[open]") || event.metaKey || event.ctrlKey || event.altKey) return;
    if ((event.key === " " || event.key === "Enter") && event.target.closest("button, a")) return;
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      toggleReveal();
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      move(1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      move(-1);
    }
  });

  readSettings();
  paintSettings();
  load();
})();
