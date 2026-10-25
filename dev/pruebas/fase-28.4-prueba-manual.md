# Fase 28.4 · Prueba manual: portada, guía «Empieza aquí» y GitHub

Objetivo: comprobar que un visitante entiende qué es CandidatAI y por qué elegirlo en la primera
pantalla, que puede instalarlo sin leer nada interno, que sabe qué necesita (el agente incluido)
antes de empezar, y que el repo tiene lo que GitHub y la comunidad esperan.

Los comandos `gh` y los textos que hay que pegar están en
[`fase-28.4-github.md`](fase-28.4-github.md). Este documento es la lista de lo que te toca
comprobar, en orden y con casillas. Ningún paso usa tus datos: todo va con la demo.

## Ya hecho por el agente (2026-10-25)

- [x] README en inglés y en español reescritos (215 líneas cada uno, mismas secciones).
- [x] `docs/START_HERE.md` y `docs/EMPEZAR.md`, con botones, páginas, rutas y comandos comprobados
  contra la UI, los instaladores y la CLI.
- [x] `CONTRIBUTING.md` en inglés, `CODE_OF_CONDUCT.md`, tres plantillas de incidencias,
  `config.yml` y plantilla de PR (YAML validado).
- [x] Tests de README y CHANGELOG, ruff, `sync_agents.py --check`, `check_links.py` (0 enlaces
  rotos) y `check_readme_coverage.py`, en verde.
- [x] Revisión del rol `reviewer`, sin bloqueantes y con lo importante aplicado.

## A. Antes del commit: leer (unos 20 minutos)

Abre los ficheros con la vista previa de Markdown de tu editor (en VS Code, `Ctrl+Shift+V`).

**README (`README.md` y `README.es.md`)**
- [ ] La frase de arriba dice lo que quieres prometer. Si cambias algo, cámbialo en los dos.
- [ ] La nota «Where it stands» / «En qué punto está» es exacta: Windows lo más probado, macOS y
  Linux nuevos, Claude Code probado del todo, Codex con una oferta, Antigravity a medias, OpenCode
  probado solo con un 20B local que no terminó y Qwen Code sin probar.
- [ ] La tabla «Why CandidatAI» / «Por qué CandidatAI» te parece justa con career-ops y AI Job
  Search, y «What they do better» / «Lo que ellos hacen mejor» no se queda corto.
- [ ] No echas de menos nada importante que antes estaba y ahora solo está en `docs/` (la tabla de
  skills, las fuentes, los agentes, los diagramas, las decisiones).

**Guía (`docs/EMPEZAR.md` y `docs/START_HERE.md`)**
- [ ] La tabla de agentes: los precios (unos 20 US$ al mes en Claude Pro y ChatGPT Plus) y lo que
  dice de cada agente cuadran con lo que tú sabes.
- [ ] La pregunta del correo te parece bien explicada: dice que en Gmail una contraseña de
  aplicación llega a todo el buzón y que el límite a una etiqueta lo pone la app.
- [ ] El paso 5 (crear el perfil abriendo tu agente en la carpeta de la app) es lo que harías tú.
  Ahora no hay botón en «Mi perfil» para eso: si crees que debería haberlo, apúntalo como mejora.

**Para quien contribuye**
- [ ] `CONTRIBUTING.md`: te parecen bien los tres caminos fáciles y la línea en español.
- [ ] `CODE_OF_CONDUCT.md`: aceptas que los avisos de conducta lleguen por el formulario privado de
  seguridad (empezando el título por «Conduct:»).

Si cambias algo, pídeme que vuelva a pasar los comprobadores antes del commit.

## B. Comprobar la instalación desde la guía, tú mismo (unos 15 minutos)

En un Windows 11 que **no** tenga CandidatAI (la máquina virtual de la 28.1 vale: restaura la
instantánea limpia), siguiendo **solo** `docs/EMPEZAR.md` en el navegador, sin mirar nada más:

- [ ] Las dos líneas de PowerShell instalan sin errores y aparece el acceso directo «CandidatAI».
- [ ] No sale SmartScreen ni ningún aviso de ejecución de scripts. Si sale alguno, haz una captura y
  dime cuál: la guía dice que no debería salir.
- [ ] Opcional: descarga `install.ps1` con Edge, «Desbloquear» en Propiedades y ejecútalo con la
  segunda línea cambiando la ruta. Funciona como dice la guía.
- [ ] La comprobación de la suma a mano (los dos comandos de PowerShell sobre el zip y el `.sha256`
  de la release) da el mismo código en las dos líneas.
- [ ] El acceso directo abre la ventana y luego el navegador en `http://127.0.0.1:8000`.
- [ ] En «Agente», los agentes que no tienes salen como «No instalado» con su comando para copiar.
- [ ] Los tres comandos de la demo (sección 4) funcionan tal cual, y se ve el aviso «Modo demo».
  Repítelos una segunda vez: la segunda línea falla porque la demo ya existe, como avisa la guía.
