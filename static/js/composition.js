(function () {
  "use strict";

  const KEY = "sa.composition";
  const state = {
    words: [],
    drawn: [],
    grammar: [],
    drawnGrammar: [],
    count: 5,
    provider: "online",
    feedback: null,
    feedbackLanguage: null,
    pending: false,
  };

  const $ = (id) => document.getElementById(id);

  function saveState() {
    try {
      sessionStorage.setItem(KEY, JSON.stringify({
        drawn: state.drawn.map((word) => word.id),
        drawnGrammar: state.drawnGrammar.map((item) => item.id),
        count: state.count,
        text: $("comp-text").value,
        provider: state.provider,
        feedback: state.feedback,
        feedbackLanguage: state.feedbackLanguage,
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
    $("char-count").textContent = SA.t("composition.character_count", { count: length });
  }

  function updateDrawNote() {
    $("draw-note").textContent = SA.t("composition.available_counts", {
      words: state.words.length,
      grammar: state.grammar.length,
      grammarCount: state.count === 5 ? 3 : 5,
    });
  }

  function setPlaceholder() {
    for (const id of ["word-chips", "grammar-chips"]) {
      const placeholder = document.createElement("span");
      placeholder.className = "placeholder-text";
      placeholder.textContent = SA.t("composition.draw_prompt");
      $(id).replaceChildren(placeholder);
    }
  }

  function renderChips() {
    if (state.drawn.length === 0 && state.drawnGrammar.length === 0) {
      setPlaceholder();
      return;
    }
    renderWordChips();
    renderGrammarChips();
  }

  function renderWordChips() {
    const wrap = $("word-chips");
    wrap.replaceChildren();
    state.drawn.forEach((word, index) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.title = SA.t("composition.swap_word", { word: word.word });
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
    if (state.drawn.length === 0) {
      const empty = document.createElement("span");
      empty.className = "placeholder-text";
      empty.textContent = SA.t("composition.draw_prompt");
      wrap.append(empty);
    }
  }

  function renderGrammarChips() {
    const wrap = $("grammar-chips");
    wrap.replaceChildren();
    state.drawnGrammar.forEach((item, index) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.title = SA.t("composition.swap_grammar", { grammar: item.pattern });
      const label = document.createElement("span");
      label.textContent = item.pattern;
      chip.append(label);
      if (item.connection) {
        const connection = document.createElement("span");
        connection.className = "chip-reading";
        connection.textContent = item.connection;
        chip.append(connection);
      }
      chip.addEventListener("click", () => swapGrammar(index));
      wrap.append(chip);
    });
    if (state.drawnGrammar.length === 0) {
      const empty = document.createElement("span");
      empty.className = "placeholder-text";
      empty.textContent = SA.t("composition.draw_prompt");
      wrap.append(empty);
    }
  }

  function renderFeedback() {
    const box = $("feedback");
    if (!state.feedback) {
      const placeholder = document.createElement("span");
      placeholder.className = "placeholder-text";
      placeholder.textContent = SA.t("composition.feedback_placeholder");
      box.replaceChildren(placeholder);
      return;
    }
    box.replaceChildren();
    for (const [label, value] of [[SA.t("composition.corrected"), state.feedback.corrected], [SA.t("composition.evaluation"), state.feedback.evaluation]]) {
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
      setStatus(SA.t("composition.no_other_words"), "error");
      return;
    }
    state.drawn[index] = pool[Math.floor(Math.random() * pool.length)];
    state.feedback = null;
    state.feedbackLanguage = null;
    renderChips();
    renderFeedback();
    setStatus("");
    saveState();
  }

  function swapGrammar(index) {
    const used = new Set(state.drawnGrammar.map((item) => item.id));
    const pool = state.grammar.filter((item) => !used.has(item.id));
    if (pool.length === 0) {
      setStatus(SA.t("composition.no_other_grammar"), "error");
      return;
    }
    state.drawnGrammar[index] = pool[Math.floor(Math.random() * pool.length)];
    state.feedback = null;
    state.feedbackLanguage = null;
    renderChips();
    renderFeedback();
    setStatus("");
    saveState();
  }

  function drawWords() {
    if (state.words.length < state.count) {
      setStatus(SA.t("composition.need_words", { count: state.count, available: state.words.length }), "error");
      return;
    }
    const grammarCount = state.count === 5 ? 3 : 5;
    if (state.grammar.length < grammarCount) {
      setStatus(SA.t("composition.need_grammar", {
        count: grammarCount,
        available: state.grammar.length,
      }), "error");
      return;
    }
    const pool = state.words.slice();
    for (let index = pool.length - 1; index > 0; index -= 1) {
      const swap = Math.floor(Math.random() * (index + 1));
      [pool[index], pool[swap]] = [pool[swap], pool[index]];
    }
    state.drawn = pool.slice(0, state.count);
    const grammarPool = state.grammar.slice();
    for (let index = grammarPool.length - 1; index > 0; index -= 1) {
      const swap = Math.floor(Math.random() * (index + 1));
      [grammarPool[index], grammarPool[swap]] = [grammarPool[swap], grammarPool[index]];
    }
    state.drawnGrammar = grammarPool.slice(0, grammarCount);
    state.feedback = null;
    state.feedbackLanguage = null;
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
    const grammarCount = state.count === 5 ? 3 : 5;
    if (state.drawn.length !== state.count || state.drawnGrammar.length !== grammarCount) {
      setStatus(SA.t("composition.draw_first"), "error");
      return;
    }
    const text = $("comp-text").value.trim();
    if (!text) {
      setStatus(SA.t("composition.write_first"), "error");
      return;
    }
    state.pending = true;
    const feedbackLanguage = SA.language();
    const button = $("submit-composition");
    SA.setBusy(button, true, SA.t("composition.marking"));
    setStatus(SA.t("composition.marking"));
    state.feedback = null;
    state.feedbackLanguage = null;
    renderFeedback();
    saveState();
    try {
      const data = await SA.api("/api/ai/composition", {
        method: "POST",
        body: {
          words: state.drawn.map((word) => word.word),
          grammar_points: state.drawnGrammar.map((item) => ({
            pattern: item.pattern,
            connection: item.connection,
            meaning: item.meaning,
          })),
          text: text,
          provider: state.provider,
          language: feedbackLanguage,
        },
      });
      state.feedback = { corrected: data.corrected, evaluation: data.evaluation };
      state.feedbackLanguage = feedbackLanguage;
      renderFeedback();
      setStatus(SA.t("composition.marking_ready"), "ok");
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
      
      if (typeof saved.text === "string") $("comp-text").value = saved.text;
      if (saved.feedbackLanguage === SA.language() && saved.feedback && typeof saved.feedback.corrected === "string" && typeof saved.feedback.evaluation === "string") {
        state.feedback = saved.feedback;
        state.feedbackLanguage = saved.feedbackLanguage;
      }
      state.savedDrawn = Array.isArray(saved.drawn) ? saved.drawn : [];
      state.savedDrawnGrammar = Array.isArray(saved.drawnGrammar) ? saved.drawnGrammar : [];
    }
    paintSettings();
    updateCount();
    renderFeedback();

    try {
      const [wordData, grammarData] = await Promise.all([
        SA.api("/api/words"),
        SA.api("/api/grammar"),
      ]);
      state.words = wordData.words;
      state.grammar = grammarData.items;
    } catch (error) {
      SA.toast(error.message, "error");
    }
    if (state.savedDrawn) {
      const byId = new Map(state.words.map((word) => [word.id, word]));
      state.drawn = state.savedDrawn.map((id) => byId.get(id)).filter(Boolean);
    }
    if (state.savedDrawnGrammar) {
      const byId = new Map(state.grammar.map((item) => [item.id, item]));
      state.drawnGrammar = state.savedDrawnGrammar.map((id) => byId.get(id)).filter(Boolean);
    }
    renderChips();
    updateDrawNote();
  }

  $("count-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-count]");
    if (!button) return;
    state.count = Number(button.dataset.count);
    paintSettings();
    updateDrawNote();
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

  SA.ready.then(init);
})();
