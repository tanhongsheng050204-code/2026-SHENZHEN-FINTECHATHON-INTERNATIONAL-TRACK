# Plan 9 — Web hardening and China reachability

**Implemented:** 2026-10-09.

## Delivered

**Security headers** (`frontend/vercel.json`, on every response):
- Content Security Policy: scripts only from the app itself, no inline script or `eval`, connections only to the app, Supabase and Sentry, `frame-ancestors 'none'`, `object-src 'none'`, `upgrade-insecure-requests`;
- HSTS (two years);
- `X-Content-Type-Options: nosniff`;
- Referrer-Policy;
- Permissions-Policy (camera, microphone, geolocation, payment and USB all off);
- `X-Frame-Options: DENY`.

**Search hygiene:**
- `X-Robots-Tag: noindex, nofollow` on every path except the landing, security and legal pages and the robots, sitemap and `.well-known` files;
- `robots.txt` and `sitemap.xml` listing only those pages;
- a browser-tab title per page.

**Vulnerability reporting:**
- `/.well-known/security.txt` (RFC 9116);
- `SECURITY.md` rewritten from GitHub's placeholder template into a real policy.

**No third-party loads:**
- e-invoice QR codes are drawn in the browser (`components/QrCode.tsx`, MIT-licensed `qrcode-generator`). Before, every invoice UIN was sent to `api.qrserver.com`.
- Fonts were already bundled.

**Rate limit:** the public Passport verify and share-link endpoints allow 30 requests a minute per client address, then return 429 with `Retry-After` (`backend/app/security/rate_limit.py`).

**CI guard:** `frontend/scripts/check-web-hardening.mjs` fails the build if a required header is missing, if `script-src` allows inline or `eval`, or if any source, public file or `index.html` loads from another origin. Run against the previous `main`, it fails, which shows the check works.

**Text:** meta and Open Graph descriptions rewritten for the SME finance copilot positioning.

**Runbook:** [`docs/deployment/china-reachability.md`](../../deployment/china-reachability.md).

## Evidence

**On the preview deployment** (`finbrain-topic-e-preview.vercel.app`), carrying the same headers:
- `curl` shows every header on app routes;
- the landing page has no `X-Robots-Tag`;
- `security.txt` and `robots.txt` are served.

**In a real browser:** across 9 pages, there were no Content Security Policy violations or console errors, and every request went to the app's own origin. The same check passed locally across 20 pages, and the locally drawn QR code renders on the e-invoice detail page.

**Tests:**
- Backend: 434 tests pass, including the rate-limit test.
- Frontend: clean install, typecheck and build pass; lint shows 0 errors (14 warnings were already there).

## Not done

| Item | Owner |
|---|---|
| Custom domain for the app: `vercel.app` is mostly blocked in mainland China, the biggest remaining risk | Team |
| GreatFire and mainland multi-node tests on the final URLs | Team |
| Backend sign-in mode (`VITE_AUTH_MODE=backend`) after Plan 2 deploys, so the browser never calls Supabase | Team |
| Private vulnerability reporting on the GitHub repo, so the `security.txt` contact works | Repo owner (currently off) |
| A new Open Graph image for the new positioning | Optional |
