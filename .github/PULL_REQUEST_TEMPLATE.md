## What and why

<!-- What this changes and the problem it solves. Link the issue: "Closes #12". Puedes escribir en español. -->

## How to check it

<!-- Steps with the demo data (`cai demo seed`), or the tests that cover it. A screenshot if it changes the UI. -->

## Checklist

- [ ] Tests pass: `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` (backend) and `pnpm typecheck && pnpm test` (frontend)
- [ ] `uv run scripts/sync_agents.py --check` passes (if `.agents/` changed)
- [ ] No personal data in code, tests, fixtures, screenshots or docs: only `demo/` data
- [ ] No LLM SDK or API call added; nothing is sent to a third party without the user's confirmation in the UI
- [ ] New logic lives in `backend/app/services/`; a new MCP tool has its `cai … --json` command
- [ ] A schema change has its Alembic migration; a job state change goes through an event
- [ ] UI texts are in `locales/es` and `locales/en`
- [ ] Anything a user would notice is under `## [Sin publicar]` in `CHANGELOG.md` (English is fine)
- [ ] The README, start guide, user guide or feature list are updated in both languages, if affected
