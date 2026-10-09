# Security policy

FinBrain OS is a competition entry for the 2026 Shenzhen FinTech competition (International Track). It is not a commercial service yet. Only the `main` branch is maintained.

## Reporting a vulnerability

Report it privately through this repository's [security advisories](https://github.com/tanhongsheng050204-code/2026-SHENZHEN-FINTECHATHON-INTERNATIONAL-TRACK/security/advisories/new). Please do not open a public issue.

Include what you found, how to reproduce it, and what an attacker could do with it. Do not access other people's data, and do not run denial-of-service or automated scanning against the hosted demo.

We aim to:
- reply within 3 working days;
- tell you whether we accept the report;
- fix accepted issues as quickly as the risk requires.

We will credit you unless you prefer not to be named.

## Scope

**In scope:**
- the code in this repository;
- the hosted demo at `finbrainos.vercel.app` and its API.

**Out of scope:** third-party services we use, such as Supabase, Vercel and Google Cloud. Report those to their own security teams.

## What we have already documented

Known residual risks, the threat model and the incident runbook are in [`docs/standards/`](docs/standards/README.md).
