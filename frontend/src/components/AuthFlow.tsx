import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useAuth } from "../auth/AuthProvider";
import {
  challengeTotp,
  enrollTotp,
  listFactors,
  sessionMessage,
  setPassword,
  setupCompany,
  signUpWithPassword,
  startInvitation,
  startRecovery,
  verifyEmailCode,
  verifyTotp,
  type SessionResponse,
  type TotpEnrollment,
} from "../api/session";

export type AuthFlowMode = "signin" | "signup" | "recovery" | "invitation";

const MIN_PASSWORD = 12;

function slugFrom(name: string): string {
  return name.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="fb-mkt-field">{label}{children}</label>;
}

/**
 * Every step of backend sign-in: password, the emailed code, the authenticator
 * app (set up on first sign-in) and, for a new owner, the company. The server
 * decides the next step; this component only renders it.
 */
export function AuthFlow({ mode, onModeChange }: { mode: AuthFlowMode; onModeChange: (mode: AuthFlowMode) => void }) {
  const { session, signIn, applySession } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPasswordValue] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [enrollment, setEnrollment] = useState<TotpEnrollment | null>(null);
  const [factorId, setFactorId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const state = session?.state ?? "start";

  // Entering an authenticator step: enrol a new factor or find the existing one.
  useEffect(() => {
    let active = true;
    if (state === "mfa_enrollment_required" && !enrollment) {
      enrollTotp()
        .then((e) => { if (active) { setEnrollment(e); setFactorId(e.factor_id); } })
        .catch((e: Error) => active && setError(sessionMessage(e.message)));
    }
    if (state === "mfa_required" && !factorId) {
      listFactors()
        .then((factors) => {
          const verified = factors.find((f) => f.status === "verified") ?? factors[0];
          if (active) {
            if (verified) setFactorId(verified.id);
            else setError("No authenticator app is set up for this account. Contact your company owner.");
          }
        })
        .catch((e: Error) => active && setError(sessionMessage(e.message)));
    }
    return () => { active = false; };
  }, [state, enrollment, factorId]);

  const run = async (work: () => Promise<SessionResponse | void>) => {
    setBusy(true);
    setError(null);
    try {
      const next = await work();
      if (next) await applySession(next);
      setCode("");
    } catch (e) {
      setError(e instanceof Error ? sessionMessage(e.message, e.message) : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    switch (state) {
      case "start":
        if (mode === "signin") return void run(() => signIn(email.trim(), password));
        if (mode === "signup") {
          if (password.length < MIN_PASSWORD) return setError(`Use at least ${MIN_PASSWORD} characters.`);
          if (password !== confirm) return setError("The two passwords don't match.");
          return void run(() => signUpWithPassword(email.trim(), password));
        }
        return void run(() => (mode === "recovery" ? startRecovery(email.trim()) : startInvitation(email.trim())));
      case "email_code_required":
        return void run(() => verifyEmailCode(code.trim()));
      case "password_required":
        if (password.length < MIN_PASSWORD) return setError(`Use at least ${MIN_PASSWORD} characters.`);
        if (password !== confirm) return setError("The two passwords don't match.");
        return void run(() => setPassword(password));
      case "mfa_enrollment_required":
      case "mfa_required":
        if (!factorId) return;
        return void run(async () => verifyTotp(factorId, await challengeTotp(factorId), code.trim()));
      case "company_setup_required":
        return void run(() => setupCompany(companyName.trim(), slugFrom(companyName)));
    }
  };

  const heading: Record<string, [string, string]> = {
    start: {
      signin: ["Welcome back", "Sign in to your workspace"],
      signup: ["Create your company", "Start with the owner account"],
      recovery: ["Forgot your password?", "We'll email you a code"],
      invitation: ["You were invited", "Accept your invitation"],
    }[mode] as [string, string],
    email_code_required: ["Check your email", "Enter the code we sent"],
    password_required: ["Almost there", "Choose a password"],
    mfa_enrollment_required: ["Protect your account", "Set up your authenticator app"],
    mfa_required: ["Two-step sign-in", "Enter your authenticator code"],
    company_setup_required: ["Last step", "Name your company"],
    authenticated: ["Signed in", "Opening your workspace…"],
  };
  const [eyebrow, title] = heading[state] ?? heading.start;

  return (
    <form className="fb-mkt-auth-form" onSubmit={submit}>
      <div className="fb-mkt-eyebrow is-plain">{eyebrow}</div>
      <h2>{title}</h2>
      <div className="fb-mkt-auth-fields">
        {state === "start" && (
          <>
            <Field label="Email">
              <input className="fb-mkt-input" type="email" autoComplete="username" autoFocus required value={email} onChange={(e) => setEmail(e.target.value)} />
            </Field>
            {(mode === "signin" || mode === "signup") && (
              <Field label="Password">
                <input className="fb-mkt-input" type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"} required minLength={mode === "signup" ? MIN_PASSWORD : 1} value={password} onChange={(e) => setPasswordValue(e.target.value)} />
              </Field>
            )}
            {mode === "signup" && (
              <Field label="Confirm password">
                <input className="fb-mkt-input" type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
              </Field>
            )}
          </>
        )}

        {state === "email_code_required" && (
          <>
            <p className="fb-mkt-fine">We emailed you a sign-in code. It expires in a few minutes.</p>
            <Field label="Email code">
              <input className="fb-mkt-input fb-auth-code" inputMode="numeric" autoComplete="one-time-code" pattern="\d{6,8}" maxLength={8} autoFocus required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
            </Field>
          </>
        )}

        {state === "password_required" && (
          <>
            <Field label="New password">
              <input className="fb-mkt-input" type="password" autoComplete="new-password" required minLength={MIN_PASSWORD} value={password} onChange={(e) => setPasswordValue(e.target.value)} />
            </Field>
            <Field label="Confirm password">
              <input className="fb-mkt-input" type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </Field>
            <p className="fb-mkt-fine">At least {MIN_PASSWORD} characters. Changing it signs you out everywhere else.</p>
          </>
        )}

        {state === "mfa_enrollment_required" && (
          <>
            <p className="fb-mkt-fine">Owners, finance and compliance must use an authenticator app such as Google Authenticator or Microsoft Authenticator. Scan this code, then enter the 6-digit code it shows.</p>
            {enrollment ? (
              <div className="fb-auth-qr">
                <img src={enrollment.qr_code} alt="QR code to add FinBrain to your authenticator app" width={180} height={180} />
                <span className="fb-mkt-fine">Can't scan? Enter this key: <code>{enrollment.secret}</code></span>
              </div>
            ) : (
              <p className="fb-mkt-fine">Preparing your code…</p>
            )}
          </>
        )}

        {(state === "mfa_enrollment_required" || state === "mfa_required") && (
          <Field label="6-digit code">
            <input className="fb-mkt-input fb-auth-code" inputMode="numeric" autoComplete="one-time-code" pattern="\d{6}" maxLength={6} autoFocus required value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
          </Field>
        )}

        {state === "company_setup_required" && (
          <>
            <Field label="Company name">
              <input className="fb-mkt-input" autoFocus required maxLength={120} value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
            </Field>
            {companyName && <p className="fb-mkt-fine">Workspace address: <code>{slugFrom(companyName) || "—"}</code></p>}
            <p className="fb-mkt-fine">You start as the owner with trading-company defaults. You can change everything in Company settings.</p>
          </>
        )}

        {error && <div className="fb-mkt-callout" role="alert">{error}</div>}
      </div>

      {state !== "authenticated" && (
        <button className="fb-mkt-btn is-accent is-lg fb-auth-submit" type="submit" disabled={busy || (state.startsWith("mfa") && !factorId)}>
          {busy && <span className="fb-mkt-btn-spinner" aria-hidden="true" />}
          {busy ? "Checking…" : state === "start" ? ({ signin: "Continue", signup: "Create account", recovery: "Email me a code", invitation: "Email me a code" } as const)[mode] : "Continue"}
        </button>
      )}

      {state === "start" && (
        <div className="fb-auth-links">
          {mode !== "signin" && <button type="button" onClick={() => onModeChange("signin")}>Sign in instead</button>}
          {mode !== "recovery" && <button type="button" onClick={() => onModeChange("recovery")}>Forgot password</button>}
          {mode !== "invitation" && <button type="button" onClick={() => onModeChange("invitation")}>I was invited</button>}
          {mode !== "signup" && <button type="button" onClick={() => onModeChange("signup")}>Create a company</button>}
        </div>
      )}
      {state !== "start" && state !== "authenticated" && (
        <div className="fb-auth-links">
          <button type="button" onClick={() => { void applySession(null); setEnrollment(null); setFactorId(null); setError(null); }}>Start over</button>
        </div>
      )}
    </form>
  );
}
