(function () {
  "use strict";

  const state = { all: [], queue: [], index: 0, revealed: false, revealedAt: 0, scope: "all", order: "random", category: "" };
  const $ = (id) => document.getElementById(id);

  function shuffle(items) {
    for (let index = items.length - 1; index > 0; index -= 1) {
      const swap = Math.floor(Math.random() * (index + 1));
      [items[index], items[swap]] = [items[swap], items[index]];
    }
    return items;
  }

  function rebuild() {
    let source = state.all;
    if (state.scope === "today") source = source.filter((item) => item.added_on === SA.todayISO());
    if (state.category) source = source.filter((item) => item.category === state.category);
    state.queue = state.order === "random" ? shuffle(source.slice()) : source.slice();
    state.index = 0;
    state.revealed = false;
    render();
  }

  function renderCategories() {
    const select = $("category-filter");
    const list = Array.from(new Set(state.all.map((item) => item.category).filter(Boolean))).sort();
    select.replaceChildren(new Option(SA.t("grammar.all_categories"), ""));
    for (const name of list) select.append(new Option(name, name));
    select.value = state.category;
  }

  function setText(id, value) {
    $(id).textContent = value || "";
    $(id).hidden = !value;
  }

  function render() {
    for (const button of $("scope-group").querySelectorAll(".seg-btn")) {
      button.classList.toggle("active", button.dataset.scope === state.scope);
    }
    for (const button of $("order-group").querySelectorAll(".seg-btn")) {
      button.classList.toggle("active", button.dataset.order === state.order);
    }
    $("review-counter").textContent = "";
    $("review-progress").style.width = "0";
    if (state.queue.length === 0) {
      $("review-view").hidden = true;
      $("review-empty").hidden = false;
      return;
    }
    $("review-empty").hidden = true;
    $("review-view").hidden = false;

    const item = state.queue[state.index];
    $("flash-pattern").textContent = item.pattern;
    setText("flash-connection", item.connection);
    $("flash-meaning").textContent = item.meaning;
    setText("flash-example", item.example);
    setText("flash-category", item.category ? "#." + item.category : "");
    setText("flash-notes", item.notes);
    $("flash-hint-text").textContent = state.revealed ? SA.t("review.answer_shown") : SA.t("review.click_or_press");
    $("flash-card").classList.toggle("revealed", state.revealed);
    $("review-counter").textContent = SA.t("review.position", { current: state.index + 1, total: state.queue.length });
    $("review-progress").style.width = ((state.index + 1) / state.queue.length * 100) + "%";
  }

  function toggleReveal() {
    if (state.queue.length === 0) return;
    state.revealed = !state.revealed;
    state.revealedAt = state.revealed ? performance.now() : 0;
    render();
  }

  function move(amount) {
    if (state.queue.length === 0) return;
    state.index = (state.index + amount + state.queue.length) % state.queue.length;
    state.revealed = false;
    render();
  }

  function speak() {
    const item = state.queue[state.index];
    const text = item && (item.example || item.pattern);
    if (!text || !("speechSynthesis" in window)) {
      SA.toast(SA.t("review.tts_unavailable"), "error");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ja-JP";
    window.speechSynthesis.speak(utterance);
  }

  async function grade(rating) {
    if (!state.revealed || state.queue.length === 0) return;
    const item = state.queue[state.index];
    const buttons = $("review-grade").querySelectorAll("button");
    for (const button of buttons) button.disabled = true;
    try {
      await SA.api("/api/study/" + encodeURIComponent(item.id) + "/grade", {
        method: "POST",
        body: {
          rating,
          correct: rating !== "again",
          duration: Math.max(0, (performance.now() - state.revealedAt) / 1000),
        },
      });
      state.queue.splice(state.index, 1);
      if (state.index >= state.queue.length) state.index = 0;
      state.revealed = false;
      render();
    } catch (error) {
      SA.toast(error.message, "error");
    } finally {
      for (const button of buttons) button.disabled = false;
    }
  }

  async function load() {
    try {
      const data = await SA.api("/api/grammar");
      state.all = data.items;
      if (new URLSearchParams(location.search).get("scope") === "today") state.scope = "today";
      renderCategories();
      rebuild();
    } catch (error) {
      SA.toast(error.message, "error");
    }
  }

  $("scope-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-scope]");
    if (!button || button.dataset.scope === state.scope) return;
    state.scope = button.dataset.scope;
    rebuild();
  });
  $("order-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-order]");
    if (!button || button.dataset.order === state.order) return;
    state.order = button.dataset.order;
    rebuild();
  });
  $("category-filter").addEventListener("change", (event) => {
    state.category = event.target.value;
    rebuild();
  });
  $("flash-card").addEventListener("click", (event) => {
    if (event.target.closest("a, button")) return;
    toggleReveal();
  });
  $("review-prev").addEventListener("click", () => move(-1));
  $("review-next").addEventListener("click", () => move(1));
  $("speak-example").addEventListener("click", (event) => {
    event.stopPropagation();
    speak();
  });
  $("review-grade").addEventListener("click", (event) => {
    const button = event.target.closest("[data-rating]");
    if (button) grade(button.dataset.rating);
  });

  document.addEventListener("keydown", (event) => {
    const tag = (event.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select" || event.target.isContentEditable) return;
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

  SA.ready.then(load);
})();
