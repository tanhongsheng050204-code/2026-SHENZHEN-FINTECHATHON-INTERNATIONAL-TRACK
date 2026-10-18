# Simulated bank: operation logs, 2026-10-18

Execution evidence for the competition's "simulated-account / sandbox operation logs". No real bank is connected; DuitDuit's simulated bank is a sandbox ledger on the company's audit chain.

Generated offline from the real review-inbox routes and sandbox ledger, on a synthetic in-memory company:

```
cd backend
python -m scripts.export_sandbox_evidence ../docs/submission/evidence/sandbox-2026-10-18
```

| File | What it shows |
| --- | --- |
| [operations.log](operations.log) | Every step in order, with UTC time, HTTP status and outcome |
| [sandbox-ledger.json](sandbox-ledger.json) | The ledger after the run: one payment, with its `SIM-` reference |
| [audit-chain.jsonl](audit-chain.jsonl) | The company's hash-chained workflow audit log: each entry's `prev_hash` is the previous entry's `event_hash` |
| [eval-report.md](eval-report.md) | The offline evaluation run the same day: 57 of 57 pass, including ADV-25 (an induced transfer cannot run) |

What the run shows:

1. An agent proposes an L3 payroll payment of RM38,400.00. It lands in the review inbox; the agent cannot execute it.
2. An employee tries to approve it: refused (`409 maker_approval_required`).
3. Finance approves as the maker: `awaiting_second_approval`, and the ledger is still empty.
4. Finance tries to approve again as the checker: refused (`409 same_person_cannot_approve_twice`).
5. The owner approves as a different checker: `approved`, reference `SIM-975AA7E173`, and the simulated bank pays it.
6. Running the bank again returns the same reference: the payment is made once.
7. A rejected L3 item, a half-approved L3 item and an approved L2 item: the bank pays none of them.
8. The final ledger holds one payment, and the audit chain verifies intact (10 entries).

The ledger event carries ids and the amount only, never titles or names. All data is synthetic.
