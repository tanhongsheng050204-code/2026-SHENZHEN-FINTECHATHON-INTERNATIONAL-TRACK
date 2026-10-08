import { useEffect, useRef, useState, type FormEvent } from "react";
import { Modal } from "./Modal";
import {
  authMode,
  challengeTotp,
  listFactors,
  registerStepUpHandler,
  sessionMessage,
  verifyTotp,
} from "../api/session";

/**
 * Sensitive actions (granting autonomy, the kill switch, invitations, security
 * settings) need an authenticator code from the last five minutes. When the API
 * answers step_up_required this asks for one, then the request is retried.
 */
export function StepUpPrompt() {
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const resolver = useRef<((ok: boolean) => void) | null>(null);

  useEffect(() => {
    if (authMode !== "backend") return;
    registerStepUpHandler(
      () =>
        new Promise<boolean>((resolve) => {
          resolver.current = resolve;
          setCode("");
          setError(null);
          setOpen(true);
        }),
    );
    return () => registerStepUpHandler(null);
  }, []);

  const finish = (ok: boolean) => {
    setOpen(false);
    resolver.current?.(ok);
    resolver.current = null;
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const factors = await listFactors();
      const factor = factors.find((f) => f.status === "verified");
      if (!factor) {
        setError("This account has no authenticator app set up yet. Sign out and sign in again to set one up.");
        return;
      }
      await verifyTotp(factor.id, await challengeTotp(factor.id), code.trim());
      finish(true);
    } catch (e) {
      setError(sessionMessage(e instanceof Error ? e.message : "", "That code didn't work. Try the current one."));
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;
  return (
    <Modal onClose={() => finish(false)} maxWidth="420px">
      <form className="fb-stepup" onSubmit={(e) => void submit(e)} aria-labelledby="fb-stepup-title">
        <div className="fb-eyebrow">Confirm it's you</div>
        <h2 id="fb-stepup-title">Enter your authenticator code</h2>
        <p className="fb-inbox-muted">This action is protected. Enter the 6-digit code from your authenticator app to continue.</p>
        <label className="fb-cash-field">
          <span>6-digit code</span>
          <input
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="\d{6}"
            maxLength={6}
            autoFocus
            required
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          />
        </label>
        {error && <div className="fb-inbox-error" role="alert">{error}</div>}
        <div className="fb-inbox-actions">
          <button className="fb-btn fb-btn-solid" type="submit" disabled={busy || code.length !== 6}>{busy ? "Checking…" : "Confirm"}</button>
          <button className="fb-btn fb-btn-outline" type="button" onClick={() => finish(false)}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}
