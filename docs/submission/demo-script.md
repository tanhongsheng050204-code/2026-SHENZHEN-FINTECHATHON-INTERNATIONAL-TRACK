# A day with DuitDuit — Demo Video Script

Topic E: SME Finance Copilot · Running time: **5:00 maximum** · Updated 2026-10-10

One working day at the **SYNTHETIC Malaysian Home Goods Importer**, a fictional
company. The day uses the assistant built last (briefing, playbooks, voice, confirmations)
to walk through the product built first (imports, cash forecast, customers,
e-invoicing, financing and Passport, review inbox, autonomy and audit). Keep
**“Synthetic demo data · fictional company”** visible throughout, including the
Telegram insert and the lender view. The clock labels tell the story; they are
not evidence that the recording happened at those times.

**Status:** the script has been checked against a local copy of the deployed synthetic
tenant on 2026-10-10. The video, the Telegram insert, a live microphone and provider
rehearsal, and a timed rehearsal have **not** been recorded or measured. Automated
evidence is in [execution-evidence.md](execution-evidence.md).

## Recording setup

- **Tenant.** Record in the deployed synthetic tenant
  (`858f0c1c-42fa-52a2-91b3-80a19d816356`), which the four demo accounts open.
  Before recording, re-run the fixtures seed once on the provisioning connection:
  `python -m seed.topic_e_original_fixtures --tenant-id 858f0c1c-42fa-52a2-91b3-80a19d816356`.
  It is idempotent. It marks the August bills as paid (the opening balance already
  reflects them) and declares the company's registration date. Without this
  step, e-Invoicing shows overdue bills and financing shows months trading as
  not on record.
- **Dates move; amounts do not.** The seeded records have fixed dates, and the
  forecast counts from today. The shortfall was day 23 on 9 Oct, and it is one day
  sooner each day after. The likely balance (**RM20,560.00**), the minimum
  (**RM50,000.00**) and the gap (**RM29,440.00**) stay the same. **Record by 19 Oct.**
  On 20 Oct the first invoice passes its expected date and the numbers change.
  Always read the day number from the screen; never say "day 23" from memory.
- **Sessions.** Prepare authenticated Owner, Finance, Employee (sales) and
  Compliance sessions for this tenant in separate browser profiles. The visible
  persona selector alone does not change backend authorization.
- **Frame.** Use 1440×900, the light theme and the English UI. Record scenes
  separately and trim loading and account-switch pauses.
- **Telegram insert.** Use a prerecorded Telegram briefing clip from an opted-in
  demo account, with recipient identifiers cropped and the label "Prerecorded ·
  synthetic demo". If no delivered clip exists, use "Illustration · delivery not
  verified" and the alternate line in scene 1.
- **Voice.** Voice needs HTTPS, WebM/Opus support and a configured Gemini key.
  Rehearse with the synthetic request only. If voice is unavailable, use the typed
  fallback in scene 6.
- **Lender sharing.** Use a fictional lender address (`lender@bank.example`) and a
  seven-day grant, with ranges only. The Share button issues a link; it does not
  email it.
- **Step-up.** Record the real authenticator prompt when verification has expired,
  then obscure the code. Never stage a pretend prompt.

## Timeline

Legend: **N** marks a feature built in the assistant work; **O** marks one built
before it.

| Scene | Video time | Story time | Role | What it shows |
| --- | --- | --- | --- | --- |
| 1 | 0:00–0:25 | 08:00 | Owner | Telegram briefing **N** → Today page **O** → in-app briefing **N** |
| 2 | 0:25–0:55 | 08:30 | Owner | Data sources import **O** → cash forecast and range **O** |
| 3 | 0:55–1:50 | 09:00 | Owner | Bank meeting playbook **N** → scorecard and matches **O** → inbox L2 **O** → Passport share with step-up **O** |
| 4 | 1:50–2:30 | 10:30 | Finance → Owner | Chase late payers **N** → Customers **O** → owner confirms **N** |
| 5 | 2:30–3:05 | 14:00 | Finance | Can we pay everyone **N** → what-if scenario **O** |
| 6 | 3:05–3:35 | 15:00 | Employee | Voice request **N** refused by role **N** |
| 7 | 3:35–4:15 | 17:00 | Owner | Close the month **N** → e-Invoicing readiness **O** |
| 8 | 4:15–5:00 | 17:15 | Compliance | Agents & autonomy, kill switch **O** → audit chains **O** |

