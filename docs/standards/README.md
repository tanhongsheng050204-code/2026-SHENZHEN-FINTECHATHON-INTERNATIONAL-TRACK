# Standards pack

How DuitDuit's controls line up with published guidance. Each control is tied to the code that implements it and the test or evaluation task that checks it. DuitDuit is not certified under any standard: "aligned" means mapped, not audited.

| Document | What it covers |
|---|---|
| [owasp-agentic-mapping.md](owasp-agentic-mapping.md) | OWASP Top 10 for Agentic Applications (2026): one control and one check per risk |
| [agent-registry.md](agent-registry.md) | One card per agent: purpose, tools, side effects, autonomy, reviewer, limits, evaluation. Aligned with the NIST AI RMF and ISO/IEC 42001 inventory practices. |
| [threat-model.md](threat-model.md) | STRIDE over the main assets and trust boundaries |
| [incident-response.md](incident-response.md) | What to do when something goes wrong, in order |
| [known-risks.md](known-risks.md) | Residual risks we accept or have not fixed yet |

## How to check the claims yourself

Every command runs from `backend/`.

| Check | Command | What it produces |
|---|---|---|
| Evaluation harness | `uv run python -m eval.run ../output` | `output/eval-report.md` and `output/eval-report.json` |
| Full test suite | `uv run pytest` | Pass or fail for every test |

The evaluation harness runs 22 functional tasks and 8 adversarial ones. It works offline, with no model provider.

CI repeats all of this on every push (`.github/workflows/ci.yml`). It also runs:
- `pip-audit` and `npm audit` on the dependencies;
- a `gitleaks` secret scan of the full git history;
- an SPDX software bill of materials.

## Where the evaluation stands (2026-10-09)

**On `main`:** 26 tasks pass and 4 skip.

The 4 skips wait for the teammate's Plan 2 (identity and guardrails) and Plan 3 (data importers) code, which is not committed yet:
- ADV-01, ADV-02 and ADV-08 need the Plan 2 content guardrail.
- F20 needs the Plan 3 business tables.

**With that code applied in a scratch copy:** all 30 tasks pass, including all 8 adversarial cases.
