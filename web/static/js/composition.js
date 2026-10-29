(function () {
  "use strict";

  const KEY = "sa.composition";
  const state = {
    words: [],
    drawn: [],
    count: 5,
    provider: "local",
    feedback: null,
    pending: false,
  };

  const $ = (id) => document.getElementById(id);

  function saveState() {
    try {
      sessionStorage.setItem(KEY, JSON.stringify({
        drawn: state.drawn.map((word) => word.id),
        count: state.count,
        text: $("comp-text").value,
        provider: state.provider,
        feedback: state.feedback,
      }));
    } catch (error) { /* ignore */ }
  }

  function setStatus(message, kind) {
    const status = $("comp-status");
    status.textContent = message || "";
    status.className = "comp-status" + (kind ? " " + kind : "");
  }

  function updateCount() {
    const length = $("comp-text").value.length;
    $("char-count").textContent = length + (length === 1 ? " character" : " characters");
  }

  function setPlaceholder() {
    $("chips").replaceChildren();
    const placeholder = document.createElement("span");
    placeholder.className = "placeholder-text";
    placeholder.textContent = "Press “Draw words” to get started.";
    $("chips").append(placeholder);
  }

  function renderChips() {
    if (state.drawn.length === 0) {
      setPlaceholder();
      return;
    }
    const wrap = $("chips");
    wrap.replaceChildren();
    state.drawn.forEach((word, index) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.title = "Click to swap “" + word.word + "”";
      const label = document.createElement("span");
      label.textContent = word.word;
      chip.append(label);
      if (word.reading && word.reading !== word.word) {
        const reading = document.createElement("span");
        reading.className = "chip-reading";
        reading.textContent = word.reading;
        chip.append(reading);
      }
      chip.addEventListener("click", () => swapWord(index));
      wrap.append(chip);
    });
  }

  function renderFeedback() {
    const box = $("feedback");
    if (!state.feedback) {
      const placeholder = document.createElement("span");
      placeholder.className = "placeholder-text";
      placeholder.textContent = "Your corrected composition and evaluation will appear here.";
      box.replaceChildren(placeholder);
      return;
    }
    box.replaceChildren();
    for (const [label, value] of [["Corrected", state.feedback.corrected], ["Evaluation", state.feedback.evaluation]]) {
      const block = document.createElement("div");
      block.className = "feedback-block";
      const heading = document.createElement("span");
      heading.className = "feedback-label";
      heading.textContent = label;
      const body = document.createElement("div");
      body.textContent = value;
      block.append(heading, body);
      box.append(block);
    }
  }

  function paintSettings() {
    for (const button of $("count-group").querySelectorAll("[data-count]")) {
      button.classList.toggle("active", Number(button.dataset.count) === state.count);
    }
    for (const button of $("provider-group").querySelectorAll("[data-provider]")) {
      button.classList.toggle("active", button.dataset.provider === state.provider);
    }
  }

  function swapWord(index) {
    const used = new Set(state.drawn.map((word) => word.id));
    const pool = state.words.filter((word) => !used.has(word.id));
    if (pool.length === 0) {
      setStatus("No other saved words to swap in.", "error");
      return;
    }
    state.drawn[index] = pool[Math.floor(Math.random() * pool.length)];
    state.feedback = null;
    renderChips();
    renderFeedback();
    setStatus("");
    saveState();
  }

  function drawWords() {
    if (state.words.length < state.count) {
      setStatus("You need at least " + state.count + " saved words (you have " + state.words.length + ").", "error");
      return;
    }
    const pool = state.words.slice();
    for (let index = pool.length - 1; index > 0; index -= 1) {
      const swap = Math.floor(Math.random() * (index + 1));
      [pool[index], pool[swap]] = [pool[swap], pool[index]];
    }
    state.drawn = pool.slice(0, state.count);
    state.feedback = null;
    $("comp-text").value = "";
    updateCount();
    renderChips();
    renderFeedback();
    setStatus("");
    saveState();
    $("comp-text").focus();
  }

  async function submit() {
    if (state.pending) return;
    if (state.drawn.length === 0) {
      setStatus("Draw words first.", "error");
      return;
    }
    const text = $("comp-text").value.trim();
    if (!text) {
      setStatus("Write something first.", "error");
      return;
    }
    state.pending = true;
    const button = $("submit-composition");
    SA.setBusy(button, true, "Marking…");
    setStatus("Marking…");
    state.feedback = null;
    renderFeedback();
    saveState();
    try {
      const data = await SA.api("/api/ai/composition", {
        method: "POST",
        body: {
          words: state.drawn.map((word) => word.word),
          text: text,
          provider: state.provider,
        },
      });
      state.feedback = { corrected: data.corrected, evaluation: data.evaluation };
      renderFeedback();
      setStatus("Marking ready", "ok");
      saveState();
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      state.pending = false;
      SA.setBusy(button, false);
    }
  }

  async function init() {
    let saved = null;
    try { saved = JSON.parse(sessionStorage.getItem(KEY) || "null"); } catch (error) { saved = null; }
    if (saved) {
      if (saved.count === 5 || saved.count === 10) state.count = saved.count;
      if (saved.provider === "local" || saved.provider === "online") state.provider = saved.provider;
      if (typeof saved.text === "string") $("comp-text").value = saved.text;
      if (saved.feedback && typeof saved.feedback.corrected === "string" && typeof saved.feedback.evaluation === "string") {
        state.feedback = saved.feedback;
      }
      state.savedDrawn = Array.isArray(saved.drawn) ? saved.drawn : [];
    }
    paintSettings();
    updateCount();
    renderFeedback();

    try {
      const data = await SA.api("/api/words");
      state.words = data.words;
    } catch (error) {
      SA.toast(error.message, "error");
    }
    if (state.savedDrawn) {
      const byId = new Map(state.words.map((word) => [word.id, word]));
      state.drawn = state.savedDrawn.map((id) => byId.get(id)).filter(Boolean);
    }
    renderChips();
    $("draw-note").textContent = state.words.length + " words in your list";
  }

  $("count-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-count]");
    if (!button) return;
    state.count = Number(button.dataset.count);
    paintSettings();
    saveState();
  });

  $("provider-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-provider]");
    if (!button) return;
    state.provider = button.dataset.provider;
    paintSettings();
    saveState();
  });

  $("draw-words").addEventListener("click", drawWords);
  $("submit-composition").addEventListener("click", submit);
  $("comp-text").addEventListener("input", () => {
    updateCount();
    saveState();
  });

  init();
})();
