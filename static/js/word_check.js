(function () {
  "use strict";

  const FIELDS = [
    ["word", "check.kanji_kana"],
    ["reading", "home.reading"],
    ["meaning", "home.meaning"],
    ["part_of_speech", "word.part_of_speech"],
  ];
  const BATCH_SIZE = 50;

  const state = {
    words: [],
    suggestions: [],
    applied: new Set(),
    provider: "online",
    pending: false,
    allMode: new URLSearchParams(location.search).get("all") === "1",
    completedIds: new Set(),
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

  function queuedWords() {
    const source = state.allMode ? state.words : flagged();
    return state.allMode
      ? source.filter((word) => !state.completedIds.has(word.id))
      : source;
  }

  function renderQueue() {
    const queue = queuedWords();
    $("flag-count").textContent = queue.length
      + (SA.t("check.words_count", { count: queue.length }))
      + SA.t(state.allMode ? "check.to_recheck" : "check.queued_suffix");
    $("run-check").disabled = queue.length === 0 || state.pending;
    const list = $("check-queue");
    list.replaceChildren();
    if (queue.length === 0) {
      const empty = document.createElement("p");
      empty.className = "placeholder-text";
      empty.textContent = state.allMode
        ? SA.t("check.no_saved")
        : SA.t("check.nothing_queued");
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
    $("run-check").disabled = queue.length === 0 || state.pending;
    $("run-check").textContent = SA.t(state.allMode ? "check.recheck_all" : "check.check_flagged");
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
      ? SA.t("check.apply_all_count", { count: pending.length })
      : SA.t("check.apply_all");
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
      same.textContent = before || SA.t("check.empty");
      value.append(same);
    } else {
      const oldText = document.createElement("span");
      oldText.className = "diff-before";
      oldText.textContent = before || SA.t("check.empty");
      const arrow = document.createElement("span");
      arrow.className = "diff-arrow";
      arrow.textContent = "→";
      const newText = document.createElement("span");
      newText.className = "diff-after";
      newText.textContent = after || SA.t("check.empty");
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
      badge.textContent = applied ? SA.t("check.applied") : changed ? SA.t("check.changes_suggested") : SA.t("check.looks_correct");
      head.append(title, badge);
      card.append(head);

      for (const [field, label] of FIELDS) {
        card.append(diffRow(field, SA.t(label), word, suggestion));
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
      apply.textContent = applied ? SA.t("check.applied") : changed ? SA.t("check.apply_corrections") : SA.t("check.no_changes");
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
        part_of_speech: suggestion.part_of_speech,
      }));
    if (payload.length === 0) return;
    if (button) SA.setBusy(button, true, SA.t("check.applying"));
    try {
      const data = await SA.api("/api/words/apply", { method: "POST", body: { changes: payload } });
      for (const updated of data.words) {
        const word = state.words.find((item) => item.id === updated.id);
        if (word) Object.assign(word, updated);
        state.applied.add(updated.id);
      }
      renderResults();
      SA.toast(SA.t("check.applied_count", { count: data.words.length }));
    } catch (error) {
      SA.toast(error.message, "error");
    } finally {
      if (button) SA.setBusy(button, false);
    }
  }

  async function runCheck() {
    if (state.pending) return;
    const queue = queuedWords();
    if (queue.length === 0) return;
    state.pending = true;
    const button = $("run-check");
    const batches = [];
    for (let index = 0; index < queue.length; index += BATCH_SIZE) {
      batches.push(queue.slice(index, index + BATCH_SIZE));
    }
    const suggestions = [];
    SA.setBusy(button, true, SA.t("check.checking_progress", { completed: 0, total: queue.length }));
    setStatus(SA.t("check.preparing", { count: batches.length }));
    $("apply-all").disabled = true;
    try {
      for (let index = 0; index < batches.length; index += 1) {
        const batch = batches[index];
        const completed = suggestions.length;
        button.textContent = SA.t("check.checking_progress", { completed, total: queue.length });
        setStatus(
          SA.t("check.checking_batch", { current: index + 1, total: batches.length, count: batch.length })
        );
        const data = await SA.api("/api/ai/check", {
          method: "POST",
          body: {
            provider: state.provider,
            language: SA.language(),
            word_ids: batch.map((word) => word.id),
          },
        });
        const checkedIds = new Set(data.suggestions.map((suggestion) => suggestion.id));
        for (const word of state.words) {
          if (checkedIds.has(word.id)) {
            word.check_ai = "False";
            state.completedIds.add(word.id);
          }
        }
        suggestions.push(...data.suggestions);
        state.suggestions = suggestions;
        renderQueue();
        renderResults();
      }
      state.applied.clear();
      state.allMode = false;
      const url = new URL(location.href);
      url.searchParams.delete("all");
      history.replaceState(null, "", url);
      renderQueue();
      renderResults();
      setStatus(
        SA.t("check.checked_done", { count: suggestions.length }),
        "ok"
      );
      SA.toast(SA.t("check.finished"));
    } catch (error) {
      setStatus(
        SA.t("check.batch_failed", { message: error.message }),
        "error"
      );
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
    setStatus(state.allMode
      ? SA.t("check.rechecking_all")
      : flagged().length
        ? SA.t("check.marked_count", { count: flagged().length })
        : SA.t("check.none"));
    if (state.allMode && state.words.length) runCheck();
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

  SA.ready.then(init);
})();