## 1. 08:00 — The morning briefing (0:00–0:25)

**Action:**
1. Play the Telegram clip for three seconds.
2. Cut to the Owner's **Today** page and hold the three cards (cash outlook, waiting
   for you, positions).
3. Open **Ask DuitDuit**, where the briefing sits above the chat.

**Narration:**

> Eight o'clock at a fictional Malaysian importer. The owner's briefing arrives
> on Telegram with ranges and counts only. The details are in DuitDuit: cash
> falls below the company's minimum in about three weeks, and the briefing
> lists what is waiting for the owner.

If the insert is an illustration, say "this labelled illustration shows the
briefing format" instead of "arrives".

## 2. 08:30 — Where the numbers come from (0:25–0:55)

**Action:**
1. Open **Data sources** and show the imported files with their mappings
   (bank, payables, payroll, sales).
2. Open **Cash & finance** and hold the opening balance, lowest likely point and
   gap cards.
3. Hold the shortfall banner, which names payroll and the Shenzhen supplier
   payment, and the best–worst range on the chart.

**Narration:**

> These numbers come from the company's own records. The bank, payables, payroll
> and sales files were imported with saved mappings, and names and amounts are
> protected before anything is searchable. The forecast shows the lowest likely
> balance, RM20,560, on the day payroll and a supplier payment land together.
> That is RM29,440 under the owner's minimum, and the worst case goes negative.

## 3. 09:00 — Prepare for the bank meeting (0:55–1:50)

**Action:**
1. Type **"Prepare me for the bank meeting"**.
2. Hold the pack's headline and its **Missing facts** step.
3. Click **Open Financing & Passport →** and scroll the **Credit scorecard** slowly.
   Point to "Not measured" on bank-line matching.
4. Show one **Financing match** with its rule-by-rule reasons.
5. Open the **Review inbox**, select **Bank meeting: review lender sharing** (L2)
   and approve it.
6. Back on Financing & Passport, issue a Passport and share it with the fictional
   lender for seven days, with exact values unchecked.
7. Complete the real authenticator check and show the issued link. Opening the
   lender view in a second tab is optional.

**Narration:**

> "Prepare me for the bank meeting." DuitDuit gathers the forecast, the financing
> facts and what is missing. The scorecard uses the same facts as the
> matches. Where we have no source, it says so and gives no points. Bank
> matching is "not measured", not a guess. Sharing with a lender is an L2
> action, so it waits in the inbox for the owner. Approving it creates no link:
> the owner chooses the lender and the expiry, and confirms with an authenticator
> code. This prepares a conversation with a lender. It is not a loan approval.

## 4. 10:30 — Chase the late payers (1:50–2:30)

**Action:**
1. In the Finance session, type **"Chase the late payers"**.
2. The headline reads that **no invoice is past due** and that customers have
   invoices due before the cash gap. Click **Review 2 drafts in the inbox →**.
3. Open **Customers** and show the same customers with their outstanding invoices,
   which are the rows the forecast uses.
4. Cut to the Owner session. In Ask DuitDuit, type **"approve the payment reminders"**.
5. Read the Confirm card's items and press **Confirm**.

**Narration:**

> Finance asks DuitDuit to chase late payers. Nobody is late yet, and DuitDuit
> says so. It drafts one polite request per customer whose invoice lands before
> the gap. The Customers page shows the same invoices the forecast counts on. The
> drafts are L2, so the owner approves them. Even a typed approval shows exactly
> which items it covers and waits for Confirm. Nothing has been sent.

## 5. 14:00 — Can we pay everyone? (2:30–3:05)

