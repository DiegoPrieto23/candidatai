// Va en <head>, antes de pintar: marca que hay JS y aplica el tema elegido antes (si lo hay), para
// que la página no parpadee. Sin elección guardada, manda prefers-color-scheme (lo resuelve el CSS).
(function () {
  var root = document.documentElement;
  root.classList.add("js");
  try {
    var theme = localStorage.getItem("candidatai-theme");
    if (theme === "light" || theme === "dark") root.setAttribute("data-theme", theme);
  } catch (e) {
    /* Sin almacenamiento (ventana privada, datos bloqueados): se sigue al sistema. */
  }
})();
