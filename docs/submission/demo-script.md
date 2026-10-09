# A day with DuitDuit — Demo Video Script

Topic E: SME Finance Copilot · Planned running time: **5:00** · Updated 2026-10-10

One day at **Synthetic Trading Co.**, a fictional Malaysian home-goods importer.
Keep **“Synthetic demo data · fictional company”** visible throughout the video,
including the Telegram insert and lender view. The clock labels tell the story;
they are not evidence that the recording happened at those times.

**Status:** script written and checked against the implementation. The video,
Telegram insert, live microphone/provider rehearsal and timed rehearsal are not
recorded or measured in this writing pass. Automated evidence is in
[execution-evidence.md](execution-evidence.md).

## Recording setup

- Use the backend-connected app with persistent storage in a disposable demo
  tenant. Prepare actual authenticated Owner, Finance, Employee (sales) and
  Compliance sessions for the **same tenant** in separate browser profiles.
  The visible persona selector alone does not change backend authorization.
- Use the built-in synthetic cash fixture for the day-23 story: a demo tenant
  without an imported opening bank balance gets this fixture, while its review
  proposals still persist. Confirm the displayed values before recording:
  RM20,560.00 likely balance, RM50,000.00 cash minimum and RM29,440.00 gap.
  A tenant using imported records can have different dates and results; its
  narration must use the actual card values.
- Frame the browser at 1440×900, light theme, English UI. Record scenes separately
  and trim loading and account-switch pauses. Keep result labels and approval
  states readable. The timeline below allocates 300 seconds; rehearse the actual
  actions and narration with a timer before calling the video five minutes long.
- Prepare a prerecorded Telegram briefing clip from an opted-in demo account.
  Crop recipient identifiers and keep “Prerecorded · synthetic demo” visible.
  A real delivered clip is an asset required for that version of the recording;
  none is supplied by this script. If it is unavailable, use a clearly labelled
  “Illustration · delivery not verified” insert and the alternate line in scene 1.
- Voice needs a secure browser context, WebM/Opus recording support and a configured
  Gemini transcription provider. Rehearse with the synthetic request only.
  Record a working clip before the presentation; if voice is unavailable, use
  the labelled typed fallback in scene 4.
- Use a fictional lender address such as `lender@bank.example`, a seven-day grant
  and ranges only. The Share button issues a link; it does not email it. The
  recording may open that link in another tab without sending it to anyone.
- For the authenticator shot, record the real step-up prompt when verification
  has expired, then crop or obscure the code entry. A still-recent verification
  can satisfy the check without a new prompt. Never add a pretend prompt or
  expose authenticator setup secrets in the video.

## Timeline

| Scene | Video time | Story time | Role | Screen and purpose |
| --- | --- | --- | --- | --- |
| 1 | 0:00–0:35 | 08:00 | Owner | Telegram insert → in-app morning briefing |
| 2 | 0:35–1:35 | 09:00 | Owner | Bank meeting pack → inbox review → Passport sharing |
| 3 | 1:35–2:15 | 10:30 | Finance → Owner | Late-payer drafts → explicit owner confirmation |
| 4 | 2:15–2:55 | 11:00 | Employee (sales) | Voice preview → Send → payment request refused |
| 5 | 2:55–3:45 | 14:00 | Finance | Pay-everyone forecast → honest cash gap → options |
| 6 | 3:45–4:20 | 17:00 | Owner | Month-end checklist → unresolved work and not measured |
| 7 | 4:20–5:00 | 17:15 | Compliance | Trust & audit → workflow events → verify both chains |

## 1. 08:00 — The morning briefing (0:00–0:35)

**Action:** play the labelled prerecorded Telegram clip for a few seconds, then
cut to the signed-in Owner's in-app briefing. If needed, ask
**“Good morning, what needs me today?”** in Ask DuitDuit. Point to the actual cash,
inbox and sharing lines returned for this account.

**Narration, with a delivered clip:**

> It is eight o'clock at Synthetic Trading Co. All the company data in this
> demonstration is fictional. This prerecorded Telegram briefing shows an
> opted-in demo notification, with ranges and counts. The owner opens DuitDuit
> for the details. The in-app briefing brings together the cash risk, the items
> waiting for review and sharing that needs attention.

**If the insert is an illustration:** replace the Telegram sentence with
“This labelled illustration shows the opt-in Telegram briefing format; delivery
is not verified in this demonstration.” Do not present it as a delivered message.

