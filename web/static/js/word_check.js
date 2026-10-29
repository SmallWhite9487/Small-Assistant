(function () {
  "use strict";

  const FIELDS = [
    ["word", "Kanji / kana"],
    ["reading", "Reading"],
    ["meaning", "Meaning"],
  ];

  const state = {
    words: [],
    suggestions: [],
    applied: new Set(),
    provider: "local",
    pending: false,
  };

  const $ = (id) => document.getElementById(id);

  function setStatus(message, kind) {
    const status = $("check-status");
    status.textContent = message || "";
    status.style.color = kind === "error"
      ? "var(--danger)"
      : kind === "ok"
        ? "var(--ok)"
        : "";
  }

  function paintProvider() {
    for (const button of $("provider-group").querySelectorAll("[data-provider]")) {
      button.classList.toggle("active", button.dataset.provider === state.provider);
    }
  }

  function flagged() {
    return state.words.filter((word) => word.check_ai === "True");
  }

  function renderQueue() {
    const queue = flagged();
    $("flag-count").textContent = queue.length + (queue.length === 1 ? " word queued" : " words queued");
    $("run-check").disabled = queue.length === 0 || state.pending;
    const list = $("check-queue");
    list.replaceChildren();
    if (queue.length === 0) {
      const empty = document.createElement("p");
      empty.className = "placeholder-text";
      empty.textContent = "Nothing queued. Toggle AI check on your word list first.";
      list.append(empty);
    } else {
      for (const word of queue) {
        const row = document.createElement("div");
        row.className = "check-row";
        const w = document.createElement("span");
        w.className = "w";
        w.textContent = word.word;
        const r = document.createElement("span");
        r.className = "r";
        r.textContent = word.reading || "—";
        const m = document.createElement("span");
        m.className = "m";
        m.textContent = word.meaning;
        row.append(w, r, m);
        list.append(row);
      }
    }
    $("queue-card").hidden = queue.length === 0 && state.suggestions.length === 0;
    $("check-empty").hidden = queue.length !== 0 || state.suggestions.length !== 0;
  }

  function changedSuggestions() {
    return state.suggestions.filter((suggestion) => {
      const word = state.words.find((item) => item.id === suggestion.id);
      if (!word) return false;
      return FIELDS.some(([field]) => (word[field] || "") !== (suggestion[field] || ""));
    });
  }

  function updateApplyAll() {
    const pending = changedSuggestions().filter((suggestion) => !state.applied.has(suggestion.id));
    $("apply-all").disabled = pending.length === 0 || state.pending;
    $("apply-all").textContent = pending.length > 0
      ? "Apply all AI changes (" + pending.length + ")"
      : "Apply all AI changes";
  }

  function diffRow(field, label, word, suggestion) {
    const row = document.createElement("div");
    row.className = "diff-row";
    const title = document.createElement("span");
    title.className = "diff-label";
    title.textContent = label;
    const value = document.createElement("div");
    value.className = "diff-value";
    const before = word[field] || "";
    const after = suggestion[field] || "";
    if (before === after) {
      const same = document.createElement("span");
      same.textContent = before || "(empty)";
      value.append(same);
    } else {
      const oldText = document.createElement("span");
      oldText.className = "diff-before";
      oldText.textContent = before || "(empty)";
      const arrow = document.createElement("span");
      arrow.className = "diff-arrow";
      arrow.textContent = "→";
      const newText = document.createElement("span");
      newText.className = "diff-after";
      newText.textContent = after || "(empty)";
      value.append(oldText, arrow, newText);
    }
    row.append(title, value);
    return row;
  }

  function renderResults() {
    const wrap = $("check-results");
    wrap.replaceChildren();
    state.suggestions.forEach((suggestion, index) => {
      const word = state.words.find((item) => item.id === suggestion.id);
      if (!word) return;
      const card = document.createElement("article");
      card.className = "check-card";

      const head = document.createElement("div");
      head.className = "check-card-head";
      const title = document.createElement("span");
      title.className = "w";
      title.textContent = word.word;
      const applied = state.applied.has(suggestion.id);
      const changed = FIELDS.some(([field]) => (word[field] || "") !== (suggestion[field] || ""));
      const badge = document.createElement("span");
      badge.className = "badge " + (applied ? "green" : changed ? "warn" : "");
      badge.textContent = applied ? "Applied" : changed ? "Changes suggested" : "Looks correct";
      head.append(title, badge);
      card.append(head);

      for (const [field, label] of FIELDS) {
        card.append(diffRow(field, label, word, suggestion));
      }

      if (suggestion.reason) {
        const reason = document.createElement("p");
        reason.className = "check-reason";
        reason.textContent = suggestion.reason;
        card.append(reason);
      }

      const foot = document.createElement("div");
      foot.className = "check-card-foot";
      const apply = document.createElement("button");
      apply.type = "button";
      apply.className = "btn sm primary";
      apply.textContent = applied ? "Applied" : changed ? "Apply corrections" : "No changes needed";
      apply.disabled = applied || !changed;
      apply.addEventListener("click", () => applySuggestions([suggestion], apply));
      foot.append(apply);
      card.append(foot);
      wrap.append(card);
    });
    updateApplyAll();
  }

  async function applySuggestions(items, button) {
    const payload = items
      .filter((suggestion) => state.words.some((word) => word.id === suggestion.id))
      .map((suggestion) => ({
        id: suggestion.id,
        word: suggestion.word,
        reading: suggestion.reading,
        meaning: suggestion.meaning,
      }));
    if (payload.length === 0) return;
    if (button) SA.setBusy(button, true, "Applying…");
    try {
      const data = await SA.api("/api/words/apply", { method: "POST", body: { changes: payload } });
      for (const updated of data.words) {
        const word = state.words.find((item) => item.id === updated.id);
        if (word) Object.assign(word, updated);
        state.applied.add(updated.id);
      }
      renderResults();
      SA.toast("Applied " + data.words.length + (data.words.length === 1 ? " correction." : " corrections."));
    } catch (error) {
      SA.toast(error.message, "error");
    } finally {
      if (button) SA.setBusy(button, false);
    }
  }

  async function runCheck() {
    if (state.pending) return;
    const queue = flagged();
    if (queue.length === 0) return;
    state.pending = true;
    const button = $("run-check");
    SA.setBusy(button, true, "Checking…");
    setStatus("Checking " + queue.length + " word(s) with the AI. This can take a moment…");
    $("apply-all").disabled = true;
    try {
      const data = await SA.api("/api/ai/check", {
        method: "POST",
        body: { provider: state.provider },
      });
      const checkedIds = new Set(data.suggestions.map((suggestion) => suggestion.id));
      for (const word of state.words) {
        if (checkedIds.has(word.id)) word.check_ai = "False";
      }
      state.suggestions = data.suggestions;
      state.applied.clear();
      renderQueue();
      renderResults();
      setStatus("Checked " + data.suggestions.length + " word(s). Their AI check flags are now off. Review the suggestions below.", "ok");
      SA.toast("AI check finished");
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      state.pending = false;
      SA.setBusy(button, false);
      renderQueue();
      updateApplyAll();
    }
  }

  async function init() {
    try {
      const data = await SA.api("/api/words");
      state.words = data.words;
    } catch (error) {
      SA.toast(error.message, "error");
    }
    renderQueue();
    renderResults();
    setStatus(flagged().length
      ? flagged().length + " word(s) are marked for checking."
      : "No words are marked for checking.");
  }

  $("provider-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-provider]");
    if (!button) return;
    state.provider = button.dataset.provider;
    paintProvider();
  });

  $("run-check").addEventListener("click", runCheck);
  $("apply-all").addEventListener("click", () => {
    const pending = changedSuggestions().filter((suggestion) => !state.applied.has(suggestion.id));
    applySuggestions(pending, $("apply-all"));
  });

  init();
})();
