(function () {
  "use strict";

  const state = {
    all: [],
    queue: [],
    index: 0,
    revealed: false,
    scope: "all",
    order: "random",
    posFilter: null,
    revealedAt: 0,
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
    const source = state.scope === "all"
      ? state.all.slice()
      : state.all.filter((word) => word.added_on === SA.todayISO());
    const filtered = state.posFilter
      ? source.filter((word) => state.posFilter.matches(word))
      : source;
    state.queue = state.order === "random" ? shuffle(filtered) : filtered;
    state.index = 0;
    state.revealed = false;
  }

  function renderEmpty() {
    $("review-view").hidden = true;
    const empty = $("review-empty");
    empty.hidden = false;
    const action = $("review-empty-action");
    if (state.posFilter && state.posFilter.tags.length > 0) {
      $("review-empty-title").textContent = SA.t("review.no_matching");
      $("review-empty-copy").textContent = SA.t("review.no_matching_help");
      action.hidden = true;
    } else if (state.scope === "today" && state.all.length > 0) {
      $("review-empty-title").textContent = SA.t("review.no_words_today");
      $("review-empty-copy").textContent = SA.t("review.no_words_today_help");
      action.hidden = false;
      action.textContent = SA.t("review.review_all");
      action.dataset.action = "all";
    } else if (state.all.length === 0) {
      $("review-empty-title").textContent = SA.t("review.no_words");
      $("review-empty-copy").textContent = SA.t("review.no_words_help");
      action.hidden = false;
      action.textContent = SA.t("review.add_first_word");
      action.dataset.action = "add";
    } else {
      $("review-empty-title").textContent = SA.t("review.nothing");
      $("review-empty-copy").textContent = SA.t("review.nothing_help");
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
    $("flash-pos").textContent = word.part_of_speech ? "#." + word.part_of_speech : "";
    $("flash-pos").hidden = !word.part_of_speech;
    $("flash-notes").textContent = word.notes || "";
    $("flash-notes").hidden = !word.notes;
    $("flash-hint-text").textContent = state.revealed ? SA.t("review.answer_shown") : SA.t("review.click_or_press");

    const card = $("flash-card");
    card.classList.toggle("revealed", state.revealed);
    card.setAttribute("aria-label", state.revealed
      ? SA.t("review.card_answer_aria", { word: word.word })
      : SA.t("review.card_question_aria", { word: word.word }));

    const conjugator = $("flash-conjugate");
    conjugator.href = SA.conjugationUrl(word);

    $("review-counter").textContent = SA.t("review.position", { current: state.index + 1, total: state.queue.length });
    $("review-progress").style.width = ((state.index + 1) / state.queue.length * 100) + "%";
  }

  function toggleReveal() {
    if (state.queue.length === 0) return;
    state.revealed = !state.revealed;
    state.revealedAt = state.revealed ? performance.now() : 0;
    render();
  }

  function speak(slow) {
    if (!("speechSynthesis" in window) || state.queue.length === 0) {
      SA.toast(SA.t("review.tts_unavailable"), "error");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(state.queue[state.index].reading || state.queue[state.index].word);
    utterance.lang = "ja-JP";
    utterance.rate = slow ? 0.5 : 1;
    window.speechSynthesis.speak(utterance);
  }

  async function grade(rating) {
    if (!state.revealed || state.queue.length === 0) return;
    const word = state.queue[state.index];
    for (const button of $("review-grade").querySelectorAll("button")) button.disabled = true;
    try {
      const data = await SA.api("/api/study/" + encodeURIComponent(word.id) + "/grade", {
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
      for (const button of $("review-grade").querySelectorAll("button")) button.disabled = false;
    }
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
      state.posFilter.setOptions(state.all);
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
    if (state.scope === "all") url.searchParams.delete("scope");
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

  state.posFilter = SATagFilter($("review-pos-filter"), rebuild);

  $("flash-card").addEventListener("click", (event) => {
    if (event.target.closest("a, button")) return;
    toggleReveal();
  });

  $("review-prev").addEventListener("click", () => move(-1));
  $("review-next").addEventListener("click", () => move(1));
  $("speak-word").addEventListener("click", (event) => {
    event.stopPropagation();
    speak(false);
  });
  $("speak-slow").addEventListener("click", (event) => {
    event.stopPropagation();
    speak(true);
  });
  $("review-grade").addEventListener("click", (event) => {
    const button = event.target.closest("[data-rating]");
    if (button) grade(button.dataset.rating);
  });

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
  SA.ready.then(load);
})();
