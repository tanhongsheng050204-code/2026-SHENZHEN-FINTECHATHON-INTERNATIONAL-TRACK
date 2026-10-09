import { useEffect, useState, type ChangeEvent } from "react";
import { Wordmark } from "../components/Logo";
import { friendlyLoadError } from "../api/client";
import type { SharedRoute } from "../lib/sharedRoutes";
import {
  errorCode,
  fetchSharedAuditPack,
  fetchSharedPassport,
  verifyPassportPublic,
  type AuditPack,
  type Passport,
  type VerificationResult,
} from "../api/topicE";

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-MY", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function loadError(error: unknown): string {
  const code = errorCode(error);
  if (code === "grant_expired") return "This link has expired. Ask the company for a new one.";
  if (code === "grant_revoked") return "The company has withdrawn this link.";
  if (code === "grant_not_found") return "This link is not valid. Check that you copied all of it.";
  return friendlyLoadError(code);
}

function VerifyResult({ result }: { result: VerificationResult }) {
  return (
    <div className={"fb-fin-verify is-" + result.status} role="status">
      {result.status === "verified" && <><strong>Verified.</strong> This document is exactly what FinBrain issued{result.chain_intact ? ", and the audit chain behind it is intact." : ", but the audit chain could not be confirmed."}</>}
      {result.status === "mismatch" && <><strong>Does not match what was issued.</strong> Changed: {result.mismatched_fields.join(", ") || "the document"}.</>}
      {result.status === "unknown_passport" && <><strong>Unknown document.</strong> FinBrain never issued this Passport.</>}
      <br />
      <span className="fb-cash-fx">SHA-256 computed {result.computed_sha256.slice(0, 16)}…{result.anchor && ` · anchored in ${result.anchor.repository_path}`}</span>
    </div>
  );
}

function PassportView({ token }: { token: string }) {
  const [passport, setPassport] = useState<Passport | null>(null);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchSharedPassport(token).then((p) => active && setPassport(p)).catch((e) => active && setError(loadError(e)));
    return () => { active = false; };
  }, [token]);

  const verify = async () => {
    if (!passport) return;
    try {
      setResult(await verifyPassportPublic(passport));
    } catch (e) {
      setError(loadError(e));
    }
  };

  if (error) return <div className="fb-callout" role="alert">{error}</div>;
  if (!passport) return <div className="fb-callout">Loading the shared Passport…</div>;
  return (
    <section className="fb-cash-card">
      <div className="fb-eyebrow">Financing Readiness Passport · v{passport.version}</div>
      <h1 className="fb-share-title">{passport.company_label}</h1>
      <p className="fb-inbox-muted">Issued {when(passport.issued_at)}. Figures are shown as ranges unless the company allowed exact values.</p>
      <dl className="fb-fin-metrics">
        {passport.metrics.map((m) => (
          <div key={m.key}>
            <dt>{m.label}</dt>
            <dd>{m.value}<span className="fb-cash-fx">{m.evidence.length > 0 && ` · ${m.evidence.map((e) => e.label).join(", ")}`}</span></dd>
          </div>
        ))}
      </dl>
      <p className="fb-fin-hash">SHA-256 <code title={passport.sha256}>{passport.sha256}</code></p>
      <div className="fb-inbox-actions">
        <button className="fb-btn fb-btn-solid" type="button" onClick={() => void verify()}>Verify this Passport</button>
      </div>
      {result && <VerifyResult result={result} />}
    </section>
  );
}

function AuditPackView({ token }: { token: string }) {
  const [pack, setPack] = useState<AuditPack | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchSharedAuditPack(token).then((p) => active && setPack(p)).catch((e) => active && setError(loadError(e)));
    return () => { active = false; };
  }, [token]);

  if (error) return <div className="fb-callout" role="alert">{error}</div>;
  if (!pack) return <div className="fb-callout">Loading the shared audit pack…</div>;
  return (
    <section className="fb-cash-card">
      <div className="fb-eyebrow">Audit pack · {pack.period}</div>
      <h1 className="fb-share-title">{pack.company_label}</h1>
      <p className="fb-inbox-muted">Prepared {when(pack.created_at)}. Read-only. Each item carries its own SHA-256 so you can check the files you receive.</p>
      <ul className="fb-fin-items">
        {pack.items.map((item) => (
          <li key={item.key}>
            <span><strong>{item.label}</strong><br /><span className="fb-inbox-muted">{item.description}</span></span>
            <code title={item.sha256}>{item.sha256.slice(0, 12)}…{item.sha256.slice(-8)}</code>
          </li>
        ))}
      </ul>
      <p className="fb-fin-hash">Pack SHA-256 <code>{pack.sha256}</code></p>
    </section>
  );
}

function VerifyUpload() {
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const check = async (event: ChangeEvent<HTMLInputElement>) => {
    setResult(null);
    setError(null);
    const file = event.target.files?.[0];
    if (!file) return;
    let document: unknown;
    try {
      document = JSON.parse(await file.text());
    } catch {
      setError("That file is not a Passport document (it should be the .json file you were sent).");
      return;
    }
    try {
      setResult(await verifyPassportPublic(document));
    } catch (e) {
      const code = errorCode(e);
      setError(code.includes("extra") || code.includes("Field") || code.includes("missing")
        ? "This document has fields that FinBrain never issues, so it cannot be genuine."
        : loadError(e));
    }
  };

  return (
    <section className="fb-cash-card">
      <div className="fb-eyebrow">For lenders and auditors</div>
      <h1 className="fb-share-title">Check a Financing Readiness Passport</h1>
      <p className="fb-inbox-muted">Choose the Passport file a company sent you. FinBrain recomputes its SHA-256, compares it with what was issued and checks the audit chain. The file is only checked, not stored.</p>
      <label className="fb-cash-field">
        <span>Passport file (.json)</span>
        <input type="file" accept="application/json,.json" onChange={(e) => void check(e)} />
      </label>
      {result && <VerifyResult result={result} />}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
    </section>
  );
}

export default function SharedView({ route }: { route: SharedRoute }) {
  return (
    <div className="fb-root fb-share">
      <header className="fb-share-head">
        <Wordmark />
        <span className="fb-inbox-muted">Shared securely through FinBrain OS</span>
      </header>
      <main className="fb-share-main">
        {route.kind === "lender" && <PassportView token={route.token} />}
        {route.kind === "auditor" && <AuditPackView token={route.token} />}
        {route.kind === "verify" && <VerifyUpload />}
        <p className="fb-inbox-muted fb-share-foot">
          This page shows only what the company chose to share, for a limited time, and the company can revoke access at any time.
        </p>
      </main>
    </div>
  );
}
