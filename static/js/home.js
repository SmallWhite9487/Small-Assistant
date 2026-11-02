(function () {
  "use strict";

  const state = { words: [], query: "", filter: "all", posFilter: null, showTranslations: false };
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
    $("stat-flagged").textContent = state.words.filter((item) => item.check_ai === "True").length;
  }

  function visibleWords() {
    const query = state.query.trim().toLowerCase();
    return state.words.filter((word) => {
      if (state.filter === "flagged" && word.check_ai !== "True") return false;
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

  function render() {
    const rows = $("word-rows");
    rows.replaceChildren();
    const words = visibleWords();

    for (const word of words) {
      const tr = document.createElement("tr");
      tr.dataset.id = word.id;

      const wordCell = document.createElement("td");
      wordCell.className = "w-word";
      wordCell.textContent = word.word;
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
