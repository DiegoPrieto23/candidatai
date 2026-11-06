// Interacción de la web: cambiar de tema, las pestañas y los botones de copiar.
// Sin JS la página se lee entera: los paneles se ven uno detrás de otro y estos botones no salen.
(function () {
  var root = document.documentElement;
  var KEY = "candidatai-theme";

  function currentTheme() {
    var chosen = root.getAttribute("data-theme");
    if (chosen) return chosen;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function syncToggle(button) {
    var dark = currentTheme() === "dark";
    button.setAttribute("aria-pressed", dark ? "true" : "false");
    button.setAttribute("aria-label", dark ? button.dataset.labelLight : button.dataset.labelDark);
    button.title = button.getAttribute("aria-label");
  }

  document.querySelectorAll(".theme-toggle").forEach(function (button) {
    syncToggle(button);
    button.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem(KEY, next);
      } catch (e) {
        /* Se aplica igual; solo no se recuerda. */
      }
      syncToggle(button);
    });
  });

  // Si cambia el tema del sistema y no se ha elegido uno, el botón se pone al día.
  var scheme = window.matchMedia("(prefers-color-scheme: dark)");
  if (scheme.addEventListener) {
    scheme.addEventListener("change", function () {
      if (root.getAttribute("data-theme")) return;
      document.querySelectorAll(".theme-toggle").forEach(syncToggle);
    });
  }

  // Pestañas accesibles: flechas, Inicio y Fin mueven el foco y la selección.
  document.querySelectorAll("[data-tabs]").forEach(function (group) {
    var tabs = Array.prototype.slice.call(group.querySelectorAll('[role="tab"]'));
    function select(tab, focus) {
      tabs.forEach(function (other) {
        var selected = other === tab;
        other.setAttribute("aria-selected", selected ? "true" : "false");
        other.tabIndex = selected ? 0 : -1;
        document.getElementById(other.getAttribute("aria-controls")).hidden = !selected;
      });
      if (focus) tab.focus();
    }
    tabs.forEach(function (tab, index) {
      tab.addEventListener("click", function () {
        select(tab, false);
      });
      tab.addEventListener("keydown", function (event) {
        var target = null;
        if (event.key === "ArrowRight") target = tabs[(index + 1) % tabs.length];
        if (event.key === "ArrowLeft") target = tabs[(index - 1 + tabs.length) % tabs.length];
        if (event.key === "Home") target = tabs[0];
        if (event.key === "End") target = tabs[tabs.length - 1];
        if (target) {
          event.preventDefault();
          select(target, true);
        }
      });
    });
    select(tabs[0], false);
  });

  // Copiar un bloque de código.
  document.querySelectorAll(".copy").forEach(function (button) {
    var label = button.textContent;
    button.addEventListener("click", function () {
      var text = button.parentElement.querySelector("pre").textContent.trim();
      function done(message) {
        button.textContent = message;
        setTimeout(function () {
          button.textContent = label;
        }, 1800);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(
          function () {
            done(button.dataset.copied);
          },
          function () {
            done(button.dataset.failed);
          }
        );
      } else {
        done(button.dataset.failed);
      }
    });
  });
})();
