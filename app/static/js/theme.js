(function () {
  var STORAGE_KEY = "app-theme";
  var DEFAULT_PREFERENCE = "auto";
  var mq = window.matchMedia("(prefers-color-scheme: dark)");

  function getSystemTheme() {
    return mq.matches ? "dark" : "light";
  }

  function getPreference() {
    var t = localStorage.getItem(STORAGE_KEY);
    if (t === "light" || t === "dark" || t === "auto") return t;
    return DEFAULT_PREFERENCE;
  }

  function resolveTheme(preference) {
    if (preference === "auto") return getSystemTheme();
    return preference === "light" ? "light" : "dark";
  }

  function applyResolved(resolved, preference) {
    var root = document.documentElement;
    root.setAttribute("data-theme", resolved);
    root.setAttribute("data-bs-theme", resolved);
    root.setAttribute("data-theme-preference", preference);

    var meta = document.querySelector('meta[name="color-scheme"]');
    if (meta) meta.setAttribute("content", resolved);

    var nav = document.getElementById("app-nav");
    if (nav) {
      nav.classList.toggle("navbar-dark", resolved === "dark");
      nav.classList.toggle("navbar-light", resolved === "light");
    }

    var themeSwitch = document.querySelector("[data-theme-switch]");
    if (themeSwitch) themeSwitch.setAttribute("data-active", preference);

    document.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      var pref = btn.getAttribute("data-theme-set");
      var active = pref === preference;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function applyFromStorage() {
    var preference = getPreference();
    applyResolved(resolveTheme(preference), preference);
  }

  function setPreference(preference) {
    localStorage.setItem(STORAGE_KEY, preference);
    applyFromStorage();
  }

  window.AppTheme = {
    getPreference: getPreference,
    getResolved: function () {
      return resolveTheme(getPreference());
    },
    set: setPreference,
    apply: applyFromStorage,
  };

  mq.addEventListener("change", function () {
    if (getPreference() === "auto") applyFromStorage();
  });

  document.addEventListener("DOMContentLoaded", function () {
    applyFromStorage();

    document.querySelectorAll("[data-theme-set]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setPreference(btn.getAttribute("data-theme-set"));
      });
    });
  });
})();
