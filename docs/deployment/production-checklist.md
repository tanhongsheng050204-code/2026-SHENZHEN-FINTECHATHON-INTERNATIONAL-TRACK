# Production checklist for the judged deployment

This is for the person who holds the production keys and runs the backend. Do the steps in order. Each step says how to check it worked.

You never need to paste a secret into chat, a commit or this file. The steps use only key names.

For a slower, click-by-click version of the sign-in, email, demo and tunnel steps, see [backend-owner-setup-guide.md](backend-owner-setup-guide.md).

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
| `DEMO_DAILY_RESET` | `true` (the default) | The demo company starts clean every day at 03:00, so each judge sees the same state |
| `AUTOMATIONS_ENABLED` | `true` (the default) | Automations set in Company settings are checked every 15 minutes |
| `CHAT_NOTIFICATIONS_ENABLED`, `CHAT_NOTIFY_TENANT_ID` | `true`, and the one company whose team chat gets the notices | Optional. Posts "N items wait for review" to Slack or WhatsApp |
| `SLACK_WEBHOOK_URL` | A Slack incoming-webhook address | Optional, for Slack |
| `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_RECIPIENT`, `WHATSAPP_TEMPLATE` | From a WhatsApp Business (Cloud API) account, with an approved template that has one body variable | Optional, for WhatsApp. Not tested against a live account |
| `ALERT_CHECKS_ENABLED` | `true` | Alert rules are checked every 15 minutes |
| `CUSTOMER_INTELLIGENCE_ENABLED` | `true` | The Customers page reads the sales ledger |
| `CORS_ORIGINS` | `https://duitduit-umber.vercel.app`, the app's exact address with no trailing slash. Add a custom domain here too once there is one, separated by a comma. | Cookie sign-in only works from listed origins |
| `AUTH_COOKIE_SECURE` | `true` (the default) | The session cookie is sent over HTTPS only |

Nothing in the demo company leaves the system, whatever `OUTBOUND_EMAIL_ENABLED` or `TELEGRAM_OUTBOUND_ENABLED` say:
- email and Telegram briefings, alerts and customer reminders are recorded as simulated and not sent;
- team invitations are refused.

Restart the API after changing these.

**Check:** `GET /auth/demo/status` returns `{"available": true}`.

## 6. Frontend (Vercel)

The frontend is already deployed at **https://duitduit-umber.vercel.app**, as the Vercel project `duitduit` on the repository owner's account. `VITE_AUTH_MODE` and `VITE_API_URL` are already set.

The only thing still missing is the API's address. **Send the backend's public HTTPS address (no trailing slash) to the repository owner.** They set it as `BACKEND_ORIGIN` and redeploy.

| Setting | Value |
|---|---|
| `VITE_AUTH_MODE` | `backend` (set) |
| `VITE_API_URL` | `/api` (set) |
| `BACKEND_ORIGIN` | The API's HTTPS address, with no trailing slash (**to set**) |

If the API runs through a tunnel, use an address that stays the same when the tunnel restarts, such as a named Cloudflare tunnel. A quick tunnel gets a new random address on every restart, and the site breaks each time.

`VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` are not needed in backend mode, because the browser never talks to Supabase.

Redeploy afterwards. `VITE_` settings are baked into the build, so changing them has no effect until the next build.

**Check:** open the site, then **Log in**. The **Open the demo company** card appears above the sign-in form.

## 6b. Supabase Auth settings (dashboard)

DuitDuit signs people in with **6-digit codes**, not email links. Supabase's defaults send a link that points at `http://localhost:3000`, so these settings must change. They are in the Supabase dashboard of the project the backend's `SUPABASE_URL` points to. They need an **Owner** or **Administrator** role in that organisation.

**1. Authentication → URL Configuration**
- **Site URL:** `https://duitduit-umber.vercel.app` → **Save changes**.
- **Redirect URLs → Add URL:** `https://duitduit-umber.vercel.app/**` → **Save**.

**2. Authentication → Emails → Templates.** Each of the four templates below must show the code `{{ .Token }}`. The backend checks that code with the matching type:

| Template | Used when | Suggested subject |
|---|---|---|
| Confirm signup | Someone creates a company | Your DuitDuit code |
| Magic Link | **Every sign-in**: the code after the password | Your DuitDuit sign-in code |
| Invite user | An owner invites a team member | You're invited to DuitDuit |
| Reset password | "Forgot password" | Your DuitDuit reset code |

Body for each (replace the whole message; keep `{{ .Token }}` exactly):

```html
<h2>Your DuitDuit code</h2>
<p>Enter this code in DuitDuit to continue:</p>
<p style="font-size:28px;font-weight:700;letter-spacing:4px">{{ .Token }}</p>
<p>It expires soon. If you did not ask for it, you can ignore this email.</p>
```

**3. Authentication → Sign In / Providers → Email**
- **Email provider:** enabled. **Confirm email:** on.
- **Email OTP length:** 6 (the app accepts 6 to 8 digits).

**4. Authentication → Multi-Factor**
- **TOTP (authenticator app):** enabled. Owners, finance and compliance must enrol one.

**5. Email delivery.** Supabase's built-in mail sender is for testing only. It sends very few emails an hour, and may only deliver to members of the Supabase organisation. For anyone else, set **Authentication → Emails → SMTP Settings** to a real mailbox. The Gmail SMTP details already in the backend `.env` (`EMAIL_SMTP_*`, with an app password) work: host `smtp.gmail.com`, port `587`.

**Check:** on the site, **Log in → Create a company** with a new address. The email shows a 6-digit code and no `localhost` link. Entering it moves on to the authenticator step.

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
- The demo company resets itself every day at 03:00 (the API's `APPLICATION_TIMEZONE`) while one-click demo is on:
  - stopped agents are switched back on;
  - settings return to the seeded version, as a new version;
  - decided inbox items wait for review again, and widened autonomy is withdrawn.
- Nothing is deleted. Each reset is a `demo_reset` event on the company's audit chain, and earlier decisions stay on the chain.
- To reset it now, for example just before judging starts: `python -m scripts.reset_demo_company` from `backend/`. It refuses any company except `DEMO_TENANT_ID`.
- Alert rules and lender or auditor links are not reset. Links end on their own when they expire.
- Run step 3 again if bank lines or bills look wrong.

## 9. Reachability from mainland China

Follow `china-reachability.md` ("How to test before submission") on the final app address, and record the date and results. `*.vercel.app` is mostly blocked there, so a custom domain is strongly recommended.

## Rollback

- **Frontend:** set `VITE_AUTH_MODE=supabase` and redeploy.
- **Demo:** set `DEMO_SIGN_IN_ENABLED=false` and restart the API. The demo account stays, but nobody can use one-click sign-in.
- **Migrations:** these three only add policies, a table and an allowed value. None needs rolling back for the app to work on older code.
