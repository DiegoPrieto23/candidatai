# Fase 28.4 · Lo que se hace en GitHub y la prueba con un lector

Lo que esta subfase deja escrito para que lo hagas tú (decisión del usuario: los ajustes públicos
de GitHub no los hace el agente). Los comandos `gh` sirven en PowerShell y en Git Bash; lo que no
tiene API va por la web. Hazlo **después del push a `main`**, para que los enlaces de las
plantillas (`START_HERE.md`, `CONTRIBUTING.md#test-an-agent`) ya existan.

## 1. Descripción, sitio web y temas

Descripción (una frase en inglés, la que sale en la búsqueda de GitHub y al pegar el enlace):

```
gh repo edit DiegoPrieto23/candidatai --description "Your whole job search in one local app: your AI agent (Claude Code, Codex…) reads and writes, the app keeps the rules, and nothing is sent without you."
```

Sitio web: mientras no haya página propia, la guía para empezar (es lo que más ayuda a quien llega
desde una búsqueda):

```
gh repo edit DiegoPrieto23/candidatai --homepage "https://github.com/DiegoPrieto23/candidatai/blob/main/docs/START_HERE.md"
```

Temas: GitHub admite 20. Hoy hay 14; quedan 19, que suman `cv-generator`, `agent-skills`,
`self-hosted`, `opencode`, `job-tracker` y `resume-builder`, y quitan `cv`, que casi nadie busca
(los buscados de verdad son `resume` y `job-search`), y dejan un hueco libre. GitHub los enseña por orden alfabético, así
que el orden no importa: importa cuáles están.

```
gh repo edit DiegoPrieto23/candidatai --remove-topic cv
gh repo edit DiegoPrieto23/candidatai --add-topic job-search,resume,cv-generator,resume-builder,cover-letter,job-hunting,job-tracker,career,claude-code,codex,opencode,ai-agents,agent-skills,mcp,local-first,self-hosted,fastapi,react,sqlite
```

Comprueba: `gh repo view DiegoPrieto23/candidatai --json description,homepageUrl,repositoryTopics`.

## 2. Imagen social (solo por la web)

Settings → General → **Social preview** → «Edit» → «Upload an image» → `docs/img/social-en.png`
(1280×640, de la 28.3b). Sustituye al punto de la 28.4 de `PENDIENTES.md`.

## 3. La release `v0.1.0`

GitHub no deja «fijar» una release: la última sale sola en la columna derecha como «Latest», y el
distintivo de versión del README la lee de ahí. Lo que sí conviene:

