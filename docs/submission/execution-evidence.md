# FinBrain OS — Execution Evidence

Recorded 2026-10-09 on commit `2e334fd` (`main`). Every figure below came from a run on that commit; the commands reproduce it.

## Automated checks

| Check | Command (from the folder shown) | Result |
| --- | --- | --- |
| Backend test suite | `backend/`: `uv run pytest -q` | **394 passed** |
| Topic E contract tests | `backend/`: `uv run pytest -q tests/test_contract_*.py` | **132 passed** |
| Backend lint | `backend/`: `uv run ruff check .` | All checks passed |
| API contract drift | included in the suite (`test_committed_contract_matches_the_code`) | `docs/api/topic-e-contract.json` matches the code |
| Frontend type-check and build | `frontend/`: `npm ci && npm run build` | Built with no errors |
| Frontend lint | `frontend/`: `npx eslint .` | 0 errors (14 pre-existing warnings) |
| Same-origin API proxy | local test against a fake backend (method, body, cookies, CSRF, streaming, refused paths) | All assertions passed |

CI (`.github/workflows/ci.yml`) runs the backend lint and tests and the frontend type-check, lint and build on every push.

## What the tests cover (Topic E contract)

| Area | Examples of behaviour pinned by tests |
| --- | --- |
| Roles and positions | One person can hold several positions; staff decide only their own positions' items |
| Review inbox | L2 needs the owner; L3 needs a maker who holds the position and a different checker; L3 drafts cannot be edited; Compliance sees all items read-only; each item says whether the viewer may decide |
| Cash flow | Shortfall on day 23 of the demo company; scenarios move events; risk signals never move the balance |
| Financing | Ineligible products name the failing rule; the scorecard scores 695 (grade B) from published bands; points follow the bands at their edges |
| Passport | Documents with fields that were never issued are rejected; verification recomputes the SHA-256 |
| Settings | Safety floors (owner alerts, MFA for privileged roles, 60-minute idle cap); security changes and security rollbacks wait for Compliance; equivalent submissions are not changes |
| Templates and imports | Unknown or malformed placeholders and personal numbers refused; import mappings match on every header regardless of order, case and byte-order mark |
| Agent runs | Events stream in order and are documented as `AgentRunEvent` items in the contract |

## Live demonstrations

| What | Where |
| --- | --- |
| Preview of every Topic E screen with synthetic data (signed in as a demo owner) | https://finbrain-topic-e-preview.vercel.app |
| Public lender view of a shared Passport, with verification | https://finbrain-topic-e-preview.vercel.app/lender/passports/demo-grant-token |
| API contract (OpenAPI) | `docs/api/topic-e-contract.json` |

## Not yet evidenced

Stated plainly so nothing is over-claimed:

- **Plan 2 identity and security backend** (cookie sessions, email codes, TOTP, persisted settings, guardrails): code exists in a teammate's working copy; it has not been committed or tested end to end.
- **Audit-chain anchors**: the daily `anchor-audit-chain.yml` workflow exists, but no `audit-anchors/` files are in the repository yet; it needs the `PRODUCTION_DATABASE_URL` secret to run.
- **Agent evaluation harness** (scripted financial tasks and adversarial guardrail tests, Plan 7): not built.
- **Production deployment** on Cloud Run behind the same-origin proxy: documented in `docs/deployment/cloud-run-and-vercel.md`, not yet performed.

## Before submission

- [ ] Re-run the commands above on the final commit and update this page.
- [ ] Add screenshots of the CI run and the demo flow.
- [ ] Add the audit-anchor evidence once the workflow has run.
- [ ] Link the demo video and its mainland-China mirror.
