# User guide

**English** · [Español](GUIA.md)

How to install CandidatAI, try it with the demo and use it every day with your own data and your
AI agent. To learn what it is and why it works this way, start with the [README](../README.md).

> The user interface is in English and Spanish: switch with the globe button at the bottom of the
> sidebar (see [Language](#language)). This guide quotes the English names.

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

**To use it** you only need Windows and, if you want Word CVs on top of PDFs, LibreOffice. The
installer takes care of the rest (uv, Python and the Chromium that renders PDFs). For the agent's
part you also need **an AI agent** (Claude Code, Codex…; see section 5).

**To develop it** (clone the repository and change the code):

| What | For | How |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | Python 3.12 and backend dependencies (no separate Python install needed) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Node LTS + pnpm | Building and developing the UI | Node from nodejs.org; `npm install -g pnpm` (Node 25+ no longer ships `corepack`) |
| LibreOffice **or** Playwright's Chromium | CV and cover-letter PDFs | LibreOffice from libreoffice.org (if it isn't in `C:\Program Files\LibreOffice` or on the `PATH`, set `SOFFICE_PATH` in `.env`); Chromium with `uv run playwright install chromium` |
| Git | Cloning and updating | git-scm.com |

Open a new terminal after installing so the `PATH` is refreshed.

## 2. Installation

### To use it: the installer

In PowerShell (no administrator rights needed):

```powershell
iwr -useb https://raw.githubusercontent.com/DiegoPrieto23/candidatai/main/install.ps1 -OutFile $env:TEMP\cai-install.ps1
powershell -ExecutionPolicy Bypass -File $env:TEMP\cai-install.ps1
```

The installer:

1. installs [uv](https://docs.astral.sh/uv/) if it's missing (it brings Python 3.12);
2. downloads the latest CandidatAI release, with the UI already built (no Node needed);
3. puts it in `%LOCALAPPDATA%\CandidatAI\app`, and your data in `%LOCALAPPDATA%\CandidatAI\data`;
4. prepares the environment, the PDF Chromium and the database;
5. creates a **"CandidatAI"** shortcut on the desktop and in the Start menu.

Opening the shortcut starts everything and opens your browser at `http://127.0.0.1:8000`. Keep the
window that appears open while you use it; to close CandidatAI, close that window.

- **Before installing**, `-WhatIf` (at the end of the second line) explains what it would do
  without changing anything. In the examples below, if PowerShell refuses to run scripts, use
  `powershell -ExecutionPolicy Bypass -File .\install.ps1 …` instead of `.\install.ps1 …`.
- **Updating:** run the installer again (with CandidatAI closed). Your data isn't touched, and
  the app's `.env` (`…\CandidatAI\app\.env`) is kept.
- **Uninstalling:** `.\install.ps1 -Uninstall` removes the app and the shortcuts, not your data
  (with `-RemoveData`, your data too, after confirming).
- While the repository is private or no release has been published, the one-line command has
  nothing to download: install from your copy of the repository (below) with
  `.\install.ps1 -Source <repository folder>`, after building the UI (`pnpm build`).

### To develop it: clone the repository

```powershell
git clone https://github.com/DiegoPrieto23/candidatai.git candidatai
cd candidatai\backend
uv sync                                # backend dependencies (creates .venv)
uv run playwright install chromium     # html templates and PDFs without LibreOffice
uv run cai doctor                      # checks the environment and tells you what's missing
uv run cai agents doctor               # which AI agents you have, which one is used and what's missing
cd ..\frontend
pnpm install
pnpm build                             # the built UI that `cai start` serves
```

Optional: `uv sync --extra matching` installs local semantic similarity (brings torch, ~1 GB).
Without it the score works the same, minus that component.

## 3. Try the demo

The demo is a fictional candidate with 60 jobs, 8 weeks of history and 2 CVs. It lives in its own
folder and never touches your data. There are two: in English (a candidate in Dublin) and in
Spanish (a candidate in Galicia).

```powershell
cd backend
uv run cai demo seed --lang en --dir data-demo-en      # --force to recreate it
$env:CAI_DATA_DIR = "data-demo-en"; uv run cai start
```

Without `--lang en` you get the Spanish demo in `data-demo/`. Your browser opens at
`http://127.0.0.1:8000` with a "Demo mode" banner. To try the skills on the
demo, start your agent with `CAI_DATA_DIR` pointing at the demo folder so its MCP server uses it.

## 4. Your data and your profile

Everything of yours lives in `data/`, which is outside git: database, profile, CVs, templates,
photo, documents and emails. Keys go in `.env`, also outside git.

| What | Where | How |
|---|---|---|
| **Profile** (the source of truth for anything written about you) | `data/profile.yaml` | The `update-profile` skill reads your CV, asks for what's missing and validates it. Every change creates a version |
| **Your CV as a design** | `data/templates/<id>/` | Upload your CV in **Templates → My CV** and use the `import-cv-template` skill. Word, PDF, image or HTML (Canva, Google Docs…) |
| **Photo** | `data/photo.jpg` (or png) | Each template crops it to its shape; it's included or not depending on the job's country |
| **Context** (style, narrative, criteria) | `data/contexto/*.md` | Guides the agent, but never backs a CV claim |
| **Source documents** (old CVs, degrees, references) | `data/documentos/` | `update-profile` can read them, confirming before writing |
| **What you've done in public** (repositories, portfolio, Kaggle, Scholar, verifiable certifications) | `data/profile.yaml` | The `expand` skill, or "Expand profile from my links" in "My profile". Use it **right after creating your profile**: it proposes projects, skills (with no level: you set it), achievements with the numbers the source gives and certifications, each with its link in `source`, and writes only what you accept. Public web only: no LinkedIn, nothing behind a login. Needs an agent with web search |

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

### Without paying for tokens: free and local models

Besides your subscription (Claude, ChatGPT), you can use open-source agents with a **local model**
(Ollama or LM Studio: free, and nothing leaves your computer) or a **free cloud model** (OpenRouter
`:free`, Antigravity's free plan: free, with daily limits, and the postings and your profile go to
the provider). With Ollama, set `OLLAMA_CONTEXT_LENGTH=32768` or more: with its default 4,096,
agents don't work. `cai agents doctor` and each agent's card tell you which models you have and
whether the context is enough. Models of about 8B or less tend to fail on the CV. Full guide, with
recommended models by memory and what leaves your computer in each case:
[`MODELOS_GRATIS.md`](MODELOS_GRATIS.md) (Spanish).

## 6. Start the app every day

- **With the installer:** open the "CandidatAI" shortcut. To close it, close its window.
- **From the repository:** `cd backend; uv run cai start`. It starts the API (which also serves
  the UI) and the worker in one command, applies pending migrations and opens your browser.
  Ctrl+C to close. Its logs go to `data/logs/start-*.log`.
- **To develop the UI** with hot reload: `uv run cai start --dev` also starts Vite and opens
  `http://127.0.0.1:5173`. You can also run `cai serve`, `cai worker` and `pnpm dev` separately,
  each in its own window.

Start CandidatAI **outside your agent** (its own window or the shortcut): if the agent runs out of
memory it may close what it started.

A typical day:

1. Open **Home**: it tells you what's waiting (jobs to triage, CVs ready, overdue follow-ups).
2. Ask your agent for `process-jobs` and `assess-fit`, or press their buttons in the UI.
3. Triage in **To review**.
4. `generate-cv` for the approved ones and, when you're ready, apply from the job page.
5. `daily-summary` sums all of that up in one answer.

## 7. Set up job sources

| Source | How to set it up |
|---|---|
| **Manual** | **New job** in the UI: a URL or pasted text |
| **Target companies** (Greenhouse, Lever, Ashby, Personio, Teamtailor, Workable, SmartRecruiters, Recruitee) | **Sources → Target companies** page or `cai sources add --kind greenhouse --name "Acme" --slug acme`. `cai sources discover --file companies.txt` finds the board of each company in a list. How to find the slug: [`FUENTES_OFERTAS.md`](FUENTES_OFERTAS.md#cómo-encontrar-el-slug) (Spanish) |
| **InfoJobs and Adzuna** | Their keys in `.env` (`CAI_INFOJOBS_CLIENT_ID`/`_SECRET`, `CAI_ADZUNA_APP_ID`/`_KEY`) and a search with `cai sources add` |
| **Manfred and freehire.me** | No keys: a search on the same page or with `cai sources add --kind manfred --name Manfred --query "data engineer"` (for freehire, also `--country` and `--remote-only`) |
| **Email alerts** | Create job alerts on LinkedIn, InfoJobs, Indeed… and have them land in a label of your mailbox. Set up read-only IMAP in `.env`: step by step in [`CONFIGURAR_CORREO.md`](CONFIGURAR_CORREO.md) (Spanish). Without IMAP, drop `.eml` files in `data/inbox/`. What comes in shows up in **Alerts** |
| **"Send to CandidatAI" button** | Load `extension/` as an unpacked extension in Chrome or Edge and paste the token from `cai capture token` into its options. Instructions: [`extension/README.md`](../extension/README.md) (Spanish) |
| **Your agent with your browser** | `search-jobs configurar` picks portals and searches (**Sources → Platforms** page); `search-jobs` browses them. LinkedIn stays off until you turn it on |
| **LinkedIn's public search** | The **Public search without signing in** switch on the LinkedIn card in **Sources → Platforms**. Off by default: it goes against LinkedIn's terms and may get your IP blocked for a while |

The worker runs the automatic sources every day at `connectors.daily_at`
(`config/policies.yaml`), and on start-up if one was missed. Detail of each source:
[`FUENTES_OFERTAS.md`](FUENTES_OFERTAS.md) (Spanish).

## 8. From job to application

1. **Extract:** `process-jobs` turns each posting's text into structured data. Posting text is
   untrusted content: if it carries hidden text or phrases aimed at an AI, the job page warns you.
2. **Assess:** the app computes the score and applies your hard filters; `assess-fit` adds a
   reasoned verdict.
3. **Triage:** in **To review**, `J`/`K` to move, `A` to approve, `D` to discard (with a reason)
   and `O` to open the job page. It can be undone.
4. **CV:** `generate-cv 42` writes the content, the code validates and renders it, and the
   `verifier` role reviews it. On the job page you change template, photo, colour and sections
   without spending agent time, compare renders and mark the one to send.
5. **Cover letter:** `generate-cover-letter 42`, with your general instructions (profile) and the job's
   (job page). It matches the CV.
6. **Application:** `prepare-application 42` prepares the screening answers. On the job page,
   **Prepare application** opens a dedicated browser (profile in
   `data/browser-profile/`), fills in the form and stops. You review it, and it only submits if you
   type the company name. At a captcha or a login it stops and hands you the tab. If you apply
   some other way, mark it as applied manually.

## 9. Tracking, replies and funnel

- **Processes:** a kanban by stage. A card only changes column by recording what
  happened (reply, interview, test, offer, rejection). Interviews and tests create a dated
  milestone you can export to your calendar (`.ics`).
- **Follow-ups:** it reminds you of applications without a reply; `draft-follow-up` leaves
  the drafts (max. 2 per application) and the thank-you note after an interview. You send them.
- **Replies:** with IMAP set up, the app reads emails from the companies in your
  processes; `review-replies` proposes what happened and you accept it in **Replies**.
- **Funnel:** conversion by step, source, role, week, template, cover letter and
  referral, plus "Is the score right?". `review-search` runs the weekly retrospective. At the
  end, **Your search in numbers** (or `cai stats story`): your figures since the start, with no
  company names, and a line to share in a README if you want to.
- **Network:** import your LinkedIn connections (CSV export) with `cai contacts import-linkedin` and
  you'll see “You know N” on jobs at their companies; `draft-message` drafts the
  message.

## 10. Interviews and received offers

- `prepare-interview 42`: dossier and day-by-day plan up to the date, saved on the job page.
- `mock-interview 42`: one question at a time, with feedback and a better version based on
  your profile.
- `debrief-interview 42`: you tell it how it went; it saves notes and next steps and proposes new
  STAR stories for your profile (with your OK).
- **Received offers:** you record them on the job page and compare them in **Processes → Offers
  received** against your minimum and the advertised range. `prepare-negotiation 42` prepares
  arguments and a script without proposing figures.

## 11. The agent from the UI

Many pages have buttons that open your agent with the instruction already written:

- **In a terminal:** opens a window with your agent; you see and approve what it does.
- **In the background** (Claude Code; OpenCode for `process-jobs` and `assess-fit`): for skills
  that don't ask questions (`process-jobs`, `assess-fit`, `generate-cv`). It runs without a
  window, only with the app tools it needs, and you follow its progress and usage on the **Agent**
  page. If your agent can't, the menu suggests one that can. Requires `cai worker`.
  - **Cost:** the **Cost** section of the **Agent** page adds up tokens, time and, if the agent
    reports it, money, by action, agent and model (7 and 30 days), with how much each skill
    weighs; the job page shows what was spent on that job and the funnel, per sent application and
    per interview. What you do in a terminal doesn't count: there the agent doesn't report usage.
  - **Threshold before spending:** `assess-fit` in the background only assesses jobs with a
    minimum score (by default, the triage threshold minus 10; change it under **Cost**). Triage
    says why a job below it stays unassessed.
  - **Several at once:** one at a time by default. With `background_runs.max_parallel` (up to 4)
    in `config/policies.yaml` several run at once, never two for the same job; with
    `per_agent: {opencode: 1}` you cap a local model.
- **Leave for my next session**: stores the request;
  `handle-requests` does it when you open your agent.

**Which agent opens.** On the “Agent” page, the “Agents” section shows the agents you have, what
each one can do and how to install the missing ones. There you pick the default agent, each
agent's model and, in the “By action” table, a different agent or model for a specific action (e.g.
OpenCode with a local model to process postings and Claude Code for the CV). Each button's dropdown
says which agent it would use (“with Claude Code ▾”) and lets you use another one just this once.
If an agent isn't suited to an action (it has no browser to search for postings, say), the button
says so and doesn't launch it. With nothing chosen, `CAI_AGENT` from `.env` or the first installed
agent is used.

**Spending tiers.** On the same page, “Economy”, “Balanced” and “Maximum” store the agent and model
for the main actions. “Economy” uses a local model to process, assess and classify replies, and
your most capable agent for the CV. Fill them in once and apply one with a click. “Undo the last
one” puts your preferences back as they were.

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

### Language

The interface is in **English** and **Spanish**. The globe button at the bottom of the sidebar
(or of the menu on a phone) opens the list of languages; the change is instant and the app
remembers it in this browser. The first time, it follows your browser's language: Spanish if it's
Spanish, English otherwise. Dates and numbers follow the language too. Changing it redraws the
page: a dialog or a half-written form closes, so finish it first.

What the interface doesn't translate: your own data (jobs, profile, notes), what your agent writes
(CVs, letters and assessments follow each job's language) and a few messages that the server
writes without a code to translate (some warnings and run results), which stay in Spanish.

## 13. Updating

**With the installer:** run it again; your data (`%LOCALAPPDATA%\CandidatAI\data`) isn't touched and
migrations apply by themselves.

**From the repository**, with your agent **closed** (its MCP server locks the Python environment):

```powershell
copy data\candidatai.db data\candidatai.db.bak     # backup
git pull
cd backend; uv sync
cd ..\frontend; pnpm install; pnpm build
```

`cai start` applies migrations when it starts. Restart CandidatAI and your agent.

## 14. Troubleshooting

| Symptom | Fix |
|---|---|
| Something's wrong and you don't know what | `uv run cai doctor` checks database, PDF, Chromium, templates, photo, email and capture |
| "Ejecuta `cai db upgrade`" | There are new migrations: `uv run cai db upgrade` |
| `uv sync` fails with "file in use" | Close your agent (its MCP server uses `cai-mcp.exe`) and try again |
| No PDFs | Install LibreOffice or run `uv run playwright install chromium`; `cai doctor` checks it |
| The UI can't reach the API | Start CandidatAI (`cai start` or the shortcut) and keep its window open |
| "Port 8000 is used by another program" | Close that program or use `cai start --port 8001` |
| The built UI is missing | In the repository, `cd frontend; pnpm install; pnpm build` (the installer ships it) |
| Nothing comes in by itself in the morning | CandidatAI must be open (`cai start` runs the worker) |
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
