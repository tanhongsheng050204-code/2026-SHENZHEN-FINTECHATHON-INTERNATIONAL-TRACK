# Deck additions: three slides judges from a bank will look for

Draft text for three slides that the current deck does not have. Each slide says only what the code shows, or labels the content as a plan or a proposal.

---

## Slide A: Where DuitDuit meets WeBank's own work

**Title:** Built to plug into open financial infrastructure

| What DuitDuit has today | Where it could go next (plan, not built) |
|---|---|
| **Financing Readiness Passport:** a lender sees amounts as bands, through an expiring, consented link, and can check the document against the company's hash-chained audit trail. | Anchor each Passport digest on a consortium chain such as **FISCO BCOS**, so a lender checks it on infrastructure banks already run instead of a GitHub file. |
| **Audit anchors:** a daily CI job commits each company's chain tail to `audit-anchors/` in the repository, outside the database's trust boundary. | The same anchor, written to a consortium chain shared by lenders. |
| **Privacy first:** personal data is tokenized and encrypted before any AI model sees it; lenders get bands, not raw records. | Train repayment models across lenders without moving raw data, for example with federated learning (**FATE**), and replace the hand-set scorecard weights with calibrated ones. |
| **Explainable scorecard:** every point has a published band and a reason. Method: "expert_weights", stated on screen. | Calibrate the weights on real repayment outcomes; the screen already has a "Calibrated" state for that. |

**Speaker note:** say plainly that the right-hand column is a plan. The left-hand column runs today.

---

## Slide B: Who pays (proposal)

**Title:** How DuitDuit would earn money: a proposal to test

Nothing here has been tested with customers. Present it as a hypothesis.

| Who | What they get | Proposed model |
|---|---|---|
| Small business | Forecast, alerts, analysis, review inbox, assistant | Monthly subscription, with a free tier for one user |
| Lender or bank | Verified Passports and pre-qualified applicants | Fee per completed, consented application |
| Accounting firm | Several client companies, audit packs | Per-client seat |

**Unit economics:** not measured. **Willingness to pay:** not measured.

**Speaker note:** if asked about numbers, say they are not measured yet and that the first pilot would measure them.

---

## Slide C: What is not done yet

**Title:** What we have not done yet

- **Hosting:** the API runs on a team member's machine through a temporary tunnel. Moving it to Cloud Run is written up, not done.
- **Reachability from mainland China:** the site is on `vercel.app`. A custom domain is needed and has not been tested from inside China.
- **Forecast accuracy:** not measured. Each day's forecast is now kept and will be scored against the bank balance, but no real company's statement has covered a forecast day yet. The synthetic demo company is never scored.
- **Scorecard:** hand-set weights, not calibrated on repayment outcomes.
- **Lenders:** matching stops at a drafted application pack. No lender receives it or answers.
- **Data in:** uploads, email, Telegram and e-invoices. No bank feed, point-of-sale, WhatsApp or WeChat connector.
- **Security assurance:** automated scans (OWASP ZAP, dependency audits, secret scanning) and 20 scripted adversarial tests. No independent penetration test.
- **Chinese:** four main screens read in Chinese; the translations are machine-assisted and not yet checked by a fluent reader.

**Speaker note:** judges respect a clear list more than a hidden gap. Keep this slide.