- [ ] Con la demo abierta, «Procesar ofertas», «Evaluar encaje», «Generar CV» y «Renderizar» están
  donde dice la guía.

## C. Después del push de la rama (antes de fusionar)

Al hacer push de `fase/28-lanzamiento-repo`, GitHub ya enseña el README de la rama en
`https://github.com/DiegoPrieto23/candidatai/tree/fase/28-lanzamiento-repo`. Míralo ahí:

- [ ] En un portátil, la frase y el principio del recorrido animado se ven sin hacer scroll; los tres
  botones, justo debajo.
- [ ] El recorrido (unos 50 s) se ve nítido y se entiende sin sonido: aprobar y descartar, el CV,
  la candidatura parada antes de enviar, Procesos y Embudo. Ningún fotograma en blanco ni cargando.
- [ ] El banner tiene los ocho pasos en dos filas y ya no tiene el recuadro de `cai status`.
- [ ] Ni los README ni `docs/` dicen «triaje» o «triage» como palabra (el código y `dev/` sí, en
  nombres como `pending_triage`).
- [ ] Cada botón lleva a su sección («Windows», «macOS and Linux», «Docker»), en los dos README.
- [ ] Los tres distintivos (versión, CI y licencia) enseñan datos, no «invalid» ni «not found».
- [ ] La nota de madurez sale como un recuadro azul («Note»).
- [ ] Las capturas cambian a modo oscuro con el tema oscuro de GitHub.
- [ ] La CI de la rama pasa (el paso de enlaces, en los tres sistemas).

## D. Después de fusionar en `main`: ajustes de GitHub

Todo en [`fase-28.4-github.md`](fase-28.4-github.md), con sus comandos:

- [ ] §1 Descripción, sitio web y temas. `gh repo view … --json description,homepageUrl,repositoryTopics`
  enseña los nuevos.
- [ ] §2 Imagen social subida (Settings → General → Social preview).
- [ ] §3 Notas de la release `v0.1.0` leídas como alguien de fuera; opcional, la línea «New here?
  Start here».
- [ ] §4 Etiquetas: `docs`, `agent-compat`, `connector` e `i18n` creadas o renombradas.
- [ ] §5 Discussions activadas, con las categorías «Show your search» y «Compatibility».
- [ ] §5 Settings → Security: «Private vulnerability reporting» sigue activado (lo usan
  `SECURITY.md`, el código de conducta y `config.yml`).
- [ ] §6 Las 10 incidencias creadas con sus etiquetas.
- [ ] §7 GitHub Pages: decide sí o no (la recomendación es no por ahora) y apúntalo aquí.

## E. Cómo se ve desde fuera

Con una ventana privada (sin sesión) y en el móvil:

- [ ] La portada del repo en el móvil: los botones no se salen de la pantalla y la tabla «Why» se
  puede desplazar.
- [ ] «New issue» ofrece las tres plantillas («Bug report», «Idea or improvement», «Works with my
  agent») y los tres enlaces, y no deja abrir una en blanco.
- [ ] Al rellenar «Bug report», se pone sola la etiqueta `bug`; en «Works with my agent», la
  etiqueta `agent-compat` y el título `[compat] …`.
- [ ] Un PR de prueba desde una rama cualquiera trae la lista de comprobación (ciérralo sin
  fusionar).
- [ ] El enlace «Questions and help» de «New issue» abre Discussions (antes del §5 da 404).
- [ ] Al pegar el enlace del repo en una publicación de LinkedIn (sin publicarla), en X y en Slack
  salen la imagen social y la descripción nueva. Si LinkedIn enseña la antigua, fuérzala con su
  [Post Inspector](https://www.linkedin.com/post-inspector/).

## F. La prueba con un lector no técnico (cierra la subfase)

Es el criterio del encargo: hasta que alguien no técnico lo consiga sin ayuda, la 28.4 no se
cierra. El protocolo y la tabla para apuntarlo están en
[`fase-28.4-github.md` §8](fase-28.4-github.md#8-la-prueba-con-un-lector-cierra-la-subfase). En
corto:

- [ ] Alguien no técnico, en un Windows que no sea el tuyo (o en la máquina virtual limpia), con
  solo el README y `EMPEZAR.md` (o `START_HERE.md`), y tú callado.
- [ ] Cronometra hasta ver la demo y hasta que su agente crea un perfil con el CV ficticio
  (`backend/tests/fixtures/cv-ficticio.pdf`).
- [ ] Apunta cada atasco de más de un minuto: en qué paso y qué esperaba encontrar.
- [ ] Al final, tres preguntas: qué es la app en una frase, qué necesitaba antes de empezar y si se
  fiaría de conectar su correo.
- [ ] Me pasas los atascos, corrijo la guía y se repite hasta que salga sin ayuda.

## Al terminar

Marca en [`PENDIENTES.md`](PENDIENTES.md) los dos puntos de la 28.4 y dime el resultado de F:
con eso marco la 28.4 como ✅ en el ROADMAP.
