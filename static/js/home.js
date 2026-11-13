(function () {
  "use strict";

  const state = {
    words: [],
    query: "",
    filter: "all",
    posFilter: null,
    showTranslations: false,
    aiSuggestions: [],
    aiSelected: new Set(),
    aiPending: false,
  };
  const AI_FIELDS = [
    ["word", "check.kanji_kana"],
    ["reading", "home.reading"],
    ["meaning", "home.meaning"],
    ["part_of_speech", "word.part_of_speech"],
  ];
  let editing = null;
  let checkOn = true;

  const $ = (id) => document.getElementById(id);

  async function load() {
    try {
      const data = await SA.api("/api/words");
      state.words = data.words;
      state.posFilter.setOptions(state.words);
      render();
    } catch (error) {
      SA.toast(error.message, "error");
    }
  }

  function refreshStats() {
    const today = SA.todayISO();
    $("stat-total").textContent = state.words.length;
    $("stat-today").textContent = state.words.filter((item) => item.added_on === today).length;
    const flaggedCount = state.words.filter((item) => item.check_ai === "True").length;
    $("stat-flagged").textContent = flaggedCount;
    $("home-flag-count").textContent = flaggedCount;
    $("check-flagged").disabled = flaggedCount === 0 || state.aiPending;
  }

  function duplicateKey(word, reading) {
    const normalize = (value) => (value || "").normalize("NFKC").trim().toLowerCase();
    return JSON.stringify([normalize(word), normalize(reading)]);
  }

  function duplicateWordCounts() {
    const counts = new Map();
    for (const word of state.words) {
      const key = duplicateKey(word.word, word.reading);
      if (key) counts.set(key, (counts.get(key) || 0) + 1);
    }
    return counts;
  }

  function visibleWords(duplicates) {
    const query = state.query.trim().toLowerCase();
    return state.words.filter((word) => {
      if (state.filter === "flagged" && word.check_ai !== "True") return false;
      if (state.filter === "duplicates" &&
          (duplicates.get(duplicateKey(word.word, word.reading)) || 0) < 2) return false;
      if (state.posFilter && !state.posFilter.matches(word)) return false;
      if (!query) return true;
      return [word.word, word.reading, word.meaning, word.part_of_speech, word.notes]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }

  function icon(name) {
    return '<svg class="icon"><use href="#i-' + name + '"/></svg>';
  }

  function makeButton(iconName, title, handler, extraClass) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "icon-btn" + (extraClass ? " " + extraClass : "");
    button.title = title;
    button.setAttribute("aria-label", title);
    button.innerHTML = icon(iconName);
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      handler();
    });
    return button;
  }

  function aiChanged(suggestion) {
    const word = state.words.find((item) => item.id === suggestion.id);
    return word && AI_FIELDS.some(([field]) => (word[field] || "") !== (suggestion[field] || ""));
  }

  function updateAiApplyButton() {
    const hasSelection = state.aiSuggestions.some(
      (suggestion) => state.aiSelected.has(suggestion.id) && aiChanged(suggestion),
    );
    $("word-ai-apply").disabled = !hasSelection || state.aiPending;
  }

  function renderAiResults() {
    const wrap = $("word-ai-results");
    wrap.replaceChildren();
    for (const suggestion of state.aiSuggestions) {
      const word = state.words.find((item) => item.id === suggestion.id);
      if (!word) continue;
      const changed = aiChanged(suggestion);
      const card = document.createElement("article");
      card.className = "check-card";

      const head = document.createElement("div");
      head.className = "check-card-head";
      const title = document.createElement("span");
      title.className = "w";
      title.textContent = word.word;
      const badge = document.createElement("span");
      badge.className = "badge " + (changed ? "warn" : "");
      badge.textContent = changed ? SA.t("check.changes_suggested") : SA.t("check.looks_correct");
      head.append(title, badge);
      card.append(head);

      for (const [field, label] of AI_FIELDS) {
        const row = document.createElement("div");
        row.className = "diff-row";
        const name = document.createElement("span");
        name.className = "diff-label";
        name.textContent = SA.t(label);
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
        row.append(name, value);
        card.append(row);
      }

      if (suggestion.reason) {
        const reason = document.createElement("p");
        reason.className = "check-reason";
        reason.textContent = suggestion.reason;
        card.append(reason);
      }

      const foot = document.createElement("label");
      foot.className = "check-card-foot";
      foot.style.justifyContent = "flex-start";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = changed && state.aiSelected.has(suggestion.id);
      checkbox.disabled = !changed || state.aiPending;
      checkbox.setAttribute("aria-label", SA.t("check.select_word", { word: word.word }));
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) state.aiSelected.add(suggestion.id);
        else state.aiSelected.delete(suggestion.id);
        updateAiApplyButton();
      });
      const label = document.createElement("span");
      label.textContent = changed ? SA.t("check.apply_corrections") : SA.t("check.no_changes");
      foot.append(checkbox, label);
      card.append(foot);
      wrap.append(card);
    }
    updateAiApplyButton();
  }

  async function checkFlaggedWords() {
    if (state.aiPending) return;
    const queue = state.words.filter((word) => word.check_ai === "True");
    if (queue.length === 0) {
      SA.toast(SA.t("check.nothing_queued"));
      return;
    }

    state.aiPending = true;
    state.aiSuggestions = [];
    state.aiSelected.clear();
    $("check-flagged-label").textContent = SA.t("check.checking");
    $("word-ai-status").textContent = SA.t("check.checking_progress", {
      completed: 0,
      total: queue.length,
    });
    $("word-ai-dialog").showModal();
    renderAiResults();
    refreshStats();

    try {
      const batchSize = 50;
      for (let start = 0; start < queue.length; start += batchSize) {
        const batch = queue.slice(start, start + batchSize);
        $("word-ai-status").textContent = SA.t("check.checking_batch", {
          current: Math.floor(start / batchSize) + 1,
          total: Math.ceil(queue.length / batchSize),
          count: batch.length,
        });
        const data = await SA.api("/api/ai/check", {
          method: "POST",
          body: {
            provider: "online",
            language: SA.language(),
            word_ids: batch.map((word) => word.id),
          },
        });
        const checkedIds = new Set(data.suggestions.map((suggestion) => suggestion.id));
        for (const word of state.words) {
          if (checkedIds.has(word.id)) word.check_ai = "False";
        }
        state.aiSuggestions.push(...data.suggestions);
        for (const suggestion of data.suggestions) {
          if (aiChanged(suggestion)) state.aiSelected.add(suggestion.id);
        }
        refreshStats();
        renderAiResults();
      }
      $("word-ai-status").textContent = SA.t("check.checked_done", {
        count: state.aiSuggestions.length,
      });
    } catch (error) {
      $("word-ai-status").textContent = SA.t("check.batch_failed", { message: error.message });
      SA.toast(error.message, "error");
    } finally {
      state.aiPending = false;
      $("check-flagged-label").textContent = SA.t("home.check_flagged");
      refreshStats();
      renderAiResults();
    }
  }

  async function applyAiSuggestions() {
    const selected = state.aiSuggestions.filter(
      (suggestion) => state.aiSelected.has(suggestion.id) && aiChanged(suggestion),
    );
    if (!selected.length) return;
    const button = $("word-ai-apply");
    button.disabled = true;
    try {
      const changes = selected.map((suggestion) => ({
        id: suggestion.id,
        word: suggestion.word,
        reading: suggestion.reading,
        meaning: suggestion.meaning,
        part_of_speech: suggestion.part_of_speech,
      }));
      const data = await SA.api("/api/words/apply", {
        method: "POST",
        body: { changes },
      });
      for (const updated of data.words) {
        const word = state.words.find((item) => item.id === updated.id);
        if (word) Object.assign(word, updated);
      }
      $("word-ai-dialog").close();
      render();
      SA.toast(SA.t("check.applied_count", { count: data.words.length }));
    } catch (error) {
      SA.toast(error.message, "error");
    } finally {
      updateAiApplyButton();
    }
  }

  function render() {
    const rows = $("word-rows");
    rows.replaceChildren();
    const duplicates = duplicateWordCounts();
    const duplicateRecords = Array.from(duplicates.values())
      .filter((count) => count > 1)
      .reduce((total, count) => total + count, 0);
    $("duplicate-count").textContent = duplicateRecords;
    const duplicateFilter = $("filter-group").querySelector('[data-filter="duplicates"]');
    duplicateFilter.setAttribute(
      "aria-label",
      SA.t("home.duplicate_filter_aria", { count: duplicateRecords }),
    );
    const words = visibleWords(duplicates);

    for (const word of words) {
      const tr = document.createElement("tr");
      tr.dataset.id = word.id;

      const wordCell = document.createElement("td");
      wordCell.className = "w-word";
      wordCell.textContent = word.word;
      const duplicateCount = duplicates.get(duplicateKey(word.word, word.reading)) || 0;
      if (duplicateCount > 1) {
        const badge = document.createElement("span");
        badge.className = "badge warn";
        badge.textContent = SA.t("home.duplicate_badge", { count: duplicateCount });
        badge.title = SA.t("home.duplicate_badge_help", { count: duplicateCount });
        wordCell.append(" ", badge);
      }
      tr.append(wordCell);

      const readingCell = document.createElement("td");
      readingCell.className = "w-reading";
      readingCell.dataset.label = SA.t("home.reading");
      readingCell.textContent = word.reading || "—";
      tr.append(readingCell);

      const meaningCell = document.createElement("td");
      meaningCell.className = "w-meaning";
      const meaning = document.createElement("span");
      meaning.textContent = word.meaning;
      meaningCell.append(meaning);
      if (state.showTranslations && SA.language() !== "en" && SA.language() !== "dev") {
        const translated = document.createElement("span");
        translated.className = "meaning-translation";
        translated.dataset.wordId = word.id;
        translated.textContent = "…";
        meaningCell.append(translated);
      }
      meaningCell.title = word.meaning;
      tr.append(meaningCell);

      const partOfSpeechCell = document.createElement("td");
      partOfSpeechCell.className = "w-pos";
      partOfSpeechCell.dataset.label = SA.t("word.part_of_speech");
      partOfSpeechCell.textContent = word.part_of_speech || "—";
      tr.append(partOfSpeechCell);

      const dateCell = document.createElement("td");
      dateCell.className = "w-date";
      dateCell.textContent = word.added_on || "—";
      tr.append(dateCell);

      const checkCell = document.createElement("td");
      checkCell.className = "center w-check";
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "switch" + (word.check_ai === "True" ? " on" : "");
      toggle.setAttribute("role", "switch");
      toggle.setAttribute("aria-checked", word.check_ai === "True" ? "true" : "false");
      toggle.setAttribute("aria-label", SA.t("home.check_word_ai", { word: word.word }));
      toggle.addEventListener("click", (event) => {
        event.stopPropagation();
        toggleCheck(word, toggle);
      });
      checkCell.append(toggle);
      tr.append(checkCell);

      const actionCell = document.createElement("td");
      actionCell.className = "w-act";
      const actions = document.createElement("div");
      actions.className = "w-actions";
      const conjugate = document.createElement("a");
      conjugate.className = "icon-btn";
      conjugate.href = SA.conjugationUrl(word);
      conjugate.title = SA.t("home.conjugate_word", { word: word.word });
      conjugate.setAttribute("aria-label", SA.t("home.conjugate_word", { word: word.word }));
      conjugate.innerHTML = icon("swap");
      actions.append(
        conjugate,
        makeButton("pencil", SA.t("home.edit_word", { word: word.word }), () => openForm(word)),
        makeButton("trash", SA.t("home.delete_word", { word: word.word }), () => removeWord(word), "danger"),
      );
      actionCell.append(actions);
      tr.append(actionCell);

      tr.addEventListener("dblclick", (event) => {
        if (!event.target.closest("button, a")) openForm(word);
      });

      rows.append(tr);
    }

    refreshStats();
    $("table-count").textContent = words.length === state.words.length
      ? SA.t("home.word_count", { count: state.words.length })
      : SA.t("home.showing_count", { shown: words.length, total: state.words.length });

    const empty = $("word-empty");
    const scroll = $("table-scroll");
    if (words.length === 0) {
      empty.hidden = false;
      scroll.hidden = true;
      const total = state.words.length;
      $("empty-title").textContent = total === 0 ? SA.t("home.no_words") : SA.t("home.no_matching");
      $("empty-copy").textContent = total === 0
        ? SA.t("home.no_words_help")
        : SA.t("home.no_matching_help");
      $("empty-add").hidden = total !== 0;
      if (state.filter === "duplicates") {
        $("empty-title").textContent = SA.t("home.no_duplicates");
        $("empty-copy").textContent = SA.t("home.no_duplicates_help");
        $("empty-add").hidden = true;
      }
    } else {
      empty.hidden = true;
      scroll.hidden = false;
    }
  }

  async function toggleCheck(word, button) {
    const next = word.check_ai !== "True";
    button.classList.toggle("on", next);
    button.setAttribute("aria-checked", String(next));
    try {
      const data = await SA.api("/api/words/" + encodeURIComponent(word.id) + "/check", {
        method: "PATCH",
        body: { check_ai: next },
      });
      Object.assign(word, data.word);
      refreshStats();
    } catch (error) {
      button.classList.toggle("on", !next);
      button.setAttribute("aria-checked", String(!next));
      SA.toast(error.message, "error");
    }
  }

  async function removeWord(word) {
    const ok = await SA.confirm({
      title: SA.t("home.delete_title"),
      message: SA.t("home.delete_message", { word: word.word }),
      confirmText: SA.t("home.delete_confirm"),
    });
    if (!ok) return;
    try {
      await SA.api("/api/words/" + encodeURIComponent(word.id), { method: "DELETE" });
      state.words = state.words.filter((item) => item.id !== word.id);
      render();
      SA.toast(SA.t("home.deleted", { word: word.word }));
    } catch (error) {
      SA.toast(error.message, "error");
    }
  }

  /* ---- add / edit ------------------------------------------------------- */

  function setCheckSwitch(value) {
    checkOn = value;
    const button = $("w-check");
    button.classList.toggle("on", value);
    button.setAttribute("aria-checked", String(value));
  }

  function openForm(word) {
    editing = word || null;
    $("word-dialog-title").textContent = editing ? SA.t("home.edit_word_title") : SA.t("home.add_a_word");
    $("word-dialog-sub").textContent = editing
      ? SA.t("home.edit_word_help")
      : SA.t("home.add_word_help");
    $("w-word").value = editing ? editing.word : "";
    $("w-reading").value = editing ? editing.reading : "";
    $("w-meaning").value = editing ? editing.meaning : "";
    $("w-part-of-speech").value = editing ? editing.part_of_speech : "";
    $("w-notes").value = editing ? editing.notes : "";
    setCheckSwitch(editing ? editing.check_ai === "True" : true);
    $("word-save").textContent = editing ? SA.t("home.save_changes") : SA.t("home.save_word");
    $("word-dialog").showModal();
    window.setTimeout(() => $("w-word").focus(), 30);
  }

  function closeForm() {
    $("word-dialog").close();
  }

  async function submitForm(event) {
    event.preventDefault();
    const payload = {
      word: $("w-word").value.trim(),
      reading: $("w-reading").value.trim(),
      meaning: $("w-meaning").value.trim(),
      part_of_speech: $("w-part-of-speech").value.trim().toLowerCase(),
      notes: $("w-notes").value.trim(),
      check_ai: checkOn,
    };
    if (!payload.word) {
      SA.toast(SA.t("home.required_fields"), "error");
      $("w-word").focus();
      return;
    }
    const button = $("word-save");
    SA.setBusy(button, true, SA.t(editing ? "home.saving_changes" : "home.adding"));
    try {
      if (editing) {
        await SA.api("/api/words/" + encodeURIComponent(editing.id), { method: "PUT", body: payload });
        SA.toast(SA.t("home.saved_changes", { word: payload.word }));
      } else {
        await SA.api("/api/words", { method: "POST", body: payload });
        SA.toast(SA.t("home.added", { word: payload.word }));
      }
      closeForm();
      await load();
    } catch (error) {
      SA.toast(error.message, "error");
    } finally {
      SA.setBusy(button, false);
    }
  }

  /* ---- wiring ----------------------------------------------------------- */

  $("search").addEventListener("input", (event) => {
    state.query = event.target.value;
    render();
  });

  $("translate-meanings").addEventListener("click", () => {
    if ((SA.language() === "en" || SA.language() === "dev")) {
      SA.toast(SA.t("home.choose_translation_language"));
      return;
    }
    state.showTranslations = !state.showTranslations;
    $("translate-meanings").classList.toggle("active", state.showTranslations);
    render();
    if (state.showTranslations) translateVisibleMeanings();
  });

  async function translateVisibleMeanings() {
    const targets = Array.from(document.querySelectorAll(".meaning-translation[data-word-id]"));
    const words = new Map(state.words.map((word) => [word.id, word]));
    let index = 0;
    let failed = false;
    async function worker() {
      while (index < targets.length && !failed) {
        const target = targets[index];
        index += 1;
        const word = words.get(target.dataset.wordId);
        if (!word) continue;
        try {
          target.textContent = await SA.translateMeaning(word);
        } catch (error) {
          target.textContent = "—";
          if (!failed) SA.toast(error.message, "error");
          failed = true;
        }
      }
    }
    await Promise.all([worker(), worker(), worker()]);
  }

  state.posFilter = SATagFilter($("home-pos-filter"), render);

  $("filter-group").addEventListener("click", (event) => {
    const button = event.target.closest("[data-filter]");
    if (!button) return;
    state.filter = button.dataset.filter;
    for (const item of $("filter-group").querySelectorAll(".seg-btn")) {
      item.classList.toggle("active", item === button);
    }
    render();
  });

  $("check-flagged").addEventListener("click", checkFlaggedWords);
  $("word-ai-apply").addEventListener("click", applyAiSuggestions);
  $("word-ai-close").addEventListener("click", () => $("word-ai-dialog").close());
  $("word-ai-close-x").addEventListener("click", () => $("word-ai-dialog").close());

  $("add-word").addEventListener("click", () => openForm(null));
  $("empty-add").addEventListener("click", () => openForm(null));
  $("word-cancel").addEventListener("click", closeForm);
  $("word-cancel-x").addEventListener("click", closeForm);
  $("word-form").addEventListener("submit", submitForm);
  $("w-check").addEventListener("click", () => setCheckSwitch(!checkOn));

  document.addEventListener("keydown", (event) => {
    if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
    const tag = (event.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || event.target.isContentEditable) return;
    if ($("word-dialog").open) return;
    event.preventDefault();
    $("search").focus();
  });

  SA.ready.then(load);
})();
