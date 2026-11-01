/* Shared browser helpers: JSON fetch, toasts, dialogs, theme and navigation. */
(function () {
  "use strict";

  const SA = {};
  let translations = {};
  function initialLanguage() {
    try {
      const saved = localStorage.getItem("sa-language");
      if (saved && ["en", "zh-TW", "ko"].includes(saved)) return saved;
    } catch (error) { /* storage may be blocked */ }
    const browser = navigator.language || "en";
    return browser.toLowerCase().startsWith("ko") ? "ko" : browser.toLowerCase().startsWith("zh") ? "zh-TW" : "en";
  }
  let language = initialLanguage();
  SA.language = () => language;
  SA.t = (key, values) => {
    let text = translations[key] || key;
    if (values) {
      Object.keys(values).forEach((name) => {
        text = text.replaceAll("{" + name + "}", values[name]);
      });
    }
    return text;
  };
  SA.applyLanguage = function () {
    document.documentElement.lang = language;
    document.querySelectorAll("[data-i18n]").forEach((element) => { element.textContent = SA.t(element.dataset.i18n); });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
      element.setAttribute("placeholder", SA.t(element.dataset.i18nPlaceholder));
    });
    document.querySelectorAll("[data-i18n-title]").forEach((element) => {
      element.setAttribute("title", SA.t(element.dataset.i18nTitle));
    });
    document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
      element.setAttribute("aria-label", SA.t(element.dataset.i18nAriaLabel));
    });
    document.querySelectorAll("[data-i18n-content]").forEach((element) => {
      element.setAttribute("content", SA.t(element.dataset.i18nContent));
    });
    document.querySelectorAll("[data-i18n-data-placeholder]").forEach((element) => {
      element.setAttribute("data-placeholder", SA.t(element.dataset.i18nDataPlaceholder));
    });
  };
  SA.translateMeaning = async function (word) {
    if (language === "en") return "";
    const key = "sa.meaning." + language + "." + word.id;
    try {
      const cached = localStorage.getItem(key);
      if (cached) return cached;
    } catch (error) { /* continue without cache */ }
    const data = await SA.api("/api/translate/meaning", { method: "POST", body: { meaning: word.meaning, language } });
    try { localStorage.setItem(key, data.translation); } catch (error) { /* cache is optional */ }
    return data.translation;
  };

  SA.api = async function (path, options) {
    const config = Object.assign({ method: "GET" }, options || {});
    config.headers = Object.assign({ Accept: "application/json" }, config.headers || {});
    if (config.body !== undefined && typeof config.body !== "string") {
      config.body = JSON.stringify(config.body);
      config.headers["Content-Type"] = "application/json";
    }
    let response;
    try {
      response = await fetch(path, config);
    } catch (error) {
      throw new Error(SA.t("error.server_unreachable"));
    }
    const type = response.headers.get("content-type") || "";
    let data = null;
    if (type.includes("application/json")) {
      data = await response.json().catch(() => null);
    }
    if (response.status === 401) {
      window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
      throw new Error(SA.t("error.sign_in_first"));
    }
    if (!response.ok) {
      throw new Error((data && data.error) || SA.t("error.request_failed", { status: response.status }));
    }
    if (data === null) throw new Error(SA.t("error.unexpected_response"));
    return data;
  };
  SA.loadTranslations = async function () {
    const data = await SA.api("/api/locales/" + encodeURIComponent(language));
    translations = data.translations;
    SA.applyLanguage();
  };
  SA.ready = SA.loadTranslations().catch((error) => {
    console.warn("Unable to load interface translations.", error);
  });

  SA.toast = function (message, type) {
    const wrap = document.getElementById("toasts");
    if (!wrap) return;
    const toast = document.createElement("div");
    toast.className = "toast" + (type === "error" ? " error" : "");
    const dot = document.createElement("span");
    dot.className = "toast-dot";
    const text = document.createElement("span");
    text.textContent = message;
    toast.append(dot, text);
    wrap.append(toast);
    window.setTimeout(() => {
      toast.classList.add("leaving");
      window.setTimeout(() => toast.remove(), 200);
    }, type === "error" ? 5200 : 3200);
  };

  SA.confirm = function (options) {
    const dialog = document.getElementById("confirm-dialog");
    if (!dialog) return Promise.resolve(window.confirm(options.message || SA.t("dialog.confirm_title")));
    document.getElementById("confirm-title").textContent = options.title || SA.t("dialog.confirm_title");
    document.getElementById("confirm-message").textContent = options.message || "";
    const ok = document.getElementById("confirm-ok");
    ok.textContent = options.confirmText || SA.t("dialog.confirm");
    ok.className = "btn " + (options.danger === false ? "primary" : "danger");
    dialog.returnValue = "";
    dialog.showModal();
    return new Promise((resolve) => {
      dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true });
    });
  };

  SA.setBusy = function (button, busy, label) {
    if (!button) return;
    if (busy) {
      button.dataset.html = button.innerHTML;
      button.classList.add("is-busy");
      button.disabled = true;
      if (label) button.textContent = label;
    } else {
      button.classList.remove("is-busy");
      button.disabled = false;
      if (button.dataset.html) {
        button.innerHTML = button.dataset.html;
        delete button.dataset.html;
      }
    }
  };

  SA.debounce = function (fn, wait) {
    let timer = 0;
    return function () {
      const args = arguments;
      const context = this;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn.apply(context, args), wait);
    };
  };

  SA.todayISO = function () {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return now.getFullYear() + "-" + month + "-" + day;
  };

  SA.copy = async function (text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      const area = document.createElement("textarea");
      area.value = text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.append(area);
      area.select();
      let ok = false;
      try { ok = document.execCommand("copy"); } catch (ignored) { ok = false; }
      area.remove();
      return ok;
    }
  };

  SA.icon = function (name) {
    return '<svg class="icon"><use href="#i-' + name + '"/></svg>';
  };

  SA.conjugationUrl = function (word) {
    const partOfSpeech = (word.part_of_speech || "").trim().toLowerCase();
    const params = new URLSearchParams({ word: word.word });
    if (["adj", "adjective", "n", "noun"].includes(partOfSpeech)) {
      params.set("mode", "adjective");
    } else if (["v", "verb"].includes(partOfSpeech)) {
      params.set("mode", "verb");
    }
    return "/conjugation?" + params.toString();
  };

  /* ---- theme ------------------------------------------------------------ */

  const themeButton = document.getElementById("theme-toggle");
  function currentTheme() {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  }
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#0d1512" : "#f3f6f1");
    if (themeButton) themeButton.setAttribute("aria-label", SA.t("theme.switch_to", { theme: SA.t(theme === "dark" ? "theme.light" : "theme.dark") }));
  }
  if (themeButton) {
    themeButton.addEventListener("click", () => {
      const next = currentTheme() === "dark" ? "light" : "dark";
      applyTheme(next);
      try { localStorage.setItem("sa-theme", next); } catch (error) { /* ignore */ }
    });
    applyTheme(currentTheme());
  }

  const languageSelect = document.getElementById("language-select");
  if (languageSelect) {
    languageSelect.value = language;
    languageSelect.addEventListener("change", () => {
      language = languageSelect.value;
      try { localStorage.setItem("sa-language", language); } catch (error) { /* ignore */ }
      SA.loadTranslations().catch((error) => SA.toast(SA.t("error.language_load", { message: error.message }), "error"));
      window.location.reload();
    });
  }
  SA.applyLanguage();

  /* ---- mobile navigation ------------------------------------------------ */

  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebar-backdrop");
  const menuButton = document.getElementById("menu-toggle");

  function setSidebar(open) {
    if (!sidebar || !backdrop) return;
    sidebar.classList.toggle("open", open);
    backdrop.hidden = !open;
    if (menuButton) menuButton.setAttribute("aria-expanded", String(open));
  }

  if (menuButton) menuButton.addEventListener("click", () => setSidebar(!sidebar.classList.contains("open")));
  if (backdrop) backdrop.addEventListener("click", () => setSidebar(false));
  if (sidebar) {
    sidebar.addEventListener("click", (event) => {
      if (event.target.closest("a")) setSidebar(false);
    });
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setSidebar(false);
  });

  /* ---- learning profile ------------------------------------------------ */

  const profileDialog = document.getElementById("profile-dialog");
  if (profileDialog) {
    const nameInput = document.getElementById("profile-name");
    const createButton = document.getElementById("profile-create");
    const error = document.getElementById("profile-error");
    const existing = document.getElementById("profile-existing");
    const list = document.getElementById("profile-list");

    function showProfileError(message) {
      error.textContent = message;
      error.hidden = false;
    }

    async function chooseProfile(path, name) {
      error.hidden = true;
      SA.setBusy(createButton, true, SA.t("common.saving"));
      try {
        await SA.api(path, { method: "POST", body: { name } });
        window.location.reload();
      } catch (requestError) {
        showProfileError(requestError.message);
        SA.setBusy(createButton, false);
      }
    }

    async function loadProfileDialog() {
      try {
        const data = await SA.api("/api/profiles");
        if (data.profile) return;
        if (data.profiles.length) {
          existing.hidden = false;
          data.profiles.forEach((name) => {
            const button = document.createElement("button");
            button.className = "btn sm";
            button.type = "button";
            button.textContent = name;
            button.addEventListener("click", () => chooseProfile("/api/profiles/select", name));
            list.append(button);
          });
        }
        profileDialog.showModal();
        nameInput.focus();
      } catch (requestError) {
        SA.toast(SA.t("error.profile_load", { message: requestError.message }), "error");
      }
    }

    createButton.addEventListener("click", () => chooseProfile("/api/profiles", nameInput.value.trim()));
    nameInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        chooseProfile("/api/profiles", nameInput.value.trim());
      }
    });
    loadProfileDialog();
  }

  window.SA = SA;
})();
