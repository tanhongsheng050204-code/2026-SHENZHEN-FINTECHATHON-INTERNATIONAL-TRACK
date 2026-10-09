# Incident response runbook

**Owner:** the company owner, with the DuitDuit operator on call.

Work through the steps in order, and record each one with its time.

## 1. Contain (minutes)

| Situation | Action |
|---|---|
| An agent misbehaves, or a guardrail fires repeatedly | Owner or Compliance: **Agents & autonomy → Stop all agents**. Data stays untouched; people keep working. |
| A share link leaked | Owner: **Financing → the Passport or pack → revoke the grant**. The next view returns 410. |
| An account is compromised | Owner: **Team → Sign out everywhere** for that person (Plan 2), then reset their authenticator. |
| A server secret is exposed | Rotate `TOKEN_ROOT_SECRET`, `TOKEN_HASH_SECRET` and `VAULT_MASTER_KEY` in Cloud Run, then redeploy. Every share link and agent-run ID signed with the old root secret stops working. |

## 2. Assess (hours)

1. **Verify the audit chains.** Run `backend/scripts/verify_audit_anchors.py`, then compare against the latest file in `audit-anchors/`. A break shows the first altered event.
2. **Check what external parties saw.** Each grant's `external_grant_viewed` events show what a lender or auditor viewed, and when.
3. **Check what an account saw.** The disclosure chain shows which tokens it restored.

## 3. Notify

- **Personal data affected.** Notify the Personal Data Protection Commissioner and the affected people as the PDPA breach-notification duty requires. That duty was added by the 2024 amendment; confirm the current deadline in the Commissioner's guideline.
- **E-invoices affected.** Tell the company's tax agent if an e-invoice issued through MyInvois was wrong.

## 4. Recover and learn

1. Restart agents one at a time, starting at L1.
2. Add the attack as a new adversarial task in `backend/eval/tasks.json`, so CI keeps checking it.
3. Write down what happened, the timeline and the fix.
