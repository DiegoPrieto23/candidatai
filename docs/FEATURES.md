# Features

Everything CandidatAI does, in the order you use it: get jobs → review → CV and cover letter →
apply → tracking and replies → interviews and offers → strategy and profile → settings and agents.
Spanish version: [`FUNCIONALIDADES.md`](FUNCIONALIDADES.md).

**Where** is the page of the UI (its address after `http://127.0.0.1:8000`) or the **skill** your
agent runs (`/generate-cv 42` in Claude Code, `$generate-cv 42` in Codex, or just ask for it). Most
skills also have a button in the UI that opens your agent with the right order, in a terminal or in
the background. Nothing is ever sent to a company without you confirming it.

<!-- scripts/check_readme_coverage.py fails if a page or a skill is missing here, or if this list
and FUNCIONALIDADES.md stop matching row by row. -->


## 1. Get jobs

| Feature | Where | Screenshot |
|---|---|---|
| **Add a job** by pasting its URL or its text; duplicates are detected and linked to the original | `/nueva` | [New job](img/en/new-job.webp) |
| **Inbox**: every job with filters, search, signals and stage; drop the ones to complete or to extract with **Discard** and **Undo**; "Closed" with its date, sortable | `/bandeja` | [Inbox](img/en/inbox.webp) · [▶ Discard](img/en/anim/discard.webp) |
| **Target companies**: their jobs come in every day from Greenhouse, Lever, Ashby, Personio, Teamtailor, Workable, SmartRecruiters and Recruitee (public APIs, no scraping); "Test" shows how many pass your filters | `/fuentes/empresas` | [Companies](img/en/sources-companies.webp) |
| **Platforms**: the portals your agent browses, with a unique priority each, access type and jobs per run, each explained with its ⓘ; InfoJobs and Adzuna with keys, Manfred and freehire.me without | `/fuentes/plataformas` | [Platforms](img/en/sources-platforms.webp) |
| **Search portals with your browser**: your agent walks your saved searches, with page limits and pauses, adds what fits and stops at captchas | `search-jobs` | |
| **Job alerts by email**: LinkedIn, InfoJobs, Indeed… alerts come in by themselves, read-only over IMAP or from `.eml` files; **several mailboxes**, with a step-by-step guide for Gmail, Outlook, Yahoo and iCloud; summary jobs expire after 21 days | `/alertas` | [Alerts](img/en/alerts.webp) · [▶ Add a mailbox](img/en/anim/mailbox.webp) |
| **"Send to CandidatAI" button**: a Chrome/Edge extension that sends the job you're viewing (LinkedIn included) or completes an alert summary | [`extension/`](../extension/README.md) | |
| **LinkedIn public search** (off by default, at your own risk): once a day, without your account or cookies; your agent can't turn it on | `/fuentes/plataformas` | |
| **Find your companies' job boards** from a list of names | `cai sources discover` | |
| **Extract each job** into structured data with an isolated subagent that only sees that job; text aimed at an AI is flagged, never obeyed | `process-jobs` | |
| **Still open? and reposts**: the app checks whether a job is still published (never closes it by itself) and marks "Reposted ×N" | `/jobs/:id` | |
| **Dubious jobs in sight**: very wide salary range, hidden company or agency, temporary contract, old posting and AI screening, each explained; they don't change the score | `/bandeja` | |

## 2. Review

| Feature | Where | Screenshot |
|---|---|---|
| **Home**: what's waiting today (jobs to process or assess, replies, follow-ups), the best fits, ready to send and the next milestones | `/` | [Home](img/en/home.webp) |
| **Hard filters and an explained 0-100 score**: level, years, remote mode, location, languages and words that discard; skill coverage weighted by your level, preferences and optional local semantic similarity | `/por-revisar` | [To review](img/en/triage.webp) |
| **Review with the keyboard**: `J`/`K` to move, `A` approve, `D` discard with a reason, `O` open, and Undo | `/por-revisar` | [▶ Keyboard](img/en/anim/triage.webp) |
| **Your agent's verdict**: fit with risks and questions, citing your deal-breakers; in the background it skips low-score jobs. On each job, “Assess this job” when it has no assessment or an outdated one | `assess-fit` | |
| **"You know N people here"**: your LinkedIn connections (official CSV export) matched to each company | `/jobs/:id` | |
| **The job page**, in tabs (Posting, Application, Process, Company, History & notes) that open on the one that fits the stage: extraction, fit breakdown, signals, history, notes, cost in agent time, and every section below | `/jobs/:id` | [Job](img/en/job.webp) |

## 3. CV and cover letter

| Feature | Where | Screenshot |
|---|---|---|
| **Tailored CV**: your agent writes it citing evidence from your profile for every line; the code rejects what isn't there and a separate role verifies it; the job page shows a notice with the PDF as soon as it's ready | `generate-cv` | |
| **Same content, any design**: template, photo, colour and sections in the job page, rendered in seconds without the agent; compare renders and mark the one you send; the PDF layout is checked | `/jobs/:id` | [CV](img/en/job-cv.webp) · [▶ Another design](img/en/anim/cv.webp) |
| **Cover letter** following your general and per-job instructions, verified, as TXT and PDF matching the CV design; edit it by hand if you want | `generate-cover-letter` | [Letter](img/en/job-letter.webp) |
| **CV templates**: built-in (Word and HTML) and yours; "My CV" side by side with your profile | `/plantillas` | [Templates](img/en/templates.webp) |
| **Import your own CV design** from Word, PDF, an image, HTML, Canva or Google Docs as a template | `import-cv-template` | |

## 4. Apply

