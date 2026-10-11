# Setting up sign-in, email codes and the demo company

This guide is for the person who runs the DuitDuit backend and owns the Supabase project. It takes about 45 minutes and fixes these problems:

| What people see | Why | Part |
|---|---|---|
| The email has a "Confirm email address" link, not a 6-digit code | The Supabase email templates are still the defaults | 2 |
| No email arrives at all | Supabase's built-in mail sender sends very few emails, and may only deliver to your own Supabase team | 3 |
| The link says "Email link is invalid or has expired" | Links last about an hour, and DuitDuit uses codes, not links | 2 |
| Judges would have to create an account to see anything | The one-click demo company is not switched on | 5 |
| The site stops working when the tunnel restarts | A quick tunnel gets a new random address each time | 6 |

Do the parts in order. Each one ends with a check.

**Never paste a key, password or code into chat, a commit or a screenshot.** This guide only uses setting names.

---

## Part 0. What you need

- **Owner** or **Administrator** access to the Supabase project the backend uses (the project in `SUPABASE_URL` in `backend/.env`). A Developer role cannot change Auth settings.
- The computer that runs the backend, with the repository on it.
- A Gmail account to send the emails from, with **2-Step Verification** turned on. A dedicated account, such as `duitduit.noreply@gmail.com`, is best.
- About 45 minutes.

---

## Part 1. Update the code and restart

From the repository root:

```bash
git pull origin main
cd backend
uv sync
```

Then stop the backend and start it again the way you normally do.

New in this update:
- the demo company resets itself every day;
- each day's forecast is kept for the forecast check;
- the main screens can be shown in Chinese.

If you have never run them, also do steps 2 and 3 of [production-checklist.md](production-checklist.md): three migrations and the demo data seed.

**Check:** open `https://<your backend address>/health`. It shows `"status":"ok"` and `"database_reachable":true`.

---

## Part 2. Make every email carry a 6-digit code

DuitDuit asks for a code, never a link. Supabase puts the code in an email only if the template contains `{{ .Token }}`.

### 2.1 Site URL and redirect URLs

Supabase dashboard → **Authentication** → **URL Configuration**:

1. **Site URL:** `https://duitduit-umber.vercel.app` → **Save changes**.
2. **Redirect URLs** → **Add URL** → `https://duitduit-umber.vercel.app/**` → **Save URLs**.

(The Site URL already looks fixed: links now open the right site. Check it anyway.)

### 2.2 The four email templates

Supabase dashboard → **Authentication** → **Emails** → **Templates**. Each template has a **Subject** and a **Message body** (the body is HTML).

Change all four. They are used at different moments:

| Template | When DuitDuit sends it | Subject to use |
|---|---|---|
| **Confirm signup** | Someone creates a company | `Your DuitDuit code` |
| **Magic Link** | **Every sign-in**, after the password | `Your DuitDuit sign-in code` |
| **Invite user** | An owner invites a team member | `You're invited to DuitDuit` |
| **Reset password** | "Forgot password" | `Your DuitDuit reset code` |

For each one:
1. Open the template.
2. Replace the **Subject** with the one above.
3. Delete **everything** in the message body and paste this:

```html
<h2>Your DuitDuit code</h2>
<p>Enter this code in DuitDuit to continue:</p>
<p style="font-size:28px;font-weight:700;letter-spacing:4px">{{ .Token }}</p>
<p>It expires soon. If you did not ask for it, you can ignore this email.</p>
```

4. Press **Save changes** before opening the next template.

Keep `{{ .Token }}` exactly as written: two curly brackets, a space, a full stop, `Token`, a space, two curly brackets. Do not leave `{{ .ConfirmationURL }}` in the body, or the email will still show a link.

### 2.3 Email sign-in settings

Supabase dashboard → **Authentication** → **Sign In / Providers** → **Email**:

- **Enable Email provider:** on.
- **Confirm email:** on.
- **Email OTP length:** `6`. The app accepts 6 to 8 digits.
- **Email OTP expiration:** `600` seconds (10 minutes) is sensible. The default (3600) also works.

Press **Save**.

### 2.4 Authenticator apps

Supabase dashboard → **Authentication** → **Multi-Factor** (sometimes under **Sign In / Providers**):

