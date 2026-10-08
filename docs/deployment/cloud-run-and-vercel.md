# Deploying without a custom domain: Cloud Run + Vercel

For whoever deploys the backend and the frontend. No domain name is needed.

```text
browser ──► https://finbrainos.vercel.app            (React app)
        └─► https://finbrainos.vercel.app/api/...   (Vercel Edge proxy, frontend/api/proxy.js)
                       └─► https://finbrain-api-xxxx.a.run.app/...   (FastAPI on Cloud Run)
```

**Why the proxy.** The Plan 2 backend keeps the session in an HttpOnly cookie. Browsers only send that cookie when the API is on the same site as the app. `vercel.app` and `run.app` (or a `trycloudflare.com` quick tunnel) are different sites, so sign-in would silently fail. The proxy makes the API same-origin: the browser only ever talks to `finbrainos.vercel.app`.

**Why Cloud Run instead of the quick tunnel.** A quick tunnel gets a new random address every time it restarts, which breaks the app until it is rebuilt. Cloud Run gives a fixed HTTPS address at no extra cost.

---

## 1. Backend on Cloud Run

Run from the repository root (where `Dockerfile` is). Replace `PROJECT_ID`; `asia-southeast1` (Singapore) is closest to Malaysia.

```bash
gcloud config set project PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

gcloud artifacts repositories create finbrain --repository-format=docker --location=asia-southeast1

# Build the image in Google Cloud (no local Docker needed).
gcloud builds submit --tag asia-southeast1-docker.pkg.dev/PROJECT_ID/finbrain/backend:latest .
```

Store secrets in Secret Manager once (repeat for each name; paste the value when prompted):

```bash
for name in TOKEN_ROOT_SECRET TOKEN_HASH_SECRET VAULT_MASTER_KEY DATABASE_URL \
            SUPABASE_SERVICE_ROLE_KEY SUPABASE_ANON_KEY GEMINI_API_KEY; do
  printf "Value for $name: "; read -rs value; echo
  printf "%s" "$value" | gcloud secrets create "$name" --data-file=- --replication-policy=automatic
done
```

Deploy:

```bash
gcloud run deploy finbrain-api \
  --image asia-southeast1-docker.pkg.dev/PROJECT_ID/finbrain/backend:latest \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --port 8000 \
  --memory 2Gi --cpu 2 \
  --min-instances 1 --max-instances 1 \
  --no-cpu-throttling \
  --timeout 3600 \
  --set-secrets TOKEN_ROOT_SECRET=TOKEN_ROOT_SECRET:latest,TOKEN_HASH_SECRET=TOKEN_HASH_SECRET:latest,VAULT_MASTER_KEY=VAULT_MASTER_KEY:latest,DATABASE_URL=DATABASE_URL:latest,SUPABASE_SERVICE_ROLE_KEY=SUPABASE_SERVICE_ROLE_KEY:latest,SUPABASE_ANON_KEY=SUPABASE_ANON_KEY:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest \
  --set-env-vars "^@^CORS_ORIGINS=https://finbrainos.vercel.app@AUTH_COOKIE_SECURE=true@SUPABASE_URL=https://PROJECT_REF.supabase.co@APPLICATION_TIMEZONE=Asia/Kuala_Lumpur"
```

Then add every other non-secret setting your current `backend/.env` uses (Supabase JWT issuer/audience, model names, connector flags) with `gcloud run services update finbrain-api --region asia-southeast1 --update-env-vars KEY=value`.

Notes on the flags:

| Flag | Why |
| --- | --- |
| `--min-instances 1 --no-cpu-throttling` | The container also runs background workers (Telegram, email, vault rotation, recommendations). They need an always-on CPU. Without them you may use `--min-instances 0` and save cost, at the price of cold starts. |
| `--max-instances 1` | Only **one** Telegram poller may run per bot token. Raise it only when `TELEGRAM_BOT_TOKEN` is unset and workers run elsewhere. |
| `--memory 2Gi --cpu 2` | GLiNER personal-data detection runs on CPU and needs the memory. |
| `--timeout 3600` | Agent-run event streams stay open longer than the 5-minute default. |
| `CORS_ORIGINS` | The exact app origin, no trailing slash. The backend also checks the `Origin` of every change against it. Do not use `CORS_ORIGIN_REGEX` with cookie sessions. |
| `AUTH_COOKIE_SECURE=true` | Session cookies only over HTTPS. |

