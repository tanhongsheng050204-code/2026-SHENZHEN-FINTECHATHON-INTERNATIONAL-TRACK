# Production checklist for the judged deployment

This is for the person who holds the production keys and runs the backend. Do the steps in order. Each step says how to check it worked.

You never need to paste a secret into chat, a commit or this file. The steps use only key names.

## 1. Update the code

From the repository root:

```bash
git pull origin main
cd backend && uv sync
```

## 2. Apply the three new migrations

Try each one with `--dry-run` first, then run it for real:

```bash
cd backend
python -m scripts.apply_migration ../supabase/migrations/202610100001_mask_contacts_for_employees.sql --dry-run
python -m scripts.apply_migration ../supabase/migrations/202610100001_mask_contacts_for_employees.sql
python -m scripts.apply_migration ../supabase/migrations/202610100002_shared_rate_limits.sql --dry-run
python -m scripts.apply_migration ../supabase/migrations/202610100002_shared_rate_limits.sql
python -m scripts.apply_migration ../supabase/migrations/202610100003_sales_pipeline_paid_stage.sql --dry-run
python -m scripts.apply_migration ../supabase/migrations/202610100003_sales_pipeline_paid_stage.sql
```

| Migration | What it does |
|---|---|
| `…0001` | Employees no longer see customer email addresses or phone numbers |
| `…0002` | Rate limits are shared between API processes |
| `…0003` | The sales pipeline can record a paid stage |

**Check:** each run ends without an error. If a dry run fails, stop and send the error message, which contains no secrets.

## 3. Refresh the synthetic demo company

Both seeds are safe to run again. Neither deletes anything.

```bash
python -m seed.topic_e --allow-postgres
python -m seed.topic_e_original_fixtures --tenant-id 858f0c1c-42fa-52a2-91b3-80a19d816356
```

**Check:** the Financial analysis tab shows September revenue of RM249,400. Close the month shows 9 of 10 bank lines matched.

## 4. Create the shared demo account for judges

Use an address on a domain you control. No email is sent to it.

```bash
python -m scripts.provision_demo_account --email demo-owner@<your-domain> --out demo-account.env
```

This does three things:
- creates a confirmed sign-in for that address, with a long random password;
- makes it the owner of the synthetic company only;
- enrols an authenticator and checks one code.

The four settings go into `demo-account.env`, and nothing secret is printed.

**Check:** the command prints the new user id and the company id.

Copy the four lines into the API's environment (step 5), then delete `demo-account.env`.

## 5. API environment

| Setting | Value | Why |
|---|---|---|
| `DEMO_SIGN_IN_ENABLED`, `DEMO_EMAIL`, `DEMO_PASSWORD`, `DEMO_TOTP_SECRET` | From `demo-account.env` | Turns on **Open the demo company** |
| `ALERT_CHECKS_ENABLED` | `true` | Alert rules are checked every 15 minutes |
| `CUSTOMER_INTELLIGENCE_ENABLED` | `true` | The Customers page reads the sales ledger |
| `CORS_ORIGINS` | The app's exact address, e.g. `https://<app-domain>` | Cookie sign-in only works from listed origins |
| `AUTH_COOKIE_SECURE` | `true` (the default) | The session cookie is sent over HTTPS only |

Nothing in the demo company leaves the system, whatever `OUTBOUND_EMAIL_ENABLED` or `TELEGRAM_OUTBOUND_ENABLED` say:
- email and Telegram briefings, alerts and customer reminders are recorded as simulated and not sent;
- team invitations are refused.

Restart the API after changing these.

**Check:** `GET /auth/demo/status` returns `{"available": true}`.

## 6. Frontend (Vercel)

| Setting | Value |
|---|---|
| `VITE_AUTH_MODE` | `backend` |
| `VITE_API_URL` | `/api` |
| `BACKEND_ORIGIN` | The API's HTTPS address, with no trailing slash |

`VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` are not needed in backend mode, because the browser never talks to Supabase.

Redeploy afterwards. `VITE_` settings are baked into the build, so changing them has no effect until the next build.

**Check:** open the site, then **Log in**. The **Open the demo company** card appears above the sign-in form.

## 7. End-to-end check (five minutes)

1. Press **Open the demo company**. Today opens, with the Demo authenticator in the lower-left corner.
2. Open **Review inbox** and approve one L2 item.
3. Approve one L3 (money) item. When asked for a code, type the one shown by the Demo authenticator.
4. Open **Trust & audit** and press **Re-verify both chains**. Both should say intact.
5. Open **Financing & Passport**, share a Passport with `lender@bank.example` for 7 days, and open the link in a private window. The lender view loads without signing in. **Verify this Passport** says Verified.

If any step fails, note the step number and the message on screen. Messages never contain secrets.

## 8. Keep it running through judging

- Judging may continue for days after Oct 20. A home tunnel only works while that computer is on.
- If you can, move the API to Cloud Run (see `cloud-run-and-vercel.md`).
- The demo company is not reset automatically. To tidy it after many visitors:
  - turn any stopped agents back on in **Agents & autonomy**;
  - restore settings in **Company settings**, using version history.
- Run step 3 again if bank lines or bills look wrong.

## 9. Reachability from mainland China

Follow `china-reachability.md` ("How to test before submission") on the final app address, and record the date and results. `*.vercel.app` is mostly blocked there, so a custom domain is strongly recommended.

## Rollback

- **Frontend:** set `VITE_AUTH_MODE=supabase` and redeploy.
- **Demo:** set `DEMO_SIGN_IN_ENABLED=false` and restart the API. The demo account stays, but nobody can use one-click sign-in.
- **Migrations:** these three only add policies, a table and an allowed value. None needs rolling back for the app to work on older code.