- **TOTP (App Authenticator):** enabled.

Owners, finance and compliance users must set up an authenticator app (Google Authenticator, Microsoft Authenticator or similar) the first time they sign in.

**Check:** open **Magic Link** again. The body shows `{{ .Token }}` and no link.

---

## Part 3. Send the emails through Gmail

Supabase's built-in sender is for testing only:
- it sends only a handful of emails an hour for the whole project;
- it may refuse addresses that are not members of your Supabase organisation.

That is why codes are not arriving. Send them through Gmail instead.

### 3.1 Create a Gmail app password

1. Sign in to the Gmail account that will send the emails.
2. Open <https://myaccount.google.com/security>. Make sure **2-Step Verification** is **On**.
3. Open <https://myaccount.google.com/apppasswords>.
4. Name it `DuitDuit Supabase` and press **Create**.
5. Google shows a 16-character password once. Keep the window open for the next step, and do not save it anywhere else.

If the backend `.env` already has `EMAIL_SMTP_USERNAME` and `EMAIL_SMTP_PASSWORD` for this Gmail account, you can reuse that app password instead.

### 3.2 Point Supabase at Gmail

Supabase dashboard → **Authentication** → **Emails** → **SMTP Settings** → turn on **Enable custom SMTP**, and fill in:

| Field | Value |
|---|---|
| Sender email | The Gmail address |
| Sender name | `DuitDuit` |
| Host | `smtp.gmail.com` |
| Port number | `587` |
| Minimum interval between emails | `10` seconds (the default 60 also works) |
| Username | The full Gmail address |
| Password | The 16-character app password, without spaces |

Press **Save changes**.

### 3.3 Raise the email rate limit

Supabase dashboard → **Authentication** → **Rate Limits**:
- **Rate limit for sending emails:** `30` per hour (only possible once custom SMTP is on).
- Press **Save changes**.

Gmail allows about 500 emails a day from a normal account, which is plenty for judging.

**Check (most important):**
1. On <https://duitduit-umber.vercel.app>, press **Log in** → **Create a company**, with an email address you have **not** used before.
2. Within a minute the email arrives from your Gmail address. It shows a **6-digit code** and no link.
3. Type the code. The next screen asks you to set up an authenticator app.

If the email does not arrive, see **Part 8**.

---

## Part 4. A note on the earlier test account

The account the repository owner tried earlier was created while the templates still sent links. If it is stuck:

- Supabase dashboard → **Authentication** → **Users** → find the address → **⋯** → **Delete user**.
- Then they create the company again, and the new email carries a code.

Delete only that one test user, never the demo account from Part 5.

---

## Part 5. Switch on "Open the demo company" for judges

Judges should not need email at all. The demo button signs them in, in one click, as the owner of the synthetic company:
- the password and authenticator steps still happen, run by the server;
- nothing the demo does leaves the system (emails and Telegram messages are recorded, not sent);
- the company resets itself every day at 03:00 Malaysia time.

### 5.1 Create the demo account

Use an address on a domain you control. No email is sent to it. From `backend/`:

```bash
uv run python -m scripts.provision_demo_account --email demo-owner@<your-domain> --out demo-account.env
```

It prints a user id and the company id, and writes four settings to `demo-account.env`. Nothing secret is printed.

### 5.2 Add the settings and restart

1. Open `demo-account.env` and copy its four lines into `backend/.env`:
   - `DEMO_SIGN_IN_ENABLED`
   - `DEMO_EMAIL`
   - `DEMO_PASSWORD`
   - `DEMO_TOTP_SECRET`
2. Check these lines in `backend/.env` too:

   | Setting | Value |
   |---|---|
   | `CORS_ORIGINS` | `https://duitduit-umber.vercel.app` |
   | `ALERT_CHECKS_ENABLED` | `true` |
   | `CUSTOMER_INTELLIGENCE_ENABLED` | `true` |
   | `DEMO_DAILY_RESET` | `true` (or leave it out; true is the default) |

3. Delete `demo-account.env`.
4. Restart the backend.
5. Optional, just before judging starts, give the demo company a clean start:

   ```bash
   uv run python -m scripts.reset_demo_company
   ```

