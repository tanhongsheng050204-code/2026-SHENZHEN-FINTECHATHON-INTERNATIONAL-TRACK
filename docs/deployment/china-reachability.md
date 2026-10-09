# China reachability

The judges are in mainland China, so every request the browser makes has to reach something that loads there.

## What the browser loads today

We loaded 9 pages of the app through a real browser on 2026-10-09, against the preview deployment carrying the production headers:
- every request went to the app's own origin;
- there were no Content Security Policy violations or console errors.

`frontend/scripts/check-web-hardening.mjs` runs in CI after every build and fails if:
- a source file, `public/` file or `index.html` loads anything from another origin;
- a required security header goes missing.

**What we removed to get there:**
- **Google Fonts** (blocked): fonts are bundled with the app (`@fontsource-variable`).
- **`api.qrserver.com`:** e-invoice QR codes are now drawn in the browser (`components/QrCode.tsx`). Before, every invoice UIN was sent to that service, which was also a privacy leak.
- **Direct backend calls from the browser:** the app calls `/api` on its own origin. The Vercel Edge proxy forwards to Cloud Run server-side, so the browser never contacts `run.app`.

## What can still fail, and what to do

| Dependency | Status from mainland China (GreatFire figures recorded in the design spec) | Action |
|---|---|---|
| `*.vercel.app` (the app itself) | Mostly blocked: 127 of 131 tested URLs | Serve the app from a custom domain. This is the main remaining risk. |
| `*.run.app` (the API) | Intermittent: 12 of 19 tested URLs disrupted | Reached only server-side through the proxy, so the browser is not affected. |
| `supabase.co` | Intermittent: 12 of 17 tested URLs disrupted | With `VITE_AUTH_MODE=supabase` (today's default), the browser signs in against Supabase directly. Switch to `VITE_AUTH_MODE=backend` once Plan 2 is deployed: then only the backend talks to Supabase. |
| Sentry (optional) | Not tested | Leave `VITE_SENTRY_DSN` unset for the judged deployment. The app works without it. |
| YouTube | Blocked | Submit the video as an MP4 file and mirror it on a host that loads in China, such as Bilibili. |
| Telegram | Blocked | Do not depend on a live Telegram moment in the demo. |

## How to test before submission

1. Run `https://en.greatfire.org/analyzer` on the final app URL and on the API URL, and record the results with their date.
2. Request the app URL and `/api/health` from mainland nodes using a China-based multi-node HTTP test site (for example 17ce.com or ping.chinaz.com), and record the success rate per region.
3. If anyone on the team can, open the app on a mainland network and sign in as the demo owner.
4. Put the results into the security self-assessment (section 8 and the evidence list).

If the app URL fails these tests, the demo video carries the evidence: make sure every claim in the deck also appears in it.