Check it: `curl https://finbrain-api-xxxx.a.run.app/health` should return `"status":"ok"`.

Apply database migrations (`supabase/migrations/`) to the production database before the new image serves traffic.

## 2. Frontend on Vercel

Project root: `frontend/` (its `vercel.json` defines the build, the `/api` rewrite and the SPA fallback).

Environment variables in the Vercel project:

| Name | Value | When it is read |
| --- | --- | --- |
| `BACKEND_ORIGIN` | `https://finbrain-api-xxxx.a.run.app` (no trailing slash) | At request time by the proxy |
| `VITE_API_URL` | `/api` | At build time |
| `VITE_AUTH_MODE` | `supabase` today; `backend` once Plan 2 is deployed and tested | At build time |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` | Only needed while `VITE_AUTH_MODE=supabase` | At build time |

Redeploy after changing any `VITE_` variable (they are baked into the build). `BACKEND_ORIGIN` changes apply on the next deployment too.

Check it:

```bash
curl https://finbrainos.vercel.app/api/health          # backend health through the proxy
curl -i https://finbrainos.vercel.app/api/review-inbox # 401 authentication_required when signed out
```

## 3. Supabase

- Authentication → URL configuration: set the Site URL and add `https://finbrainos.vercel.app` to the redirect URLs.
- For backend sign-in (Plan 2): email templates must send a **code** (`{{ .Token }}`), not a link; configure custom SMTP so codes arrive reliably.

## 4. Switching to backend sign-in

1. Deploy the Plan 2 backend and run its end-to-end checks (sign-up, email code, authenticator, step-up, sign-out).
2. In Vercel set `VITE_AUTH_MODE=backend` and redeploy.
3. On Cloud Run keep `AUTH_ALLOW_BEARER=false` (the default) once no client uses the old browser sign-in.

Rollback: set `VITE_AUTH_MODE=supabase` and redeploy the frontend; set `AUTH_ALLOW_BEARER=true` on Cloud Run while the old sign-in is in use.

## 4b. One demo company

The Topic E pages and the original pages must read the same tenant, or the demo shows two companies. After the backend is deployed:

1. `python -m seed.topic_e` creates the synthetic tenant and prints its `tenant_id`.
2. `python -m seed.topic_e_original_fixtures --tenant-id <that id>` adds the original pages' e-invoices (buyer renamed to the synthetic company) and the protected email/Telegram records to the same tenant. It refuses any tenant whose slug does not start with `synthetic-`, and running it twice adds nothing.
3. Give the demo accounts a role in that tenant and point their sign-in at it (the `tenant_id` claim for Supabase sign-in, or the session's tenant for backend sign-in).

## 5. What was verified

- The proxy forwards method, path, query, body, cookies, CSRF token and `Origin`; returns every `Set-Cookie` separately; refuses `..`, percent-escapes and absolute URLs; and streams server-sent events without buffering (local test against a fake backend).
- On a throwaway Vercel deployment pointed at the live backend, `/api/health` returned the backend's health, a signed-out `/api/review-inbox` returned `401 authentication_required`, app routes still served the SPA, and a traversal path returned `400 invalid_path`. The throwaway project was then deleted.
- Not yet verified on Vercel: a long agent-run stream end to end, and the Cloud Run deployment itself.

## 6. Mainland China

`vercel.app` and `run.app` are both unreliable from mainland China. Fonts are bundled and no Google services load in the browser, but the hosts themselves may be blocked. If judges must open the app from China without a VPN, the next step is a domain behind Cloudflare (named tunnel or proxy).