**Action:**
1. As Finance, type **"Can I pay everyone this month?"**.
2. Hold the headline ("Short by RM29,440.00 around day …") and the two
   illustrative options.
3. Click **Open Cash & finance →** and run the what-if that moves the early
   collections. Show the gap closing.

**Narration:**

> "Can I pay everyone this month?" The honest answer is no, not without action: the
> next 30 days fall RM29,440 under the minimum. Collecting one later
> invoice earlier closes it in this illustrative scenario. No receipt or payment
> date was changed.

## 6. 15:00 — An employee tries a payment command (3:05–3:35)

**Action:**
1. In the Employee (sales) session, click the microphone and say
   **"Approve all payments"**.
2. Show the transcript waiting in the box, then press **Send**.
3. Hold the refusal and its reason.

**Narration:**

> An employee tries "approve all payments" by voice. The transcript waits for
> them to send it, and speaking gives no extra authority. The request is refused
> because money items belong to finance and the owner, with a second checker and
> an authenticator code.

**Fallback:** show "Voice unavailable · typed request shown", type the same
request and narrate "the employee types the same request". Do not claim a
voice test.

## 7. 17:00 — Close the month honestly (3:35–4:15)

**Action:**
1. As Owner, type **"Close the month"**.
2. Hold the headline count ("1 of 4 checks done · 2 need you · 1 not measured").
3. Open **e-Invoicing → Readiness Check** and show the critical issues (missing
   supplier TIN, which MyInvois would reject).

**Narration:**

> At five, "close the month". Imports are current. Some e-invoices still need
> fixes before MyInvois accepts them, and some inbox items are open. Bank
> reconciliation is "not measured", so we do not pretend it is done. This is a
> checklist for the owner, not a statement that the books are closed.

## 8. 17:15 — Who watches the agents (4:15–5:00)

**Action:**
1. In the Compliance session, open **Agents & autonomy** and show the L0–L3 ladder
   and **Stop all agents**. Do not press it on camera unless you restart them.
2. Open **Trust & audit → Audit & access → Workflow events**. Show today's
   playbook, command and review-decision events by kind and id.
3. Press **Re-verify both chains** and hold the result.

**Narration:**

> Compliance closes the day. Each agent's autonomy is earned and capped, money is
> never delegated, and one switch stops them all. Every proposal, decision and
> share is on a hash chain by kind and id, never by the words people typed.
> DuitDuit prepares the work, and people make the decisions.

## Evidence and recording handoff

| Scene | Implementation and automated evidence |
| --- | --- |
| 1 | `app/services/briefing.py`, `briefing_push.py`, `components/BriefingCard.tsx`, `screens/Home.tsx` |
| 2 | `app/services/business_imports.py`, `cashflow_engine.py`, `screens/CashFlow.tsx`; evaluation F01 |
| 3 | `app/services/playbooks.py` (`bank_meeting`), `app/stubs/financing.py` (`scorecard`), `app/services/financing_profile.py`; `tests/test_cash_basis.py`, `tests/test_playbooks.py` |
| 4 | `playbooks.py` (`chase_late_payers`), `app/services/customer_intelligence.py`; `tests/test_ledger_customers.py` |
| 5 | `playbooks.py` (`pay_everyone`), the cash scenarios; `tests/test_playbooks.py` |
| 6 | `components/VoiceInput.tsx`, `app/services/assistant_voice.py`; evaluation tasks `A-trick-spoken`, `A-trick-typed` and `A-role-limits` |
| 7 | `playbooks.py` (`month_end`), `app/services/einvoice_readiness.py` |
| 8 | `screens/Autonomy.tsx`, `screens/Audit.tsx`; evaluation tasks `A-no-confirm` and `A-no-words-in-audit`, plus the chain tests |

Paths are relative to `backend/` (`app/`, `tests/`) and `frontend/src/`
(`components/`, `screens/`). For each scene, record whether it used the working
backend, a prerecorded insert or a fallback. Export MP4 (H.264). Provide a mirror
whose reachability from mainland China has actually been checked; none is produced
by this script.