- Abre la [release](https://github.com/DiegoPrieto23/candidatai/releases/tag/v0.1.0) y lee las
  notas como alguien que no conoce la app: salen de la sección `0.1.0` del `CHANGELOG`, ya escrita
  para quien la usa. Si quieres, añade arriba una línea con el enlace a
  [`START_HERE.md`](../../docs/START_HERE.md) («New here? Start here»), con «Edit».
- Vídeos: no hay (decisión de la 28.3b).
- Lo de «Sin publicar» (medios nuevos, demo con alertas, portada y guía nuevas) irá en la `0.1.1` o
  la `0.2.0` cuando la publiques; no hace falta para el lanzamiento, porque los README se leen desde
  `main`.

## 4. Etiquetas

Las cuatro del encargo. `documentation` ya existe: se renombra a `docs` para que todas sean cortas
(las incidencias que la tengan la conservan).

```
gh label edit documentation --name docs --description "Guides, README and docs" -R DiegoPrieto23/candidatai
gh label create agent-compat --color 6D28D9 --description "How it works with an agent or a model" -R DiegoPrieto23/candidatai
gh label create connector --color 0F6E69 --description "Job sources: ATS APIs, portals, email alerts" -R DiegoPrieto23/candidatai
gh label create i18n --color FBCA04 --description "UI languages and translations" -R DiegoPrieto23/candidatai
```

`good first issue` y `help wanted` ya existen. Las de Dependabot (`dependencies`, `python:uv`,
`github_actions`, `javascript`) se quedan.

## 5. Discussions

1. `gh repo edit DiegoPrieto23/candidatai --enable-discussions`
2. En la pestaña **Discussions** → lápiz de «Categories» (las categorías no tienen API). Deja
   **Q&A** (formato pregunta y respuesta), **Ideas** y **Announcements**; borra «General» y
   «Polls» si no las quieres, y crea:
   - **Show your search** (formato «Open-ended discussion»), emoji 📈: «Share your search in
     numbers (`cai stats story`), what worked and what didn't. Aggregated numbers only: no
     companies or personal data.»
   - **Compatibility** (formato «Open-ended discussion»), emoji 🤖: «Questions and experiences with
     an agent or a model. Measured results go in an issue with the "Works with my agent" template.»
3. Abre un primer anuncio en Announcements (lo prepara la 28.5) para que la pestaña no salga vacía.

La plantilla `config.yml` ya enlaza «Questions and help» a Discussions: hasta que las actives, ese
enlace da 404. El de «Security problem» y el del código de conducta van al aviso privado de
vulnerabilidades, activado en la 28.1 (compruébalo en Settings → Security → «Private vulnerability
reporting»).

## 6. Primeras incidencias

Diez, realistas y pequeñas. Copia cada título, etiquetas y cuerpo en «New issue» (las plantillas
obligan a elegir una; usa «Idea or improvement» y sustituye el texto) o, con Git Bash, guarda el
cuerpo en un fichero y usa `gh issue create -R DiegoPrieto23/candidatai --title "…" --label "…"
--body-file cuerpo.md`.

### 1. Connector for Breezy HR job boards
Labels: `connector`, `good first issue`, `help wanted`

> Breezy HR publishes each company's open positions as public JSON
> (`https://{company}.breezy.hr/json`). A connector would bring those jobs in every day, like the
> eight ATS already supported. Steps in CONTRIBUTING → "Add an ATS connector";
> `backend/app/services/ingestion/recruitee.py` is a short one to copy. First, check that the
> endpoint is public and what each item contains (description or not), and save a fictional sample
> as the test fixture.

### 2. Find more public ATS APIs worth a connector
Labels: `connector`, `help wanted`

> Which applicant tracking systems used by the companies *you* follow have a public, documented job
> API with no login? Candidates to check: BambooHR, JazzHR, Join, Homerun, Pinpoint, Factorial.
> Comment with the endpoint and its documentation; each confirmed one becomes its own issue. No
> scraping: only endpoints meant to be read.

### 3. Dedicated parser for Indeed job-alert emails
Labels: `connector`, `help wanted`

> Today only LinkedIn alerts have their own parser (`backend/app/services/ingestion/email/parsers/linkedin.py`);
> the rest go through the generic one, which gets fewer fields right. A parser for Indeed alerts
> would extract title, company, location and link for each job. Test it with an alert email whose
> personal data you've replaced (`backend/tests/fixtures/email/` has examples).

### 4. Dedicated parser for InfoJobs or StepStone job-alert emails
Labels: `connector`, `help wanted`

> Same as the Indeed one, for InfoJobs (Spain) or StepStone (Germany and others). Pick one, say
> which in a comment so nobody duplicates it.

### 5. A third UI language
Labels: `i18n`, `good first issue`

> The UI is in Spanish and English, and adding a language is a new folder in
> `frontend/src/locales/` with the same keys (CONTRIBUTING → "Add a UI language"). French, German,
> Portuguese or Italian would be most useful. Say which one you're taking in a comment. The server
> messages and CVs stay in Spanish and English for now.

### 6. Review the English UI texts as a native speaker
Labels: `i18n`, `good first issue`

> The English UI (`frontend/src/locales/en/`) was translated from Spanish. A pass by a native
> speaker would catch unnatural phrasing: open a PR with the changes, keys untouched.

### 7. Measure OpenCode or Qwen Code with a cloud model
Labels: `agent-compat`, `help wanted`

> Both are configured, but no one has measured them with a model good enough (the only run, with a
> local 20B model on a laptop without a graphics card, didn't finish). If you use either with a
> cloud model (OpenRouter, DashScope, any OpenAI-compatible API), run
> `cai eval compat --agent opencode --model <model>` and open a "Works with my agent" report.

### 8. Try the installer on macOS and on Linux from the release
Labels: `help wanted`

> The installers are tested on a clean Windows 11 and in CI. On a real Mac or Linux machine, run
> `curl -fsSL https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.sh | bash`,
> open the shortcut, load the demo and tell us what happened: the system, how long it took and
> anything that wasn't clear in `docs/START_HERE.md`.

### 9. A new built-in CV template
Labels: `good first issue`, `help wanted`

> Three CV templates ship today (`ats-simple`, `clasica-foto`, `moderna-2col`). A fourth one, for
> example a clean one-column design for tech roles, built with the HTML engine like `moderna-2col`
> (`templates/moderna-2col/`, format in `docs/CV_TEMPLATES.md`). It must render the demo profile
> on one page and have no personal data; its preview is generated by
> `scripts/build_builtin_templates.py`.

### 10. Translate a technical doc to English
Labels: `docs`, `good first issue`

> Most technical docs are in Spanish. `docs/POLICIES.md` (the rules: truthfulness, privacy,
> applying) is the most useful one for English readers. Translate it as `docs/POLICIES.en.md` and
> link it from `docs/README.md`.

## 7. GitHub Pages (opcional)

Una página de una pantalla con la promesa, la animación y los tres botones de instalar, con el mismo
contenido que el README. **Recomendación: no por ahora.** Es una segunda copia de la portada que hay
que mantener en dos idiomas, y el README ya hace ese papel. Merece la pena si en la 28.5 la difusión
pide un enlace más corto o una vista previa mejor que la del repositorio.

## 8. La prueba con un lector (cierra la subfase)

Alguien **no técnico**, en un equipo con Windows 11 que no sea el tuyo (o en una máquina virtual
limpia), con solo `README.md` y `docs/START_HERE.md` abiertos en el navegador y sin tu ayuda:

1. Cronometra desde que abre el README hasta que ve la demo en su navegador, y hasta que su agente
   le crea un perfil a partir de un CV ficticio (usa el de `backend/tests/fixtures/cv-ficticio.pdf`).
2. Apunta cada vez que se para más de un minuto, pregunta algo o se equivoca: en qué paso y qué
   esperaba encontrar.
3. Pregúntale al final: qué es la app (en una frase), qué necesitaba antes de empezar, qué le cuesta
   y si se fiaría de conectar su correo.

Hasta que lo consiga sin ayuda, se corrige la guía y se repite. Apunta el resultado aquí, con fecha.

| Fecha | Quién (sin nombre) | Sistema | Hasta la demo | Hasta el perfil | Atascos |
|---|---|---|---|---|---|
| | | | | | |

## 9. Cómo se ve desde fuera

Con la sesión cerrada (una ventana privada) y en el móvil:

- [ ] La portada: la frase, la animación y los tres botones se ven sin hacer scroll en un portátil;
      en el móvil, los botones no se salen de la pantalla.
- [ ] Los botones llevan a su sección («Windows», «macOS and Linux», «Docker») en los dos README.
- [ ] Los tres distintivos (versión, CI, licencia) muestran datos, no «invalid» ni «not found».
- [ ] La nota «Where it stands» se lee como un aviso (recuadro azul).
- [ ] Al pegar el enlace del repo en LinkedIn (vista previa de una publicación), en X y en Slack sale
      la imagen social y la descripción nueva. LinkedIn guarda la vista previa en caché: fuérzala con
      su [Post Inspector](https://www.linkedin.com/post-inspector/).
- [ ] «New issue» ofrece las tres plantillas y los tres enlaces, y no deja abrir una en blanco.
- [ ] Un PR de prueba (desde una rama, sin fusionarlo) trae la lista de comprobación.