**Hold:** the synthetic-data caption and the briefing's actual attention lines.

## 2. 09:00 — Prepare for the bank meeting (0:35–1:35)

**Action:** as Owner, type **“Prepare me for the bank meeting”** and press Send.
Show **Bank meeting pack**: Cash forecast, Financing profile, Missing facts and
Lender sharing. Open the review inbox and select **“Bank meeting: review lender
sharing”**. Show its L2 status and draft; approve that specific proposal.

Then open **Financing & Passport**. Issue a Passport if none exists, choose its
sharing controls, enter the fictional lender address, set **For (days)** to 7,
leave **Show exact values** unchecked and press **Share**. Complete the real
authenticator check if prompted. Briefly show the issued link; opening the lender
view is optional if it fits the scene. Capture only synthetic document contents.

**Narration:**

> At nine, the owner asks, “Prepare me for the bank meeting.” The pack brings
> together the forecast, financing facts and anything missing. Its sharing step
> is an L2 proposal waiting in the inbox. I review and approve that proposal.
> Then I choose the Passport, recipient and seven-day expiry and complete the
> authenticator check to issue a link showing ranges. Proposal approval alone
> creates no link. This is preparation for a conversation with a lender, not
> a loan approval.

**Hold:** pending proposal → recorded approval → separately issued grant.
The link is issued by the person's Share action; no email is sent in this scene.

## 3. 10:30 — Chase the late payers (1:35–2:15)

**Action:** switch to the authenticated Finance session. Type
**“Chase the late payers”**, press Send and show **Late payer reminders**.
Use **Open review inbox →** to inspect one of this playbook's generic drafts and
its customer/receivable references. Finance prepares and reviews these L2 drafts;
their final approval belongs to the Owner.

Cut to the Owner session, review the same draft and press its approval control.
If using an assistant Confirm card, name that draft specifically and inspect the
listed item ids/titles before confirming. Keep the shot on the playbook's draft,
not an unrelated sample payment or reminder. Show the resulting approval state.

**Narration:**

> Later, Finance asks, “Chase the late payers.” DuitDuit groups the records into
> one reminder draft per customer and puts them in the review inbox. Finance
> checks the evidence and wording. These are L2 items, so the owner reviews
> and confirms them. The recorded result is approval of a draft. This playbook
> has not delivered an email or Telegram reminder, and it never treats preparing
> a draft as permission to contact a customer.

**Hold:** the L2 label, the draft and the Owner's recorded decision.

## 4. 11:00 — An employee tries a payment command (2:15–2:55)

**Action:** switch to the authenticated Employee/sales session. Click the
microphone, say **“Approve all payments”** and click to stop. Show the protected
transcript in the input box before doing anything else. Then press **Send**.
Hold the refusal card and its actual explanation: no waiting payment item is
the employee's to approve; money items need Finance and the Owner.

**Narration:**

> An employee tries, “Approve all payments,” by voice. Recording stops and the
> transcript appears for review; it is not sent automatically. The employee
> presses Send and receives a refusal. Speaking a command gives no extra
> authority. Finance would still need an explicit confirmation for its allowed
> money items, a recent authenticator check and a different checker. The same
> rules apply to typed and transcribed requests.

**Fallback:** if capture or transcription fails, show **“Voice unavailable · typed
request shown”**, type the same request and show its refusal. Replace the first
two narration sentences with “Voice is unavailable in this session, so the
employee types the same request.” Do not call this a successful acoustic test.

**Hold:** transcript awaiting Send → refusal with reason. No payment is executed.

## 5. 14:00 — Can we pay everyone? (2:55–3:45)

**Action:** return to Finance. Type **“Can I pay everyone this month?”** and press
Send. Show **Pay everyone**, especially **Planning window** and **Can we pay?**.
With the built-in synthetic fixture, point to:

- **Next 30 days** from the actual as-of date shown on the card.
- **Day 23:** likely balance **RM20,560.00** against the **RM50,000.00** minimum.
- **Gap:** **RM29,440.00** below that minimum.

Show **Collect earlier** and **Discuss payment timing** if the card provides
them. Use the displayed scenario results; keep their illustrative labels visible.

**Narration:**