| Feature | Where | Screenshot |
|---|---|---|
| **Application package**: the chosen CV, screening answers with a copy button each and the cover letter; salary and anything not in your profile are left for you | `prepare-application` | [Package](img/en/job-package.webp) |
| **Assisted application**: the app fills Greenhouse, Lever, Ashby or generic forms in its own browser, stops before sending, shows what it filled and from where, and **only submits after you type the company name** | `/jobs/:id` | [▶ Assisted application](img/en/anim/apply.webp) |
| **Application emails and LinkedIn messages** (≤ 300 characters) for the recruiter, the hiring manager or a peer, saved as drafts you send yourself | `draft-message` | |
| **Archive of what you sent**: CV, letter, answers and a README in its own folder, unchanged if you redo the CV later | `/jobs/:id` | |

## 5. Tracking and replies

| Feature | Where | Screenshot |
|---|---|---|
| **Processes**: a kanban that only moves through recorded events (mouse, keyboard or touch), received offers side by side and follow-up reminders | `/procesos` | [Processes](img/en/processes.webp) |
| **Process page**: milestones with date and time (edit, cancel or, if added by mistake, delete them), contacts and referrals, drafts and what happened | `/jobs/:id` | [Process](img/en/job-interview.webp) |
| **Calendar**: interviews, tests and deadlines, with an `.ics` per milestone and a feed for Google Calendar | `/calendario` | [Calendar](img/en/calendar.webp) |
| **Company replies**: the app reads your email read-only and keeps only messages from companies you applied to | `/respuestas` | [Replies](img/en/replies.webp) |
| **Classify replies**: your agent proposes interview (with its date), test, offer, rejection or nothing; nothing changes stage until you accept | `review-replies` | |
| **Follow-ups and thank-you notes** as drafts (at most 2 follow-ups per application) | `draft-follow-up` | |

## 6. Interviews and offers

| Feature | Where | Screenshot |
|---|---|---|
| **Company research** with sources: product, news, engineering culture, stack and red flags | `research-company` | [Dossier](img/en/job-research.webp) |
| **Interview prep**: a PDF guide and a day-by-day plan, shown under the interview; each round with its type (HR, technical, case, final) and your instructions, which the mock interview uses too | `prepare-interview` | [Plan](img/en/job-interview.webp) |
| **Mock interview**: one question at a time, concrete feedback and a better answer from your profile only | `mock-interview` | |
| **Debrief**: notes and next steps, the next round predicted and new STAR stories proposed; with a received offer, what to clarify before accepting | `debrief-interview` | |
| **Received offers** compared against your minimum and the posted range, **without your agent ever seeing your minimum** | `/procesos` | [Received offer](img/en/job-offer.webp) |
| **Negotiation**: arguments from your profile, questions, a script with the figure left for you, and a clause-by-clause contract review (not legal advice) | `prepare-negotiation` | |

## 7. Strategy and profile

| Feature | Where | Screenshot |
|---|---|---|
| **Funnel**: conversion step by step, by source, role, week, template, cover letter and referral, time to first reply and discard reasons | `/embudo` | [Funnel](img/en/funnel.webp) |
| **"Is the score right?"**: reply and interview rates by score, verdict, source, template, letter and referral, with 95 % intervals, under "More analysis" in the Funnel | `/embudo` | |
| **Your search in numbers**, ready to share (figures only, never companies), under "More analysis" in the Funnel | `/embudo` · `cai stats story` | |
| **Weekly retrospective**: what's working and what to change, without touching weights or filters | `review-search` | |
| **Skills**: what your jobs ask for that your profile lacks; "it's the same as…" aliases, "I have it" and "I don't have it", 25 at a time | `/skills` | [Skills](img/en/skills.webp) |
| **Training plan** with verified resources for your real gaps, and an assessment of a course or project | `training-plan` | |
| **Widen the search** with adjacent job titles from what you approve and discard | `broaden-search` | |
| **My profile, editable**: collapsible experience and achievements, projects, education, skills, STAR stories, **Search** preferences (years, private minimum salary, words that discard, contract, company type), CV and letter preferences, context and style samples; keeps your file's comments, with Undo | `/perfil` | [Experience](img/en/profile-experience.webp) · [Search](img/en/profile-search.webp) · [▶ Collapsible](img/en/anim/profile.webp) |
| **Create or update your profile** from your CV or what you tell your agent | `update-profile` | |
| **Expand your profile** from your public GitHub, portfolio, Kaggle or Scholar, each item with its source and only with your OK | `expand` | |
| **LinkedIn profile review** against your profile and the jobs you approve | `review-linkedin` | |

## 8. Settings, agents and the app

| Feature | Where | Screenshot |
|---|---|---|
| **Agent**: default agent and one per action, background runs with progress, questions and Cancel, cost by action and model, spending levels and the score's meaning-based comparison | `/agente` | [Agent](img/en/agent.webp) |
| **Every agent button explains itself**: what the skill does, what it changes and what it needs, on hover or keyboard focus | Every page | |
| **Leave it for your next session**: any button saves the order for your agent | `handle-requests` | |
| **Daily summary**: pending jobs, overdue follow-ups and next milestones | `daily-summary` | |
| **Sidebar** grouped and collapsible with what's waiting, light and dark theme, English and Spanish | `/` | [Sidebar](img/en/sidebar-collapsed.webp) |
| **Demo mode** with a fictitious search where every page has something | `cai demo seed` | |
| **Install** with one line on Windows, macOS and Linux, or with Docker; `cai doctor` checks everything | [Guide](GUIDE.md) | |
| **Five agents**: Claude Code, Codex, OpenCode, Qwen Code and Antigravity CLI, over MCP or with `cai … --json`; free and local models | [`AGENTS_COMPAT.md`](AGENTS_COMPAT.md) | |
