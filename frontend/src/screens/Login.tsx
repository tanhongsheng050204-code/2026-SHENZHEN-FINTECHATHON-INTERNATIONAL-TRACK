import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { authMode, demoAvailable, demoSignIn, sessionMessage } from "../api/session";
import { AuthFlow, type AuthFlowMode } from "../components/AuthFlow";
import { AuthStory } from "../components/AuthStory";
import { useAppState } from "../lib/appState";

export default function Login() {
  const { show } = useAppState();
  const { authError, signIn, applySession } = useAuth();
  const [demoOpen, setDemoOpen] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  const [demoError, setDemoError] = useState("");

  useEffect(() => {
    if (authMode !== "backend") return;
    let active = true;
    void demoAvailable().then((open) => active && setDemoOpen(open));
    return () => { active = false; };
  }, []);

  const openDemo = async () => {
    setDemoError("");
    setDemoBusy(true);
    try {
      await applySession(await demoSignIn());
      show("home");
    } catch (cause) {
      const code = cause instanceof Error ? cause.message : "";
      setDemoError(sessionMessage(code, "The demo company didn't open. Wait a few seconds and try again."));
    } finally {
      setDemoBusy(false);
    }
  };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [shakeToken, setShakeToken] = useState(0);
  const [flowMode, setFlowMode] = useState<AuthFlowMode>("signin");

  const hasError = Boolean(error || authError);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await signIn(email.trim(), password);
      show("home");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sign in failed.");
      setShakeToken((k) => k + 1);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fb-root fb-mkt lx lx-auth">
      <div className="fb-mkt-auth-wrap">
        <AuthStory
          from="login"
          title="Welcome back to your books."
          body="Three locks stand between this page and your company's numbers. Your role decides what you see once you are in."
        />
        <div className="fb-mkt-auth-form-wrap">
          {authMode === "backend" ? (
            <div style={{ width: "100%", maxWidth: 400, display: "flex", flexDirection: "column", gap: "1.75rem" }}>
              {demoOpen && flowMode === "signin" && (
                <section
                  aria-labelledby="dd-demo-title"
                  style={{
                    display: "flex", flexDirection: "column", gap: ".75rem", padding: "1.25rem 1.25rem 1rem",
                    border: "1px solid var(--a-line)", borderRadius: 16, background: "var(--a-surface)",
                  }}
                >
                  <h2 id="dd-demo-title" style={{ fontSize: "1.2rem", margin: 0 }}>Judging DuitDuit? Open the demo company</h2>
                  <p style={{ margin: 0, color: "var(--a-ink-soft)", fontSize: ".92rem" }}>
                    A synthetic Malaysian importer, signed in as its owner. No sign-up. Approvals work,
                    and anything that would leave the company is recorded, never sent.
                  </p>
                  <button
                    className="fb-mkt-btn is-accent is-lg"
                    style={{ width: "100%", justifyContent: "center" }}
                    type="button"
                    onClick={openDemo}
                    disabled={demoBusy}
                  >
                    {demoBusy && <span className="fb-mkt-btn-spinner" aria-hidden="true" />}
                    {demoBusy ? "Opening the demo company…" : "Open the demo company"}
                  </button>
                  {demoError && <div className="fb-mkt-callout" role="alert">{demoError}</div>}
                </section>
              )}
              <AuthFlow mode={flowMode} onModeChange={setFlowMode} />
            </div>
          ) : (
          <form className="fb-mkt-auth-form" onSubmit={submit}>
            <h2>Sign in</h2>
            <p>Use the account your administrator created for you.</p>
            <div key={shakeToken} className={"fb-mkt-auth-fields" + (hasError ? " is-shake" : "")}>
              <label className="fb-mkt-field" htmlFor="fb-login-username">Email
                <input
                  className={"fb-mkt-input" + (hasError ? " is-error" : "")}
                  id="fb-login-username"
                  name="username"
                  type="email"
                  autoComplete="username"
                  autoFocus
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </label>
              <label className="fb-mkt-field" htmlFor="fb-login-password">Password
                <div className="fb-mkt-input-wrap">
                  <input
                    className={"fb-mkt-input" + (hasError ? " is-error" : "")}
                    id="fb-login-password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                  />
                  <button
                    className="fb-mkt-password-toggle"
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                  >
                    {showPassword ? (
                      <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>
                    ) : (
                      <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 3l18 18" /><path d="M10.6 5.2A10.6 10.6 0 0 1 12 5c6.5 0 10 7 10 7a15.6 15.6 0 0 1-3.4 4.3M6.6 6.6C3.7 8.5 2 12 2 12s3.5 7 10 7a9.7 9.7 0 0 0 4.2-.9" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></svg>
                    )}
                  </button>
                </div>
              </label>
              {hasError && (
                <div className="fb-mkt-callout" role="alert">{error || authError}</div>
              )}
            </div>
            <button className="fb-mkt-btn is-accent is-lg" style={{ width: "100%", justifyContent: "center", marginTop: ".2rem" }} type="submit" disabled={submitting}>
              {submitting && <span className="fb-mkt-btn-spinner" aria-hidden="true" />}
              {submitting ? "Signing in…" : "Sign in"}
            </button>
            <div className="fb-mkt-fine">Accounts and roles are provisioned by the DuitDuit administrator.</div>
          </form>
          )}
        </div>
      </div>
    </div>
  );
}