> At two, Finance asks, “Can I pay everyone this month?” The card explicitly
> uses a rolling next-thirty-days forecast. On day twenty-three, the synthetic
> likely balance is twenty thousand five hundred and sixty ringgit, leaving
> a twenty-nine thousand four hundred and forty ringgit gap below the company's
> fifty-thousand-ringgit minimum. That is a gap to our cash floor, not an
> overdraft. Earlier collections and different supplier timing are illustrative
> options. The books and payment dates stay unchanged.

**Hold:** minimum, likely balance, gap and one available scenario. The date is
relative to this forecast; do not describe day 23 as the 23rd of the month.

## 6. 17:00 — Close the month honestly (3:45–4:20)

**Action:** switch to Owner and ask **“Close the month”**. Show **Month-end
checklist**: Recent import, e-Invoices, Open inbox items and Bank reconciliation.
Read the actual statuses. The synthetic-forecast tenant can have no imports or
e-invoices on record; show those missing-record states instead of substituting
sample data. Hold **“Bank reconciliation: not measured”**.

**Narration:**

> Before finishing, the owner asks, “Close the month.” DuitDuit checks the
> import record, e-invoice issues and persisted inbox items. Missing records
> remain visible, and unresolved work stays on the checklist. Bank reconciliation
> is explicitly “not measured.” This is a review checklist, not a declaration
> that the books are closed. The assistant prepares what the person needs to
> review and leaves that judgment with them.

**Hold:** the complete checklist with its actual statuses and the not-measured line.

## 7. 17:15 — Follow the audit chain (4:20–5:00)

**Action:** switch to the authenticated **Compliance** session. Open **Trust &
audit**, then **Audit & access**. Select **Workflow events** and locate the
records generated by the earlier scenes using their time, actor and resource id.
Inspect a playbook/command event and one **Review Decision**. If voice succeeded,
inspect its duration/outcome event; a typed fallback has no successful voice event.
The voice audit contains neither audio nor transcript. Show the separate
Passport/grant event only if issuance succeeded in scene 2. Press
**Re-verify both chains** and show the actual returned chain status.

**Narration:**

> Compliance finishes the day in Trust and audit. The workflow chain connects
> prepared proposals, the people's decisions and any separately issued share
> grant to their actors and records. Assistant events keep kinds and ids;
> voice keeps duration and outcome, not the recording or transcript. We verify
> the chains against the stored events. DuitDuit helps this fictional company
> prepare, decide and review its day, with people confirming the actions and
> unmeasured work kept visible.

**Hold:** actor/resource references, a person's Review Decision and the real
verification result. Requests and proposals are recorded as requests/proposals;
only explicit review decisions are decision events. An employee's refusal is an
assistant-command record, not a payment decision. A valid local hash chain is
not a claim of independent certification or an external anchor.

## Evidence and recording handoff

| Scene | Implementation and automated evidence to consult |
| --- | --- |
| 1 | `app/services/briefing.py`, `app/services/briefing_push.py`, `components/BriefingCard.tsx`; delivery clip remains a recording asset |
| 2 | `app/services/playbooks.py` (`bank_meeting`), `screens/Financing.tsx`; `tests/test_playbooks.py` verifies approval creates no Passport or active grant |
| 3 | `app/services/playbooks.py` (`chase_late_payers`), `screens/ReviewInbox.tsx`; reminder L2 proposals remain subject to Owner approval and no delivery |
| 4 | `components/VoiceInput.tsx`, `tests/test_assistant_voice.py`; `A-trick-spoken`, `A-trick-typed`, `A-role-limits` |
| 5 | `app/services/playbooks.py` (`pay_everyone`), `tests/test_playbooks.py`, evaluation F01; scenario changes are read-only |
| 6 | `app/services/playbooks.py` (`month_end`), `tests/test_playbooks.py`; reconciliation is not measured |
| 7 | `screens/Audit.tsx`, `app/routes/audit_log.py`; `A-no-confirm`, `A-no-words-in-audit`, workflow-chain tests |

The source paths above are relative to `backend/` for `app/` and `tests/`, and
`frontend/src/` for `components/` and `screens/`. Evaluation ids refer to
`backend/eval/tasks.json`. Passing offline tests does not establish that this
browser/provider recording or hosted authentication has been rehearsed.

Record which scenes used the working backend, a prerecorded insert or a fallback.
Show only fictional company data, crop personal account details and credentials,
and retain synthetic labels in the final edit. Export MP4 (H.264); provide a
shareable mirror whose mainland-China reachability has actually been checked.
No mirror or exported video is produced by this script.
