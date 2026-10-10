# Handoff for Codex: industrial-standard UI and sourced financing products (Oct 11, 2026)

Read `AGENTS.md` first. Its house rules apply to every line below.

Claude is working on other parts at the same time, in the `C:/Users/tanho/fba` worktree. Stay inside the files listed under **Yours** so the two of you don't collide.

## Progress (update this before starting a task)

Claude finished M1–M3 overnight and is now working through C1–C5 **in order** on `main`, because Codex had not started yet. Before you begin:
- read this table;
- `git pull`;
- take the first task that is **not** marked done or in progress;
- mark it "Codex: in progress", then commit and push that one line so Claude skips it.

| Task | Status |
|---|---|
| C1 Mobile | Claude: done (no sideways scroll on 18 signed-in screens at 375px; 44px targets) |
| C2 Accessibility | Claude: in progress |
| C3 Screen states | open |
| C4 Sourced financing | open |
| C5 中文 strings | open |

## Setup

Work in the main project folder on a new branch cut from `main`:

```
git fetch origin
git switch -c codex/industrial-ui origin/main
```

- Commit as the configured git user, with no co-author trailer.
- Push only your branch: `git push -u origin codex/industrial-ui`.
- Claude merges it into `main` after checking it. Don't push to `main` yourself.
- Don't touch the untracked `output/` files in that folder; they belong to someone else.

## Who owns what

**Yours (Codex):**
- `frontend/src/styles.css`
- every screen in `frontend/src/screens/` **except** `Login.tsx`, `Signup.tsx`, `Landing.tsx` and `SharedView.tsx`
- `frontend/src/components/` **except** `AuthFlow.tsx`, `AuthStory.tsx`, `Logo.tsx` and `RunwayFilm.tsx`
- `frontend/src/lib/i18n.tsx`
- `backend/app/stubs/financing.py` and its tests

**Claude's (don't edit):**
- the four sign-in screens and `Landing.tsx`
- `frontend/src/auth/`, `frontend/src/api/session.ts` and `backend/app/routes/auth.py`
- `backend/app/config.py`
- `.github/workflows/`
- everything under `docs/submission/` and `docs/deployment/`
- the deck

If one of your tasks really needs a change in a file Claude owns, describe the change in your final report instead of making it.

## Tasks, in order

The feature freeze is **Oct 16**. If time runs short, cut from the bottom of this list.

### C1. The signed-in app works on a phone (target Oct 12)

SME owners use their phones. The landing page is already responsive, but the signed-in app has not been checked at phone width.

1. Run the app locally at a 375 × 812 viewport. Use the stub sign-in described in "Running it locally" below.
2. Check these screens: Today (`Home.tsx`), Cash flow, Analysis, Financing, Review inbox, Approvals, Customers, Trust, Settings and Company settings.
3. Fix each of these wherever it happens:
   - horizontal page scroll;
   - clipped tables (wrap them in a scroll container with a visible edge, or switch to stacked rows);
   - buttons smaller than 44 × 44 px;
   - the sidebar covering content (`Nav.tsx` should collapse to a menu button below 768 px);
   - text under 14 px.
4. Save before-and-after screenshots of each screen to `output/industrial-ui/mobile/`. Don't commit them; `output/` stays untracked.

**Done when:** no screen scrolls sideways at 375 px, and every screen above can be used with a thumb.

### C2. Accessibility pass with a measured score (target Oct 13)

1. Run Lighthouse's accessibility audit (Chrome DevTools, or `npx lighthouse --only-categories=accessibility`) on Landing, Login, Today, Cash flow, Financing and Review inbox, in light mode and in dark mode.
2. Fix what it reports. Expect:
   - text contrast below WCAG AA (4.5:1 for body text);
   - icon buttons without an accessible name;
   - form inputs without labels;
   - missing focus outlines;
   - charts with no text alternative (give each chart a short `aria-label` that states the key number, e.g. "Lowest balance RM20,560 on day 23").
3. Make sure every interactive element can be reached and used with the keyboard alone, and that `Esc` closes modals and the Ask drawer.
4. Record the scores before and after in a table in `docs/handoff/codex-c2-accessibility-results.md`. Claude will copy them into the submission evidence. **Report the measured numbers, never estimates.**

**Done when:** every listed page scores at least 95, or the file explains what remains and why.

### C3. Empty, error and loading states on every screen (target Oct 14)

