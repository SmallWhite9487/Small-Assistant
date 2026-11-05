(function () {
  "use strict";

  const state = { items: [], query: "", filter: "all", category: "", showTranslations: false };
  const FIELDS = ["pattern", "connection", "meaning", "example", "category"];
  const FIELD_LABELS = {
    pattern: "grammar.pattern",
    connection: "grammar.connection",
    meaning: "home.meaning",
    example: "grammar.example",
    category: "grammar.category",
  };
  let editing = null;
  let checkOn = true;
  let suggestions = [];

  const $ = (id) => document.getElementById(id);
  const icon = (name) => '<svg class="icon"><use href="#i-' + name + '"/></svg>';

  async function load() {
    try {
      const data = await SA.api("/api/grammar");
      state.items = data.items;
      renderCategories();
      render();
    } catch (error) {
      SA.toast(error.message, "error");
    }
  }

  function categories() {
    return Array.from(new Set(state.items.map((item) => item.category).filter(Boolean))).sort();
  }

  function renderCategories() {
    const select = $("category-filter");
    const list = categories();
    if (state.category && !list.includes(state.category)) state.category = "";
    select.replaceChildren(new Option(SA.t("grammar.all_categories"), ""));
    for (const name of list) select.append(new Option(name, name));
    select.value = state.category;
    $("g-category-list").replaceChildren(...list.map((name) => new Option(name)));
  }

  function visibleItems() {
    const query = state.query.trim().toLowerCase();
    return state.items.filter((item) => {
      if (state.filter === "flagged" && item.check_ai !== "True") return false;
      if (state.category && item.category !== state.category) return false;
      if (!query) return true;
      return [item.pattern, item.connection, item.meaning, item.example, item.category, item.notes]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
  }

  function refreshStats() {
    const today = SA.todayISO();
    $("stat-total").textContent = state.items.length;
    $("stat-today").textContent = state.items.filter((item) => item.added_on === today).length;
    $("stat-flagged").textContent = state.items.filter((item) => item.check_ai === "True").length;
  }

  function cell(className, text, label) {
    const td = document.createElement("td");
    td.className = className;
    if (label) td.dataset.label = SA.t(label);
    td.textContent = text || "—";
    td.title = text || "";
    return td;
  }

  function meaningCell(item) {
    const td = cell("w-meaning", item.meaning, "home.meaning");
    if (item.meaning && state.showTranslations && SA.language() !== "en" && SA.language() !== "dev") {
      const translated = document.createElement("span");
      translated.className = "meaning-translation";
      translated.dataset.itemId = item.id;
      translated.textContent = "…";
      const original = td.textContent;
      td.textContent = "";
      const text = document.createElement("span");
      text.textContent = original;
      td.append(text, translated);
    }
    return td;
  }

  async function translateVisibleMeanings() {
    const targets = Array.from(document.querySelectorAll(".meaning-translation[data-item-id]"));
    const items = new Map(state.items.map((item) => [item.id, item]));
    let index = 0;
    let failed = false;
    async function worker() {
      while (index < targets.length && !failed) {
        const target = targets[index];
        index += 1;
        const item = items.get(target.dataset.itemId);
        if (!item) continue;
        try {
          target.textContent = await SA.translateMeaning(item);
        } catch (error) {
          target.textContent = "—";
          if (!failed) SA.toast(error.message, "error");
          failed = true;
        }
      }
    }
    await Promise.all([worker(), worker(), worker()]);
  }

  function button(iconName, title, handler, extra) {
    const element = document.createElement("button");
    element.type = "button";
    element.className = "icon-btn" + (extra ? " " + extra : "");
    element.title = title;
    element.setAttribute("aria-label", title);
    element.innerHTML = icon(iconName);
    element.addEventListener("click", (event) => {
      event.stopPropagation();
      handler();
    });
    return element;
  }

  function render() {
    const rows = $("grammar-rows");
    rows.replaceChildren();
    const items = visibleItems();
    for (const item of items) {
      const tr = document.createElement("tr");
      tr.dataset.id = item.id;
      tr.append(
        cell("w-word", item.pattern),
        cell("w-reading", item.connection, "grammar.connection"),
        meaningCell(item),
        cell("w-meaning", item.example, "grammar.example"),
        cell("w-pos", item.category, "grammar.category"),
        cell("w-date", item.added_on),
      );

      const checkCell = document.createElement("td");
      checkCell.className = "center w-check";
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "switch" + (item.check_ai === "True" ? " on" : "");
      toggle.setAttribute("role", "switch");
      toggle.setAttribute("aria-checked", item.check_ai === "True" ? "true" : "false");
      toggle.setAttribute("aria-label", SA.t("grammar.check_item_ai", { item: item.pattern }));
      toggle.addEventListener("click", (event) => {
        event.stopPropagation();
        toggleCheck(item, toggle);
      });
      checkCell.append(toggle);
      tr.append(checkCell);

      const actionCell = document.createElement("td");
      actionCell.className = "w-act";
      const actions = document.createElement("div");
      actions.className = "w-actions";
      actions.append(
        button("pencil", SA.t("grammar.edit_item", { item: item.pattern }), () => openForm(item)),
        button("trash", SA.t("grammar.delete_item", { item: item.pattern }), () => remove(item), "danger"),
      );
      actionCell.append(actions);
      tr.append(actionCell);
      tr.addEventListener("dblclick", (event) => {
        if (!event.target.closest("button, a")) openForm(item);
      });
      rows.append(tr);
    }

    refreshStats();
    $("table-count").textContent = items.length === state.items.length
      ? SA.t("grammar.count", { count: state.items.length })
      : SA.t("home.showing_count", { shown: items.length, total: state.items.length });
    const total = state.items.length;
    $("grammar-empty").hidden = items.length !== 0;
    $("table-scroll").hidden = items.length === 0;
    if (items.length === 0) {
      $("empty-title").textContent = total === 0 ? SA.t("grammar.none") : SA.t("home.no_matching");
      $("empty-copy").textContent = total === 0 ? SA.t("grammar.none_help") : SA.t("home.no_matching_help");
      $("empty-add").hidden = total !== 0;
    }
  }

  async function toggleCheck(item, element) {
    const next = item.check_ai !== "True";
    element.classList.toggle("on", next);
    element.setAttribute("aria-checked", String(next));
    try {
      const data = await SA.api("/api/grammar/" + encodeURIComponent(item.id) + "/check", {
        method: "PATCH",
        body: { check_ai: next },
      });
      Object.assign(item, data.item);
      refreshStats();
    } catch (error) {
      element.classList.toggle("on", !next);
      element.setAttribute("aria-checked", String(!next));
      SA.toast(error.message, "error");
    }
  }

  async function remove(item) {
    const ok = await SA.confirm({
      title: SA.t("grammar.delete_title"),
      message: SA.t("grammar.delete_message", { item: item.pattern }),
      confirmText: SA.t("home.delete_confirm"),
    });
    if (!ok) return;
    try {
      await SA.api("/api/grammar/" + encodeURIComponent(item.id), { method: "DELETE" });
      state.items = state.items.filter((entry) => entry.id !== item.id);
      renderCategories();
      render();
      SA.toast(SA.t("grammar.deleted", { item: item.pattern }));
    } catch (error) {
      SA.toast(error.message, "error");
    }
  }

  /* ---- add / edit ------------------------------------------------------- */

  function setCheckSwitch(value) {
    checkOn = value;
    $("g-check").classList.toggle("on", value);
    $("g-check").setAttribute("aria-checked", String(value));
  }

  function openForm(item) {
    editing = item || null;
    $("grammar-dialog-title").textContent = editing ? SA.t("grammar.edit") : SA.t("grammar.add");
    for (const field of FIELDS) $("g-" + field).value = editing ? editing[field] : "";
    $("g-notes").value = editing ? editing.notes : "";
    setCheckSwitch(editing ? editing.check_ai === "True" : true);
    $("grammar-dialog").showModal();
    window.setTimeout(() => $("g-pattern").focus(), 30);
  }

  function closeForm() {
    $("grammar-dialog").close();
  }

  async function submitForm(event) {
    event.preventDefault();
    const payload = { notes: $("g-notes").value.trim(), check_ai: checkOn };
    for (const field of FIELDS) payload[field] = $("g-" + field).value.trim();
    if (!payload.pattern) {
      SA.toast(SA.t("grammar.required"), "error");
      $("g-pattern").focus();
      return;
    }
    const submit = $("grammar-save");
    SA.setBusy(submit, true, SA.t("grammar.saving"));
    try {
      if (editing) {
        await SA.api("/api/grammar/" + encodeURIComponent(editing.id), { method: "PUT", body: payload });
      } else {
        await SA.api("/api/grammar", { method: "POST", body: payload });
      }
      SA.toast(SA.t("grammar.saved_item", { item: payload.pattern }));
      closeForm();
      await load();
    } catch (error) {
      SA.toast(error.message, "error");
    } finally {
      SA.setBusy(submit, false);
    }
  }

  /* ---- AI check --------------------------------------------------------- */

  async function runAiCheck() {
    const queue = state.items.filter((item) => item.check_ai === "True");
    if (queue.length === 0) {
      SA.toast(SA.t("grammar.nothing_flagged"));
      return;
    }
    const trigger = $("ai-check");
    SA.setBusy(trigger, true, SA.t("grammar.checking"));
    try {
      suggestions = [];
      for (let start = 0; start < queue.length; start += 20) {
        const data = await SA.api("/api/ai/grammar-check", {
          method: "POST",
          body: {
            provider: "online",
            language: SA.language(),
            ids: queue.slice(start, start + 20).map((item) => item.id),
          },
        });
        suggestions.push(...data.suggestions);
      }
      showSuggestions();
    } catch (error) {
      SA.toast(error.message, "error");
    } finally {
      SA.setBusy(trigger, false);
    }
  }

  function showSuggestions() {
    const container = $("ai-results");
    container.replaceChildren();
    const byId = new Map(state.items.map((item) => [item.id, item]));
    for (const suggestion of suggestions) {
      const original = byId.get(suggestion.id);
      if (!original) continue;
      const box = document.createElement("label");
      box.className = "ai-suggestion";
      box.style.cssText = "display:block;padding:12px 0;border-bottom:1px solid var(--line, #ddd)";
      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = true;
      check.dataset.id = suggestion.id;
      const title = document.createElement("strong");
      title.textContent = " " + original.pattern;
      const reason = document.createElement("div");
      reason.textContent = suggestion.reason;
      box.append(check, title, reason);
      for (const field of FIELDS) {
        if (suggestion[field] === original[field]) continue;
        const line = document.createElement("div");
        line.style.fontSize = "13px";
        line.textContent = SA.t(FIELD_LABELS[field]) + ": " + (original[field] || "—") + " → " + (suggestion[field] || "—");
        box.append(line);
      }
      container.append(box);
    }
    $("ai-dialog").showModal();
  }

  async function applySuggestions() {
    const selected = new Set(
      Array.from($("ai-results").querySelectorAll("input:checked")).map((input) => input.dataset.id),
    );
    const byId = new Map(state.items.map((item) => [item.id, item]));
    const changes = suggestions
      .filter((suggestion) => selected.has(suggestion.id))
      .map((suggestion) => ({
        id: suggestion.id,
        notes: byId.get(suggestion.id).notes,
        ...Object.fromEntries(FIELDS.map((field) => [field, suggestion[field]])),
      }));
    if (changes.length === 0) {
      $("ai-dialog").close();
      return;
    }
    const submit = $("ai-apply");
    SA.setBusy(submit, true, SA.t("grammar.saving"));
    try {
      await SA.api("/api/grammar/apply", { method: "POST", body: { changes } });
      $("ai-dialog").close();
      SA.toast(SA.t("grammar.applied", { count: changes.length }));
      await load();
    } catch (error) {
      SA.toast(error.message, "error");
    } finally {
      SA.setBusy(submit, false);
    }
  }

  /* ---- wiring ----------------------------------------------------------- */

  $("search").addEventListener("input", (event) => {
    state.query = event.target.value;
    render();
  });
  $("translate-meanings").addEventListener("click", () => {
    if (SA.language() === "en" || SA.language() === "dev") {
      SA.toast(SA.t("home.choose_translation_language"));
      return;
    }
    state.showTranslations = !state.showTranslations;
    $("translate-meanings").classList.toggle("active", state.showTranslations);
    render();
    if (state.showTranslations) translateVisibleMeanings();
  });
  $("category-filter").addEventListener("change", (event) => {
    state.category = event.target.value;
    render();
  });
  $("filter-group").addEventListener("click", (event) => {
    const target = event.target.closest("[data-filter]");
    if (!target) return;
    state.filter = target.dataset.filter;
    for (const item of $("filter-group").querySelectorAll(".seg-btn")) {
      item.classList.toggle("active", item === target);
    }
    render();
  });
  $("add-grammar").addEventListener("click", () => openForm(null));
  $("empty-add").addEventListener("click", () => openForm(null));
  $("grammar-cancel").addEventListener("click", closeForm);
  $("grammar-cancel-x").addEventListener("click", closeForm);
  $("grammar-form").addEventListener("submit", submitForm);
  $("g-check").addEventListener("click", () => setCheckSwitch(!checkOn));
  $("ai-check").addEventListener("click", runAiCheck);
  $("ai-apply").addEventListener("click", applySuggestions);
  $("ai-cancel").addEventListener("click", () => $("ai-dialog").close());
  $("ai-close-x").addEventListener("click", () => $("ai-dialog").close());

  document.addEventListener("keydown", (event) => {
    if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
    const tag = (event.target.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea" || tag === "select" || event.target.isContentEditable) return;
    if (document.querySelector("dialog[open]")) return;
    event.preventDefault();
    $("search").focus();
  });

  SA.ready.then(load);
})();
