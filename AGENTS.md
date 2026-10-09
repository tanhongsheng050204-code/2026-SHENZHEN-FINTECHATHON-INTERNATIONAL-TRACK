# Rules for coding agents working on DuitDuit

DuitDuit is an SME finance copilot built for the 2026 Shenzhen FinTech competition (International Track, Topic E).
- Backend: FastAPI and SQLAlchemy on Supabase Postgres with row-level security, in `backend/`.
- Frontend: React 19, Vite and TypeScript, in `frontend/`.

The current open work is in `docs/handoff/2026-10-10-assistant-remaining-work.md`.

## House rules

- **Commits:** commit as the repository's configured git user. Do not change git config. Do not add co-author trailers. Ask before pushing.
- **Secrets:** never print, log, commit or paste them. `backend/.env` holds production keys, so don't open or echo its values.
- **No invented facts:**
  - Make only claims you can prove from code, tests or data.
  - Label demo data as synthetic.
  - Never invent statistics.
  - If something is not measured, say "not measured".
- **Personal data:** API responses, logs and audit events never carry raw personal data or the words people typed. Audit events record kinds and ids only.
- **The assistant never acts on its own:**
  - Anything that changes records or goes outside the company is a review-inbox proposal the person confirms.
  - Money (L3) also needs a step-up code.
  - Every action stays within the person's role.
- **Records on the audit chain:** new records are stored as events on the workflow audit hash chain (`write_workflow_event`), not as new tables, unless a migration is unavoidable.
- **Before declaring anything done**, run the full backend suite, the evaluation harness and the frontend build. The commands are in the handoff file.
- **Others' work:** don't modify or commit other people's uncommitted work.
