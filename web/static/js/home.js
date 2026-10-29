(function () {
  "use strict";

  const state = { words: [], query: "", filter: "all" };
  let editing = null;
  let checkOn = true;

  const $ = (id) => document.getElementById(id);

  async function load() {
    try {
      const data = await SA.api("/api/words");
      state.words = data.words;
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
      if (!query) return true;
      return [word.word, word.reading, word.meaning, word.notes]
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
      readingCell.dataset.label = "Reading";
      readingCell.textContent = word.reading || "—";
      tr.append(readingCell);

      const meaningCell = document.createElement("td");
      meaningCell.className = "w-meaning";
      meaningCell.textContent = word.meaning;
      meaningCell.title = word.meaning;
      tr.append(meaningCell);

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
      toggle.setAttribute("aria-label", "Check " + word.word + " with AI");
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
      conjugate.href = "/conjugation?word=" + encodeURIComponent(word.word);
      conjugate.title = "Conjugate " + word.word;
      conjugate.setAttribute("aria-label", "Conjugate " + word.word);
      conjugate.innerHTML = icon("swap");
      actions.append(
        conjugate,
        makeButton("pencil", "Edit " + word.word, () => openForm(word)),
        makeButton("trash", "Delete " + word.word, () => removeWord(word), "danger"),
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
      ? state.words.length + (state.words.length === 1 ? " word" : " words")
      : "Showing " + words.length + " of " + state.words.length + " words";

    const empty = $("word-empty");
    const scroll = $("table-scroll");
    if (words.length === 0) {
      empty.hidden = false;
      scroll.hidden = true;
      const total = state.words.length;
      $("empty-title").textContent = total === 0 ? "No words yet" : "No matching words";
      $("empty-copy").textContent = total === 0
        ? "Add your first Japanese word and it will appear here."
        : "Try a different search or switch the filter.";
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
      title: "Delete this word?",
      message: word.word + " will be removed from your vocabulary list.",
      confirmText: "Delete word",
    });
    if (!ok) return;
    try {
      await SA.api("/api/words/" + encodeURIComponent(word.id), { method: "DELETE" });
      state.words = state.words.filter((item) => item.id !== word.id);
      render();
      SA.toast("Deleted " + word.word);
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
    $("word-dialog-title").textContent = editing ? "Edit word" : "Add a word";
    $("word-dialog-sub").textContent = editing
      ? "Update the spelling, reading or meaning. The added date stays the same."
      : "Save the spelling, how to read it, and what it means.";
    $("w-word").value = editing ? editing.word : "";
    $("w-reading").value = editing ? editing.reading : "";
    $("w-meaning").value = editing ? editing.meaning : "";
    $("w-notes").value = editing ? editing.notes : "";
    setCheckSwitch(editing ? editing.check_ai === "True" : true);
    $("word-save").textContent = editing ? "Save changes" : "Save word";
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
      notes: $("w-notes").value.trim(),
      check_ai: checkOn,
    };
    if (!payload.word || !payload.meaning) {
      SA.toast("Enter a Japanese word and its meaning.", "error");
      (!payload.word ? $("w-word") : $("w-meaning")).focus();
      return;
    }
    const button = $("word-save");
    SA.setBusy(button, true, editing ? "Saving…" : "Adding…");
    try {
      if (editing) {
        await SA.api("/api/words/" + encodeURIComponent(editing.id), { method: "PUT", body: payload });
        SA.toast("Saved changes to " + payload.word);
      } else {
        await SA.api("/api/words", { method: "POST", body: payload });
        SA.toast("Added " + payload.word);
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

  load();
})();
