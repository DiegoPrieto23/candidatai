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
| **Add a job** by pasting its URL or its text (with role and company, and the button says what's missing); duplicates are detected and linked to the original | `/nueva` | <!-- media:provisional --> [New job](img/en/new-job.webp) |
| **Inbox**: every job with filters (stage, **work mode**, **with or without salary** and **fit**: no fit, or 50, 70 or 85 and up), search, signals and stage; each stage explains what it is and what to do to move on, with its button; drop the ones to complete or to read with **Discard** and **Undo**; "Closed" with its date, sortable | `/bandeja` | <!-- media:provisional --> [Inbox](img/en/inbox.webp) · <!-- media:provisional --> [▶ Discard](img/en/anim/discard.webp) |
| **Company career sites**: their jobs come in every day from Greenhouse, Lever, Ashby, Personio, Teamtailor, Workable, SmartRecruiters and Recruitee (public APIs, no scraping). You add one with its name and the address of its careers site: the app works out the system and the places in the address ("Only Madrid"), and only shows the jobs that fit you | `/fuentes/empresas` | <!-- media:provisional --> [Companies](img/en/sources-companies.webp) |
| **Job boards** (in “Search jobs → Where to search”): **Set up with my agent** recommends job boards and prepares their searches; when you add a known one (InfoJobs, Tecnoempleo, Indeed, LinkedIn), the searches come from the roles and locations in your profile, and each job board can be edited. The ones your agent browses, with a unique priority each, access type and jobs per run, each explained with its ⓘ; InfoJobs and Adzuna with keys, Manfred and freehire.me without | `/fuentes/plataformas` | <!-- media:provisional --> [Platforms](img/en/sources-platforms.webp) |
| **Search jobs**: a single panel with what you're after, editable right there: your roles and places as tags (each place with what you accept there), work mode and level as chips, and how many jobs per job board; each change is saved to your profile, with **Undo**, and adding a role suggests the titles of jobs you approve that it doesn't cover yet. On the right, which job boards your agent will search, how many jobs at most and **Search now**. Below, your job boards as cards you tick, with their status and what they found last time. A notice says “Searching…” on every page and changes when your agent finishes, with what it brought | `/buscar` | <!-- media:provisional --> [Search jobs](img/en/search.webp) |
| **Discard or close from the job page**: at any stage, without going through the Board. Until you send it you discard with a reason; once sent you close the application (rejected, you withdraw or expired). **Reopen** undoes it | `/jobs/:id` | |
| **Notices from your agent**: whatever you launch with a button shows in a notice on every page, with what it has done so far, and changes when it finishes. If it needs to know something to continue, it asks in a notice and you answer there | all | |
| **More settings for your search**: they open in the same **Search jobs** panel, with the number of groups that have something set: years of experience, minimum salary (private), languages, contract and hours, and what you rule out (title words, consultancies, agencies, jobs with no employer named). They're saved together, with **Reset**, **Discard changes** and **Undo** | `/buscar/ajustes` | <!-- media:provisional --> [More settings](img/en/search-settings.webp) |
| **Search portals with your browser**: your agent walks your saved searches, with page limits and pauses, adds what fits and stops at captchas | `search-jobs` | |
| **Job alerts by email**: LinkedIn, InfoJobs, Indeed… alerts come in by themselves, read-only over IMAP or from `.eml` files; **several mailboxes**, with a step-by-step guide for Gmail, Outlook, Yahoo and iCloud; summary jobs expire after 21 days | `/fuentes/correo` | <!-- media:provisional --> [▶ Add a mailbox](img/en/anim/mailbox.webp) |
| **Complete summary jobs**: jobs that arrive as a summary, one by one: open them on their portal, send them with the browser button or discard them, with `J`/`K`, `O`, `D` and Undo; those that fail your filters stay folded away | `/bandeja/por-completar` | <!-- media:provisional --> [To complete](img/en/alerts.webp) |
| **"Send to CandidatAI" button**: a Chrome/Edge/Brave extension that sends the job you're viewing (LinkedIn, InfoJobs, Indeed, Glassdoor, Manfred, Ticjob and company career sites on Greenhouse, Lever, Workday, Ashby…) or completes an alert summary. The “Browser button” tab guides you through loading it, warns if it's out of date and connects it in one click, without the terminal, and shows how to use it in a short animation. Paste a LinkedIn URL into “New job” and it points you to it or to pasting the text | `/fuentes/extension` | <!-- media:provisional --> [Browser button](img/en/sources-extension.webp) |
| **LinkedIn public search** (off by default, at your own risk): once a day, without your account or cookies; your agent can't turn it on | `/fuentes/plataformas` | |
| **Find your companies' job boards** from a list of names | `cai sources discover` | |
| **Read and assess the new jobs in one step** ("Assess new jobs"): extracts each one into structured data with an isolated subagent that only sees that job, then assesses it against your profile; text aimed at an AI is flagged, never obeyed | `process-jobs` | |
| **Still open? and reposts**: the app checks whether a job is still published (never closes it by itself) and marks "Reposted ×N" | `/jobs/:id` | |
| **Points to review on each job**: very wide salary range, hidden company or agency, temporary contract, old posting and AI screening, each explained; they don't change the fit | `/bandeja` | |

## 2. Review

| Feature | Where | Screenshot |
|---|---|---|
| **Home**: on a fresh install, what the app does and what your agent is, and “Getting started” (upload your CV to create your profile, or start it by hand, and choose where to search with your agent); with no agent installed, “You need an AI agent” with the steps to install Claude Code; then what's waiting today (jobs to process or assess, replies, follow-ups), the best fits, ready to send and the next milestones | `/` | <!-- media:provisional --> [Home](img/en/home.webp) |
| **How it works**: who does what (you, your agent and the app), the whole journey in five steps with a link to each screen, and the guides, always at hand in the menu | `/como-funciona` | <!-- media:provisional --> [How it works](img/en/how-it-works.webp) |
| **Help on every page**: a button at the bottom right (or the `?` key) searches the [frequent questions](FAQ.md) and the user guide, offline and without an agent, and each answer takes you to the screen where it is done | “Help” button | |
| **Assistant**: a labelled button at the bottom right, next to the help one, opens a chat to ask for something in your own words (Enter sends it), with separate conversations and a history in a sidebar, like ChatGPT or Claude. It runs in the background if your agent can, or otherwise waits for your next session; the panel shows the progress, its questions and the answer, with links to whatever changed. Submitting, approving, discarding and deleting are always confirmed by you | “Assistant” button, `assistant` | |
| **Hard filters and an explained 0-100 fit** (“good fit”, “possible fit” or “low fit”, and on hover what each part measures; without a fit, the job page says what's missing): level, years, remote mode, location, languages and words that discard; skill coverage weighted by your level, preferences and optional local semantic similarity | `/bandeja/revision` | <!-- media:provisional --> [To review](img/en/triage.webp) |
| **Review with the keyboard**: `J`/`K` to move, `A` approve, `D` discard with a reason, `O` open, and Undo | `/bandeja/revision` | <!-- media:provisional --> [▶ Keyboard](img/en/anim/triage.webp) |
| **Your agent's verdict**: fit with risks and questions, citing your deal-breakers; in the background it skips low-fit jobs. It always flags jobs with possible text aimed at an AI, which never come out as a strong fit. On each job, “Assess this job”; for new jobs, “Assess new jobs” | `assess-fit` | |
| **"You know N people here"**: your LinkedIn connections (official CSV export) matched to each company | `/jobs/:id` | |
| **The job page**, in tabs (Posting, Application, Process, Company, History & notes) that open on the one that fits the stage: extraction, fit breakdown, signals, history, notes, cost in agent time, and every section below | `/jobs/:id` | <!-- media:provisional --> [Job](img/en/job.webp) |

## 3. CV and cover letter

| Feature | Where | Screenshot |
|---|---|---|
| **Tailored CV**: with your instructions for that job if you want (what to highlight, the language…); your agent writes it citing evidence from your profile for every line; the code rejects what isn't there and a separate role verifies it; the job page shows a notice with the PDF as soon as it's ready | `generate-cv` | |
| **CV editor**: the CV at reading size next to a panel to ask for changes, edit the text or change the design | | |
| **Correct a CV you already have**: say what to change and your agent touches only that, without inventing anything and verifying the result, or edit the text yourself (the app warns about what your profile doesn't back); every version is kept, with what changed and “Go back to this version” | `correct-cv`, `verify-cv` | |
| **Same content, any design**: template, photo, colour and sections in the job page, rendered in seconds without the agent; compare renders and mark the one you send; the PDF layout is checked | `/jobs/:id` | <!-- media:provisional --> [CV](img/en/job-cv.webp) · <!-- media:provisional --> [▶ Another design](img/en/anim/cv.webp) |
| **Cover letter** following your general and per-job instructions, verified, as TXT and PDF matching the CV design; edit it by hand if you want. On the job page, **Write letter** asks for it like **Generate CV**: in a terminal, in the background or for your next session | `generate-cover-letter` | <!-- media:provisional --> [Letter](img/en/job-letter.webp) |
| **CV templates**: built-in (Word and HTML) and yours; every one can be used as default and deleted (the app's are removed from your list and restored from "Deleted templates"; yours can also be renamed); "Upload new template" (or dragging the file) turns a sample CV into a new template, with the name you choose ("My CV" by default) and the card showing "Converting…" while your agent works; "Compare with the original" shows the uploaded CV next to the template | `/perfil/plantillas` | <!-- media:provisional --> [Templates](img/en/templates.webp) |
| **Import your own CV design** from Word, PDF, an image, HTML, Canva or Google Docs as a template | `import-cv-template` | |

## 4. Apply

| Feature | Where | Screenshot |
|---|---|---|
| **Application package**: the chosen CV, screening answers with a copy button each and the cover letter; salary and anything not in your profile are left for you | `prepare-application` | <!-- media:provisional --> [Package](img/en/job-package.webp) |
| **Assisted application**: the app fills Greenhouse, Lever, Ashby or generic forms in its own browser, stops before sending, shows what it filled and from where, and **only submits after you type the company name** | `/jobs/:id` | <!-- media:provisional --> [▶ Assisted application](img/en/anim/apply.webp) |
| **Application emails and LinkedIn messages** (≤ 300 characters) for the recruiter, the hiring manager or a peer, saved as drafts you send yourself | `draft-message` | |
| **Archive of what you sent**: CV, letter, answers and a README in its own folder, unchanged if you redo the CV later | `/jobs/:id` | |

## 5. Tracking and replies

| Feature | Where | Screenshot |
|---|---|---|
| **Board** (in Processes): a kanban that only moves through recorded events (mouse, keyboard or touch) and only to the right, with 3 to 5 columns of your choice (stages grouped and renamed), received offers side by side and follow-up reminders | `/procesos` | <!-- media:provisional --> [Processes](img/en/processes.webp) |
| **Process page**: milestones with date and time (edit, cancel or, if added by mistake, delete them), contacts and referrals, drafts and **What happened?**, which once in process records another interview, a test or the offer, and only lets you accept once there's an offer | `/jobs/:id` | <!-- media:provisional --> [Process](img/en/job-interview.webp) |
| **Calendar**: interviews, tests and deadlines, added from any day, with an `.ics` per milestone and a feed with alarms for your calendar, plus browser reminders while the app is open (no emails) | `/calendario` | <!-- media:provisional --> [Calendar](img/en/calendar.webp) |
| **Company replies**: the app reads your email read-only and keeps only messages from companies you applied to. When you accept or ignore one, a notice says which job it was logged on; **Ignore** can be undone from it. With the keyboard: `J`/`K` to move, `A` accept, `I` ignore | `/respuestas` | <!-- media:provisional --> [Replies](img/en/replies.webp) |
| **Classify replies**: your agent proposes interview (with its date), test, offer, rejection or nothing; nothing changes stage until you accept | `review-replies` | |
| **Follow-ups and thank-you notes** as drafts (at most 2 follow-ups per application) | `draft-follow-up` | |

## 6. Interviews and offers

| Feature | Where | Screenshot |
|---|---|---|
| **Company research** with sources: product, news, engineering culture, stack and red flags. It asks nothing: it lets you know when it finishes and you see it in the job page | `research-company` | <!-- media:provisional --> [Dossier](img/en/job-research.webp) |
| **Interview prep**: a PDF guide and a day-by-day plan, shown under the interview; each round with its type (HR, technical, case, final) and your instructions, which the mock interview uses too; ask for changes to a guide you already have, even after the interview, and your agent touches only that; the previous version is kept, with what changed and **Go back to the previous version** | `prepare-interview`, `correct-interview-guide` | <!-- media:provisional --> [Plan](img/en/job-interview.webp) |
| **Mock interview**: one question at a time, concrete feedback and a better answer from your profile only | `mock-interview` | |
| **Debrief**: notes and next steps, the next round predicted and new STAR stories proposed; with a received offer, what to clarify before accepting | `debrief-interview` | |
| **Received offers** compared against your minimum and the posted range, **without your agent ever seeing your minimum** | `/procesos` | <!-- media:provisional --> [Received offer](img/en/job-offer.webp) |
| **Negotiation**: arguments from your profile, questions, a script with the figure left for you, and a clause-by-clause contract review (not legal advice) | `prepare-negotiation` | |

## 7. Strategy and profile

| Feature | Where | Screenshot |
|---|---|---|
| **Your funnel**, also on the home page: from sent to accepted, with a branch for each group that stopped at a step and how it stands now (waiting, rejected, interviewing…); each branch takes you to those applications | `/` · `/resultados` | |
| **Results**: what works for you, in sentences (which channel gets more replies, how long companies take, where they reply sooner, your best source), and below, by question: reply rate and time by channel, conversion by source, role, week and referral, and discard reasons | `/resultados` | <!-- media:provisional --> [Funnel](img/en/funnel.webp) |
| **"Is the fit right?"**: reply and interview rates by fit, verdict, source, template, letter and referral, with 95 % intervals, under "More analysis" in Results | `/resultados` | |
| **Your search in numbers**, ready to share (figures only, never companies), under "More analysis" in Results | `/resultados` · `cai stats story` | |
| **Weekly retrospective**: what's working and what to change, without touching weights or filters | `review-search` | |
| **Skills to build**: what your jobs ask for that isn't in your profile yet; "it's the same as…" aliases, "I have it" and "I don't have it", 25 at a time | `/perfil/skills` | <!-- media:provisional --> [Skills](img/en/skills.webp) |
| **Training plan** with verified resources for your real gaps, and an assessment of a course or project | `training-plan` | |
| **Widen the search** with adjacent job titles from what you approve and discard | `broaden-search` | |
| **My profile, editable**: with no profile yet, you upload your CV and your agent builds it from it, or you start it by hand (name, headline, role and levels); context files are created from their template even before you have a profile; an index to jump to each section; skills and languages at the top; collapsible experience, projects, education, certifications and STAR stories; CV and letter preferences, context and style samples; the unsaved-changes notice names the blocks and takes you to them; keeps your file's comments, with Undo | `/perfil` | <!-- media:provisional --> [Experience](img/en/profile-experience.webp) · <!-- media:provisional --> [▶ Collapsible](img/en/anim/profile.webp) |
| **CV photo (optional)**: upload it, frame it with zoom and drag (the preview has your template's shape), reframe it from the original, change or remove it in "My profile → About you"; it stays on your computer and your agent doesn't read it | `/perfil` | |
| **English summary**: "Generate English summary" asks your agent to translate your Spanish summary without adding anything; the suggestion appears next to the field so you can use, edit or discard it before saving | `/perfil` | |
| **Create or update your profile** from your CV or what you tell your agent | `update-profile` | |
| **Import information from a CV** ("My profile"): upload a CV and your agent adds to your profile what it is missing, showing you the differences and saving nothing without your OK | `update-profile` | |
| **Improve your profile** ("Improve my profile content"): reviews the whole profile (achievements without numbers, filler text, gaps) and suggests changes; plus, from your public GitHub, portfolio, Kaggle or Scholar, projects, skills and certifications, each with its source and only with your OK | `expand` | |
| **LinkedIn profile review** against your profile and the jobs you approve | `review-linkedin` | |

## 8. Settings, agents and the app

| Feature | Where | Screenshot |
|---|---|---|
| **Agent**: at the top, whether your agent is ready or how to install one, and what sets Claude (the chat) apart from Claude Code; folded away, default agent and one per action, background runs with progress, questions and Cancel, cost by action and model, spending levels and the score's meaning-based comparison | `/agente` | <!-- media:provisional --> [Agent](img/en/agent.webp) |
| **Every agent button explains itself**: what the skill does, what it changes and what it needs, on hover or keyboard focus | Every page | |
| **Keyboard navigation**: the first Tab shows “Skip to content”, which skips the menu, and focus is always visible, in light and dark. A row of filters (the Inbox stages, the replies) is a single Tab stop, moved through with the arrows | Every page | |
| **Leave it for your next session**: any button saves the order for your agent | `handle-requests` | |
| **Daily summary**: pending jobs (flagging any with text aimed at an AI), overdue follow-ups, next milestones and company replies to review | `daily-summary` | |
| **Sidebar** grouped and collapsible with what's waiting, light and dark theme, English and Spanish | `/` | <!-- media:provisional --> [Sidebar](img/en/sidebar-collapsed.webp) |
| **Demo mode** with a fictitious search where every page has something | `cai demo seed` | |
| **Install** with one line on Windows, macOS and Linux, or with Docker; `cai doctor` checks everything | [Guide](GUIDE.md) | |
| **Five agents**: Claude Code, Codex, Antigravity CLI, OpenCode and Qwen Code, over MCP or with `cai … --json`; free and local models | [`AGENTS_COMPAT.md`](AGENTS_COMPAT.md) | |
