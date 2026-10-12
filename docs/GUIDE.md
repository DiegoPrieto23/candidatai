# User guide

**English** · [Español](GUIA.md)

How to install CandidatAI, try it with the demo and use it every day with your own data and your
AI agent. To learn what it is and why it works this way, start with the [README](../README.md).

> The user interface is in Spanish. This guide quotes button and page names in Spanish with an
> English translation the first time, e.g. «Por revisar» (Triage).

## Contents

1. [Requirements](#1-requirements)
2. [Installation](#2-installation)
3. [Try the demo](#3-try-the-demo)
4. [Your data and your profile](#4-your-data-and-your-profile)
5. [Connect your agent](#5-connect-your-agent)
6. [Start the app every day](#6-start-the-app-every-day)
7. [Set up job sources](#7-set-up-job-sources)
8. [From job to application](#8-from-job-to-application)
9. [Tracking, replies and funnel](#9-tracking-replies-and-funnel)
10. [Interviews and received offers](#10-interviews-and-received-offers)
11. [The agent from the UI](#11-the-agent-from-the-ui)
12. [Configuration](#12-configuration)
13. [Updating](#13-updating)
14. [Troubleshooting](#14-troubleshooting)
15. [Development](#15-development)

## 1. Requirements

CandidatAI is built and tested on **Windows 11**. It should work on macOS and Linux (everything
uses `pathlib` and cross-platform tools), but that hasn't been tested yet.

| What | For | How |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python 3.12 and backend dependencies (no separate Python install needed) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Node LTS + pnpm | The UI | Node from nodejs.org; `npm install -g pnpm` (Node 25+ no longer ships `corepack`) |
| LibreOffice **or** Playwright's Chromium | CV and cover-letter PDFs | LibreOffice from libreoffice.org (if it isn't in `C:\Program Files\LibreOffice` or on the `PATH`, set `SOFFICE_PATH` in `.env`); Chromium with `uv run playwright install chromium` |
| An AI agent | Extracting jobs, assessing fit, writing the CV | Claude Code (reference), Codex or another one that speaks MCP or runs commands |
| Git | Cloning and updating | git-scm.com |

Open a new terminal after installing so the `PATH` is refreshed.

## 2. Installation

```powershell
git clone https://github.com/DiegoPrieto23/candidatai.git candidatai
cd candidatai\backend
uv sync                                # backend dependencies (creates .venv)
uv run playwright install chromium     # html templates and PDFs without LibreOffice
uv run cai doctor                       # checks the environment and tells you what's missing
uv run cai db upgrade                   # creates the database in data/
cd ..\frontend
pnpm install
```

Optional: `uv sync --extra matching` installs local semantic similarity (brings torch, ~1 GB).
Without it the score works the same, minus that component.

## 3. Try the demo

The demo is a fictional candidate with 60 jobs, 8 weeks of history and 2 CVs. It lives in
`data-demo/` and never touches your data.

```powershell
cd backend
uv run cai demo seed                         # --force to recreate it
$env:CAI_DATA_DIR = "data-demo"; uv run cai serve
# in a second terminal
cd frontend; pnpm dev                       # http://127.0.0.1:5173
```

The UI shows a "Modo demo" banner. To try the skills on the demo, start your agent with
`CAI_DATA_DIR=data-demo` so its MCP server uses that folder.

## 4. Your data and your profile

Everything of yours lives in `data/`, which is outside git: database, profile, CVs, templates,
photo, documents and emails. Keys go in `.env`, also outside git.

| What | Where | How |
|---|---|---|
| **Profile** (the source of truth for anything written about you) | `data/profile.yaml` | The `update-profile` skill reads your CV, asks for what's missing and validates it. Every change creates a version |
| **Your CV as a design** | `data/templates/<id>/` | Upload your CV in «Plantillas → Mi CV» (Templates → My CV) and use the `import-cv-template` skill. Word, PDF, image or HTML (Canva, Google Docs…) |
| **Photo** | `data/photo.jpg` (or png) | Each template crops it to its shape; it's included or not depending on the job's country |
| **Context** (style, narrative, criteria) | `data/contexto/*.md` | Guides the agent, but never backs a CV claim |
| **Source documents** (old CVs, degrees, references) | `data/documentos/` | `update-profile` can read them, confirming before writing |

Your salary minimum goes in the profile's `private.salary_floor_eur`: the app uses it to compare
offers, but the agent never receives it.

## 5. Connect your agent

Open your agent **at the repository root**: that's where it finds the instructions
(`AGENTS.md`), the skills and the MCP server, already configured.

- **Claude Code:** `claude` at the root. Check with `/mcp` that the `candidatai` server is
  connected. Skills are invoked as `/generate-cv 42`.
- **Codex:** uses `.codex/` (generated). Skills are invoked as `$generate-cv 42`.
- **Other agents:** if they read `AGENTS.md` and speak MCP, register the `candidatai` server with the
  command in `.mcp.json`. If they don't speak MCP, every tool has its
  `uv run --directory backend cai … --json` command (table in
  [`AGENT_INTERFACE.md`](AGENT_INTERFACE.md), Spanish).

More detail, and how to add an agent: [`AGENTS_COMPAT.md`](AGENTS_COMPAT.md) (Spanish).

## 6. Start the app every day

Three processes, ideally each in its own terminal window and **outside your agent** (if the agent
runs out of memory it may close what it started):

```powershell
cd backend; uv run cai serve       # API at http://127.0.0.1:8000 (local only)
cd backend; uv run cai worker      # daily ingestion, scores, email, assisted applications, background runs
cd frontend; pnpm dev             # UI at http://127.0.0.1:5173
```

A typical day:

1. Open «Inicio» (Home): it tells you what's waiting (jobs to triage, CVs ready, overdue follow-ups).
2. Ask your agent for `process-jobs` and `assess-fit`, or press their buttons in the UI.
3. Triage in «Por revisar» (Triage).
4. `generate-cv` for the approved ones and, when you're ready, apply from the job page.
5. `daily-summary` sums all of that up in one answer.

## 7. Set up job sources

| Source | How to set it up |
|---|---|
| **Manual** | «Nueva oferta» (New job) in the UI: a URL or pasted text |
| **Target companies** (Greenhouse, Lever, Ashby) | «Empresas» (Companies) page or `cai sources add --kind greenhouse --name "Acme" --slug acme`. `cai sources discover --file companies.txt` finds the board of each company in a list |
| **InfoJobs and Adzuna** | Their keys in `.env` (`CAI_INFOJOBS_CLIENT_ID`/`_SECRET`, `CAI_ADZUNA_APP_ID`/`_KEY`) and a search with `cai sources add` |
| **Email alerts** | Create job alerts on LinkedIn, InfoJobs, Indeed… and have them land in a label of your mailbox. Set up read-only IMAP in `.env`: step by step in [`CONFIGURAR_CORREO.md`](CONFIGURAR_CORREO.md) (Spanish). Without IMAP, drop `.eml` files in `data/inbox/`. What comes in shows up in «Alertas» (Alerts) |
| **"Send to CandidatAI" button** | Load `extension/` as an unpacked extension in Chrome or Edge and paste the token from `cai capture token` into its options. Instructions: [`extension/README.md`](../extension/README.md) (Spanish) |
| **Your agent with your browser** | `search-jobs configurar` picks portals and searches («Plataformas», Platforms page); `search-jobs` browses them. LinkedIn stays off until you turn it on |
| **LinkedIn's public search** | The «Búsqueda pública sin sesión» (public search without login) switch on the LinkedIn card in «Plataformas». Off by default: it goes against LinkedIn's terms and may get your IP blocked for a while |

The worker runs the automatic sources every day at `connectors.daily_at`
(`config/policies.yaml`), and on start-up if one was missed. Detail of each source:
[`FUENTES_OFERTAS.md`](FUENTES_OFERTAS.md) (Spanish).

## 8. From job to application

1. **Extract:** `process-jobs` turns each posting's text into structured data. Posting text is
   untrusted content: if it carries hidden text or phrases aimed at an AI, the job page warns you.
2. **Assess:** the app computes the score and applies your hard filters; `assess-fit` adds a
   reasoned verdict.
3. **Triage:** in «Por revisar», `J`/`K` to move, `A` to approve, `D` to discard (with a reason)
   and `O` to open the job page. It can be undone.
4. **CV:** `generate-cv 42` writes the content, the code validates and renders it, and the
   `verifier` role reviews it. On the job page you change template, photo, colour and sections
   without spending agent time, compare renders and mark the one to send.
5. **Cover letter:** `generate-cover-letter 42`, with your general instructions (profile) and the job's
   (job page). It matches the CV.
6. **Application:** `prepare-application 42` prepares the screening answers. On the job page,
   «Preparar candidatura» (Prepare application) opens a dedicated browser (profile in
   `data/browser-profile/`), fills in the form and stops. You review it, and it only submits if you
   type the company name. At a captcha or a login it stops and hands you the tab. If you apply
   some other way, mark it as applied manually.

## 9. Tracking, replies and funnel

- **«Procesos» (Processes):** a kanban by stage. A card only changes column by recording what
  happened (reply, interview, test, offer, rejection). Interviews and tests create a dated
  milestone you can export to your calendar (`.ics`).
- **Follow-ups:** it reminds you of applications without a reply; `draft-follow-up` leaves
  the drafts (max. 2 per application) and the thank-you note after an interview. You send them.
- **«Respuestas» (Replies):** with IMAP set up, the app reads emails from the companies in your
  processes; `review-replies` proposes what happened and you accept it in «Respuestas».
- **«Embudo» (Funnel):** conversion by step, source, role, week, template, cover letter and
  referral, plus "Does the score work?". `review-search` runs the weekly retrospective.
- **Network:** import your LinkedIn connections (CSV export) with `cai contacts import-linkedin` and
  you'll see «Conoces a N» (You know N) on jobs at their companies; `draft-message` drafts the
  message.

## 10. Interviews and received offers

- `prepare-interview 42`: dossier and day-by-day plan up to the date, saved on the job page.
- `mock-interview 42`: one question at a time, with feedback and a better version based on
  your profile.
- `debrief-interview 42`: you tell it how it went; it saves notes and next steps and proposes new
  STAR stories for your profile (with your OK).
- **Received offers:** you record them on the job page and compare them in «Procesos → Ofertas
  recibidas» against your minimum and the advertised range. `prepare-negotiation 42` prepares
  arguments and a script without proposing figures.

## 11. The agent from the UI

Many pages have buttons that open your agent with the instruction already written:

- **In a terminal:** opens a window with your agent; you see and approve what it does.
- **In the background** (Claude Code): for skills that don't ask questions (`process-jobs`,
  `assess-fit`, `generate-cv`). It runs without a window, only with the app tools it needs, and
  you follow its progress on the «Agente» (Agent) page. Requires `cai worker`.
- **«Dejar para mi próxima sesión»** (Leave for my next session): stores the request;
  `handle-requests` does it when you open your agent.

## 12. Configuration

- **`.env`** (at the root, outside git): `CAI_DATA_DIR`, `SOFFICE_PATH`, InfoJobs and Adzuna keys,
  IMAP (`CAI_IMAP_HOST`, `CAI_IMAP_PORT`, `CAI_IMAP_USER`, `CAI_IMAP_PASSWORD`, `CAI_IMAP_FOLDER`,
  `CAI_IMAP_REPLIES_FOLDER`), `CAI_BROWSER_CHANNEL` (`chrome` or `msedge` for assisted
  applications), `CAI_EMBEDDINGS=off`. Nothing is required.
- **`config/policies.yaml`:** triage threshold, score weights, daily ingestion time, email polling,
  limits for browser search and for LinkedIn's public search, "job closed" phrases… After changing
  the score, `cai match rescore` recalculates and `cai eval matching` measures the effect.
- **Your profile:** preferences (roles, level, remote mode, locations, languages), default template,
  template rules and photo policy per country.

## 13. Updating

With your agent **closed** (its MCP server locks the Python environment):

```powershell
copy data\candidatai.db data\candidatai.db.bak     # backup
git pull
cd backend; uv sync; uv run cai db upgrade
cd ..\frontend; pnpm install
```

Restart `cai serve`, `cai worker` and your agent.

## 14. Troubleshooting

| Symptom | Fix |
|---|---|
| Something's wrong and you don't know what | `uv run cai doctor` checks database, PDF, Chromium, templates, photo, email and capture |
| "Ejecuta `cai db upgrade`" | There are new migrations: `uv run cai db upgrade` |
| `uv sync` fails with "file in use" | Close your agent (its MCP server uses `cai-mcp.exe`) and try again |
| No PDFs | Install LibreOffice or run `uv run playwright install chromium`; `cai doctor` checks it |
| The UI can't reach the API | Start `cai serve`; the UI expects the API at `127.0.0.1:8000` |
| Port 5173 is busy | Another `pnpm dev` is still open: close it (the API only accepts the UI on that port) |
| Nothing comes in by itself in the morning | `cai worker` must be running |
| Accents look wrong in `cai --help` | Known Windows console (cp1252) issue; `--json` output is fine |

## 15. Development

```powershell
cd backend
uv run pytest                                   # tests
uv run ruff check --fix; uv run ruff format     # style
uv run cai eval matching                         # matching quality
cd ..\frontend
pnpm typecheck; pnpm test; pnpm build
pnpm gen:api                                    # regenerates the client after API changes
cd ..
uv run scripts/sync_agents.py                   # regenerates agent configuration from .agents/
```

Project rules, architecture and the phase-based workflow: [`AGENTS.md`](../AGENTS.md),
[`ARCHITECTURE.md`](ARCHITECTURE.md) and [`DESARROLLO_POR_FASES.md`](DESARROLLO_POR_FASES.md)
(Spanish). Contributing: [`CONTRIBUTING.md`](../CONTRIBUTING.md).
