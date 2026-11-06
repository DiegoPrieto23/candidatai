// Interacción de la web: tema, pestañas, botones de copiar, la cabecera al bajar y la aparición
// de las secciones. Sin JS la página se lee entera: los paneles se ven uno detrás de otro.
(function () {
  var root = document.documentElement;
  var KEY = "candidatai-theme";
  var scheme = window.matchMedia("(prefers-color-scheme: dark)");

  function currentTheme() {
    return root.getAttribute("data-theme") || (scheme.matches ? "dark" : "light");
  }

  function syncToggle(button) {
    var dark = currentTheme() === "dark";
    var label = dark ? button.dataset.labelLight : button.dataset.labelDark;
    button.setAttribute("aria-pressed", dark ? "true" : "false");
    button.setAttribute("aria-label", label);
    button.dataset.tip = label;
  }

  var toggles = document.querySelectorAll(".theme-toggle");
  toggles.forEach(function (button) {
    syncToggle(button);
    button.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem(KEY, next);
      } catch (e) {
        /* Se aplica igual; solo no se recuerda. */
      }
      toggles.forEach(syncToggle);
    });
  });
  // Si cambia el tema del sistema y no se ha elegido uno, el botón se pone al día.
  if (scheme.addEventListener) {
    scheme.addEventListener("change", function () {
      if (!root.getAttribute("data-theme")) toggles.forEach(syncToggle);
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
    var label = button.querySelector("span");
    var original = label.textContent;
    button.addEventListener("click", function () {
      var text = button.parentElement.querySelector("pre").textContent.trim();
      function done(message) {
        label.textContent = message;
        setTimeout(function () {
          label.textContent = original;
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

  if (!("IntersectionObserver" in window)) {
    document.querySelectorAll(".reveal").forEach(function (el) {
      el.classList.add("is-in");
    });
    return;
  }

  // La cabecera gana su borde en cuanto la página deja de estar arriba del todo.
  var nav = document.querySelector(".nav");
  if (nav) {
    var sentinel = document.createElement("div");
    sentinel.setAttribute("aria-hidden", "true");
    sentinel.className = "sentinel";
    document.body.insertBefore(sentinel, document.body.firstChild);
    new IntersectionObserver(function (entries) {
      nav.classList.toggle("is-scrolled", !entries[0].isIntersecting);
    }).observe(sentinel);
  }

  // Cómo funciona: el paso que cruza el centro de la pantalla se activa y la ventana enseña su imagen.
  var steps = document.querySelectorAll("[data-step]");
  var shots = document.querySelectorAll("[data-shot]");
  function activate(index) {
    steps.forEach(function (step) {
      step.classList.toggle("is-active", step.dataset.step === index);
    });
    shots.forEach(function (shot) {
      shot.classList.toggle("is-active", shot.dataset.shot === index);
    });
  }
  if (steps.length) {
    activate(steps[0].dataset.step);
    var center = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) activate(entry.target.dataset.step);
        });
      },
      { rootMargin: "-48% 0px -48% 0px" }
    );
    steps.forEach(function (step) {
      center.observe(step);
    });
  }

  // Cada bloque aparece una vez, al entrar en pantalla.
  var reveal = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          reveal.unobserve(entry.target);
        }
      });
    },
    { rootMargin: "0px 0px -8% 0px" }
  );
  document.querySelectorAll(".reveal").forEach(function (el) {
    reveal.observe(el);
  });
})();
