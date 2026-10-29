/* Shared browser helpers: JSON fetch, toasts, dialogs, theme and navigation. */
(function () {
  "use strict";

  const SA = {};

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
      throw new Error("The server could not be reached. Is Flask still running?");
    }
    const type = response.headers.get("content-type") || "";
    let data = null;
    if (type.includes("application/json")) {
      data = await response.json().catch(() => null);
    }
    if (response.status === 401) {
      window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
      throw new Error("Please sign in first.");
    }
    if (!response.ok) {
      throw new Error((data && data.error) || "Request failed (" + response.status + ")");
    }
    if (data === null) throw new Error("The server returned an unexpected response.");
    return data;
  };

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
    if (!dialog) return Promise.resolve(window.confirm(options.message || "Are you sure?"));
    document.getElementById("confirm-title").textContent = options.title || "Are you sure?";
    document.getElementById("confirm-message").textContent = options.message || "";
    const ok = document.getElementById("confirm-ok");
    ok.textContent = options.confirmText || "Confirm";
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

  /* ---- theme ------------------------------------------------------------ */

  const themeButton = document.getElementById("theme-toggle");
  function currentTheme() {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  }
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#0d1512" : "#f3f6f1");
    if (themeButton) themeButton.setAttribute("aria-label", "Switch to " + (theme === "dark" ? "light" : "dark") + " theme");
  }
  if (themeButton) {
    themeButton.addEventListener("click", () => {
      const next = currentTheme() === "dark" ? "light" : "dark";
      applyTheme(next);
      try { localStorage.setItem("sa-theme", next); } catch (error) { /* ignore */ }
    });
    applyTheme(currentTheme());
  }

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

  window.SA = SA;
})();