**Check:**
1. `https://<your backend address>/auth/demo/status` shows `{"available":true}`.
2. On the live site, **Log in** shows **Open the demo company** above the sign-in form.
3. Press it. Today opens, with the Demo authenticator in the lower-left corner.

---

## Part 6. Give the backend an address that never changes

The site reaches the backend through `BACKEND_ORIGIN` on Vercel. A quick tunnel (`*.trycloudflare.com`) gets a new random address every time it restarts, and the site breaks until the address is updated. Judging can last several days after Oct 20.

Choose one of these.

### Option A: a named Cloudflare tunnel (needs a domain on Cloudflare)

The domain's DNS must be on Cloudflare (a free account is enough).

```bash
cloudflared tunnel login
cloudflared tunnel create duitduit-api
cloudflared tunnel route dns duitduit-api api.<your-domain>
```

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: duitduit-api
credentials-file: <the .json path printed by "tunnel create">
ingress:
  - hostname: api.<your-domain>
    service: http://localhost:8000
  - service: http_status:404
```

Change `8000` if the backend listens on another port. Then:

```bash
cloudflared tunnel run duitduit-api
```

The address `https://api.<your-domain>` now stays the same after every restart. On Windows, `cloudflared service install` makes it start with the computer.

### Option B: Cloud Run

Follow [cloud-run-and-vercel.md](cloud-run-and-vercel.md). It needs a Google Cloud project with billing switched on. It keeps working when your computer is off, which matters while judging continues.

### Then

Send the new address (with no trailing slash) to the repository owner. They set it as `BACKEND_ORIGIN` on Vercel and redeploy.

**Check:** restart the tunnel (or redeploy Cloud Run). The live site still signs in without anyone changing `BACKEND_ORIGIN`.

---

## Part 7. Replace the exposed service key

The `SUPABASE_SERVICE_ROLE_KEY` appeared in a screenshot. That key can read and change every row, so replace it.

Supabase dashboard → **Project Settings** → **API Keys**:

- **If you see "Secret keys" (`sb_secret_…`):**
  1. Create a new secret key.
  2. Put it in `backend/.env` as `SUPABASE_SERVICE_ROLE_KEY`.
  3. Restart the backend.
  4. Delete the old secret key.
- **If you only have the legacy keys (`anon` and `service_role`):**
  1. Use **JWT Keys** → generate a new JWT secret. This replaces **both** keys.
  2. Copy the new `service_role` key into `SUPABASE_SERVICE_ROLE_KEY` and the new `anon` key into `SUPABASE_ANON_KEY`.
  3. Restart the backend.
  4. Everyone is signed out once. Nothing on Vercel changes, because only the backend holds these keys.

**Check:** `/health` is ok and you can still sign in.

---

## Part 8. If something still goes wrong

| What you see | What to check |
|---|---|
| No email arrives | **Authentication → Logs** in Supabase. "rate limit exceeded" → Part 3.3. "Email address not authorized" → custom SMTP is not on (Part 3.2). "535 Username and Password not accepted" → wrong app password, or 2-Step Verification is off. Also check the recipient's Spam folder. |
| Email arrives with a link, not a code | That template still has `{{ .ConfirmationURL }}`. Redo Part 2.2 for that template. |
| "Invalid or expired code" | Codes last the time set in Part 2.3. Press **Start over** and use the newest email only. |
| "Supabase Auth is not configured" | `SUPABASE_URL` or `SUPABASE_ANON_KEY` is missing from `backend/.env`. |
| "DuitDuit can't reach its server" | The backend or the tunnel is down, or `BACKEND_ORIGIN` on Vercel is out of date. |
| A sign-in error mentioning the origin | `CORS_ORIGINS` must be exactly `https://duitduit-umber.vercel.app`, with no trailing slash. |
| No **Open the demo company** button | `/auth/demo/status` says `false`: the `DEMO_*` lines are missing, or the backend was not restarted. |

Messages on screen never contain secrets, so a screenshot of the error is safe to send.

---

## Done: the five-minute check

When Parts 1 to 6 are done, tell the repository owner. They will run this on the live site:

1. **Open the demo company**.
2. Approve one inbox item.
3. Approve one money item with the demo authenticator's code.
4. Re-verify both audit chains.
5. Share a Passport and open it as a lender.
