# OWASP Top 10 for Agentic Applications (2026): FinBrain mapping

Each row lists the risk, FinBrain's control, where the control lives, and the evaluation task or test that checks it. Task IDs refer to `backend/eval/tasks.json`.

**Status values:**
- **Built** — on `main` and checked.
- **Built with Plan 2** — the control is the teammate's uncommitted Plan 2 code. It passes in a scratch copy and skips on `main` until merged.

| Risk | FinBrain control | Where | Check | Status |
|---|---|---|---|---|
| ASI01 Agent goal hijack | <ul><li>Ingested content is classified before use; prompt injection in English, Malay and Chinese is quarantined.</li><li>Agents route goals with fixed rules and call a deterministic engine; model output cannot pick tools.</li></ul> | <ul><li>`app/security/guardrails.py` (Plan 2)</li><li>`app/services/agent_runtime.py`</li></ul> | ADV-01, ADV-02, F11–F14 | Built with Plan 2 |
| ASI02 Tool misuse and exploitation | <ul><li>Every tool call is checked against the agent's manifest: built agent, released skill, read or draft side effect only.</li><li>Plan 2 adds a persistent kill switch and daily tool and cost budgets.</li></ul> | <ul><li>`agent_runtime.authorize`</li><li>`guardrails.authorize_tool` (Plan 2)</li></ul> | ADV-03, `tests/test_agent_runtime.py` | Built; budgets with Plan 2 |
| ASI03 Identity and privilege abuse | <ul><li>Agents never exceed the requesting person's role.</li><li>Exact amounts go only to permitted roles; everyone else sees a band.</li><li>Agent runs are bound by HMAC to the tenant and the person who started them.</li><li>Sharing and money decisions need a recent authenticator step-up (Plan 2).</li></ul> | <ul><li>`app/security/detokenize.py`</li><li>`agent_runtime.goal_for`</li><li>`require_step_up` (Plan 2)</li></ul> | ADV-04, F17, `test_run_cannot_be_read_by_another_tenant` | Built; step-up with Plan 2 |
| ASI04 Agentic supply chain | <ul><li>Locked dependencies (`uv.lock`, `package-lock.json`).</li><li>CI runs `pip-audit`, `npm audit` (high and above), a `gitleaks` scan of the full history, and an SPDX SBOM.</li><li>The model provider is optional: every path works offline.</li></ul> | `.github/workflows/ci.yml` (supply-chain job) | The CI job itself. A 2026-10-09 local run found 76 known vulnerabilities in 5 Python packages and 1 high in npm; all were fixed in the commit that adds the job. | Built |
| ASI05 Unexpected code execution | <ul><li>No tool executes code.</li><li>Uploads are allowlisted by type and checked by file signature before parsing, in memory.</li></ul> | `app/services/upload_ingestion.py`, `app/integrations/telegram/extractors.py` | ADV-05 | Built |
| ASI06 Memory and context poisoning | <ul><li>Ingested text is stored as protected data, with personal values tokenized.</li><li>Nothing ingested can create an action.</li><li>The conversation planner refuses payloads that still contain personal data, and falls back to the deterministic path.</li></ul> | `app/services/ingestion.py`, `app/services/conversation_planning.py` | ADV-06 | Built |
| ASI07 Insecure inter-agent communication | <ul><li>The supervisor and the agents are typed function calls in one process.</li><li>There is no agent-to-agent network channel.</li></ul> | `app/services/agent_runtime.py` | `tests/test_agent_runtime.py` | Built (by design) |
| ASI08 Cascading failures | <ul><li>A provider timeout or error drops to the deterministic path instead of failing the request.</li><li>A refused tool stops the run before anything streams.</li></ul> | `conversation_planning.plan_conversation`, `agent_runtime.run_events` | ADV-07, `test_refused_tool_stops_the_run_before_streaming` | Built |
| ASI09 Human–agent trust exploitation | <ul><li>Every proposal shows its evidence and autonomy level.</li><li>Money movement needs a maker and a different checker.</li><li>A supplier bank-change request is quarantined for callback (Plan 2).</li><li>Nothing is sent or paid without a person.</li></ul> | <ul><li>`app/stubs/inbox.py` decisions</li><li>`guardrails.content_risk` (Plan 2)</li></ul> | F05, F15, ADV-08 | Built; quarantine with Plan 2 |
| ASI10 Rogue agents | <ul><li>Global and per-agent kill switches that persist (Plan 2).</li><li>Autonomy is earned from the review record; L3 is never delegated.</li><li>The trust page shows guardrail events.</li></ul> | <ul><li>`app/services/agent_security.py` (Plan 2)</li><li>`app/stubs/agents.change_autonomy`</li></ul> | F10, `test_refused_tool_stops_the_run_before_streaming` | Built; persistence with Plan 2 |

## Gaps we know about

- The guardrail patterns are deterministic. A paraphrased injection can slip past them, which is why tools are allowlisted independently.
- The disclosure path currently restores email and phone tokens for every role. Exact amounts are banded. Whether contact details should be masked for `general_employee` is an open decision, recorded in [known-risks.md](known-risks.md).
