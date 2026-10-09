import { useEffect, useRef, useState, type FormEvent } from "react";
import { Modal } from "./Modal";
import {
  authMode,
  challengeTotp,
  enrollTotp,
  listFactors,
  registerStepUpHandler,
  sessionMessage,
  verifyTotp,
  type TotpEnrollment,
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
  const [factorId, setFactorId] = useState<string | null>(null);
  const [enrollment, setEnrollment] = useState<TotpEnrollment | null>(null);
  const [loading, setLoading] = useState(false);
  const attempt = useRef(0);
  const resolver = useRef<((ok: boolean) => void) | null>(null);

  useEffect(() => {
    if (authMode !== "backend") return;
    registerStepUpHandler(
      () =>
        new Promise<boolean>((resolve) => {
          attempt.current += 1;
          resolver.current = resolve;
          setCode("");
          setError(null);
          setBusy(false);
          setLoading(true);
          setFactorId(null);
          setEnrollment(null);
          setOpen(true);
        }),
    );
    return () => {
      attempt.current += 1;
      resolver.current?.(false);
      resolver.current = null;
      registerStepUpHandler(null);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    let active = true;
    listFactors().then((factors) => {
      if (active) setFactorId(factors.find((f) => f.status === "verified")?.id ?? null);
    }).catch((e) => {
      if (active) setError(sessionMessage(e instanceof Error ? e.message : ""));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [open]);

  const finish = (ok: boolean) => {
    attempt.current += 1;
    setOpen(false);
    setBusy(false);
    resolver.current?.(ok);
    resolver.current = null;
    setEnrollment(null);
    setCode("");
  };

  const enroll = async () => {
    const current = attempt.current;
    setBusy(true);
    setError(null);
    try {
      const next = await enrollTotp();
      if (current !== attempt.current) return;
      setEnrollment(next);
      setFactorId(next.factor_id);
    } catch (e) {
      if (current === attempt.current) setError(sessionMessage(e instanceof Error ? e.message : ""));
    } finally {
      if (current === attempt.current) setBusy(false);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const current = attempt.current;
    try {
      if (!factorId) return;
      await verifyTotp(factorId, await challengeTotp(factorId), code.trim());
      if (current === attempt.current) finish(true);
    } catch (e) {
      if (current === attempt.current) setError(sessionMessage(e instanceof Error ? e.message : "", "That code didn't work. Try the current one."));
    } finally {
      if (current === attempt.current) setBusy(false);
    }
  };

  if (!open) return null;
  return (
    <Modal onClose={() => finish(false)} maxWidth="420px">
      <form className="fb-stepup" onSubmit={(e) => void submit(e)} aria-labelledby="fb-stepup-title">
        <div className="fb-eyebrow">Confirm it's you</div>
        <h2 id="fb-stepup-title">Enter your authenticator code</h2>
        <p className="fb-inbox-muted">This action is protected. Enter the 6-digit code from your authenticator app to continue.</p>
        {loading && <p role="status">Checking your authenticator setup…</p>}
        {!loading && !factorId && <div>
          <p>Add DuitDuit to an authenticator app before your first protected action.</p>
          <button className="fb-btn fb-btn-outline" type="button" disabled={busy} onClick={() => void enroll()}>Set up authenticator</button>
        </div>}
        {enrollment && <div>
          <p>Scan this QR code in your authenticator app, then enter its code below.</p>
          <img width="190" height="190" alt="DuitDuit authenticator setup QR code" src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(enrollment.qr_code)}`} />
          <label className="fb-cash-field"><span>Or enter this setup key in your authenticator app</span><input readOnly value={enrollment.secret} /></label>
        </div>}
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
          <button className="fb-btn fb-btn-solid" type="submit" disabled={busy || loading || !factorId || code.length !== 6}>{busy ? "Checking…" : "Confirm"}</button>
          <button className="fb-btn fb-btn-outline" type="button" onClick={() => finish(false)}>Cancel</button>
        </div>
      </form>
    </Modal>
  );
}