A judge must never see a blank screen or a raw error.

1. For each screen under "Yours", check three cases:
   - **Loading:** show a skeleton or quiet placeholder, not a spinner that shifts the layout.
   - **Empty:** use `EmptyState` with one sentence saying what to do next. For example: "No bank lines yet. Import a bank statement CSV in Imports."
   - **Error:** one sentence saying what happened and what to do, using `friendlyLoadError` from `api/client.ts`. Never show stack traces, HTTP codes or raw messages.
2. Add one app-wide banner for when the API can't be reached at all, with a "Try again" button. Put it in `App.tsx` or `Nav.tsx`, whichever already wraps the signed-in screens. It should say: "DuitDuit can't reach its server right now. Your data is safe. Try again in a moment."
3. Test the error case by stopping the backend while the frontend runs.

**Done when:** with the backend stopped, every signed-in screen shows the banner or a friendly error and nothing breaks.

### C4. Financing products modelled on public Malaysian schemes (target Oct 14)

The lender products in `backend/app/stubs/financing.py` are labelled synthetic. Keep them synthetic, but base each one on a **publicly documented** Malaysian SME scheme so that matching looks real. Candidates:
- SJPP (Syarikat Jaminan Pembiayaan Perniagaan) government guarantee schemes;
- Bank Negara Malaysia funds for SMEs (e.g. the All Economic Sectors Facility, the High Tech and Green Facility);
- CGC (Credit Guarantee Corporation) schemes;
- invoice financing as offered by licensed P2P / ECF platforms under the Securities Commission.

Rules:
1. Each product gets a `source_url` and a `source_checked_on` date for the public page you used. Show them in the Financing screen as a small "Based on: <scheme name>" link.
2. **Copy only facts the page states**, such as the maximum amount, tenure, guarantee coverage and eligibility (for example "Malaysian-owned SME, at least 6 months trading"). Where a page gives no rate or amount, leave that field out or show "Set by each lender". Never invent a number.
3. Keep the "Synthetic demo product" label on every card. The point is that the shape of each product is real; DuitDuit has no partnership with these bodies, so nothing may suggest one.
4. Keep the existing matching logic and the scorecard (605, grade C) unless a scheme's eligibility rule really changes who matches. If it does, update the tests and note it in your report.
5. Add tests:
   - every product has a `source_url` and a `source_checked_on` date;
   - no product claims a rate or amount its source doesn't state (a field the source doesn't give is `None`).

**Done when:** the Financing screen shows sourced products, and the backend suite passes.

### C5. Fill in the missing 中文 strings (target Oct 15, cut first)

1. In `frontend/src/lib/i18n.tsx`, list every key that has English but no `zh` value, or still has an English placeholder as its `zh` value.
2. Fill in the `zh` values for the screens shown in the demo: Today, Cash flow, Financing, Analysis, Review inbox and the Ask drawer.
3. Use plain Simplified Chinese suitable for a small-business owner. Keep financial terms standard: 现金流, 应收账款, 融资, 毛利率.
4. **These strings ship only after a person who reads Chinese well has checked them.** Put a list of every string you added in `docs/handoff/codex-c5-zh-strings-for-review.md`, as English on one side and Chinese on the other, so the reviewer can check them quickly.

## Running it locally

Use the commands in `docs/handoff/2026-10-10-assistant-remaining-work.md` under "Checks". You can look at signed-in screens without Supabase: `VITE_AUTH_MODE=backend` with a local backend works, or use the demo sign-in once Claude lands it on `main` (task M1 below).

## Before you report done

Run all of these. Every one must pass:

```
cd backend && python -m ruff check . && python -m pytest -p no:cacheprovider -W ignore
cd backend && python -m eval.run
cd frontend && npx tsc -b && npm run build && npm run lint && node scripts/check-web-hardening.mjs
```

Then:
1. Push your branch.
2. Add a short "Codex report" section at the bottom of this file. List what's done, what's not, any file outside your area that you needed changed, and the measured results.
3. Push that change too.

## What Claude is doing at the same time (for context only)

- **M1.** A one-click "Try the demo company" sign-in through the backend. Outward actions are recorded as simulated, and the demo company resets every night.
- **M2.** Security evidence: dependency scans in CI, an OWASP ZAP baseline scan and a threat model.
- **M3.** The deck's WeBank slide, demo video script updates and subtitle draft, and the production checklist for the backend owner.
