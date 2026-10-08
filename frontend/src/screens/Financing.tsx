import { useEffect, useState, type FormEvent } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { ScorecardCard } from "../components/ScorecardCard";
import { useAuth } from "../auth/AuthProvider";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import { ApiError, friendlyLoadError } from "../api/client";
import {
  createGrant,
  fetchAuditPacks,
  fetchFinancingMatches,
  fetchGrants,
  fetchPassports,
  prepareApplicationPack,
  revokeGrant,
  ringgit,
  verifyPassport,
  type AuditPack,
  type ExternalGrant,
  type FinancingMatchesResponse,
  type GrantKind,
  type Jurisdiction,
  type Passport,
  type VerificationResult,
} from "../api/topicE";

const PACK_ROLES = new Set(["finance_ops", "owner_director"]);
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-MY", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function shortHash(hash: string): string {
  return `${hash.slice(0, 12)}…${hash.slice(-8)}`;
}

function errorText(error: unknown): string {
  return friendlyLoadError(error instanceof ApiError ? error.code : error instanceof Error ? error.message : "");
}

// ── Financing matches ───────────────────────────────────────────────────────

function Matches({ canPrepare }: { canPrepare: boolean }) {
  const { show } = useAppState();
  const [jurisdiction, setJurisdiction] = useState<Jurisdiction>("MY");
  const [data, setData] = useState<FinancingMatchesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [prepared, setPrepared] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchFinancingMatches(jurisdiction)
      .then((d) => { if (active) { setData(d); setError(null); } })
      .catch((e) => active && setError(errorText(e)));
    return () => { active = false; };
  }, [jurisdiction]);

  const prepare = async (productId: string) => {
    setBusy(productId);
    try {
      const { action } = await prepareApplicationPack(productId);
      setPrepared((p) => ({ ...p, [productId]: action.title }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="fb-cash-card">
      <div className="fb-cash-card-head">
        <h2>Financing matches</h2>
        <div className="fb-inbox-tabs" role="group" aria-label="Jurisdiction">
          {(["MY", "CN"] as Jurisdiction[]).map((j) => (
            <button key={j} type="button" aria-pressed={jurisdiction === j} className={jurisdiction === j ? "is-current" : undefined} onClick={() => setJurisdiction(j)}>
              {j === "MY" ? "Malaysia" : "China"}
            </button>
          ))}
        </div>
      </div>
      {data?.shortfall_gap && <p className="fb-fin-gap">Gap to cover: <strong>{ringgit(data.shortfall_gap)}</strong></p>}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
      {!data && !error && <p className="fb-inbox-muted">Loading matches…</p>}
      {data && (
        <>
          <div className="fb-fin-matches">
            {data.matches.map((m, i) => (
              <article key={m.product.id} className={"fb-fin-match" + (i === 0 && m.eligible ? " is-best" : "")}>
                <div className="fb-fin-match-head">
                  {i === 0 && m.eligible && <span className="fb-inbox-pill is-can">Best fit</span>}
                  <span className={"fb-inbox-pill " + (m.eligible ? "is-approved" : "is-rejected")}>{m.eligible ? "Eligible" : "Not eligible"}</span>
                  <span className="fb-fin-score" aria-label={`Fit score ${m.fit_score} out of 100`}>{m.fit_score}<small>/100</small></span>
                </div>
                <h3>{m.product.name}</h3>
                <p className="fb-inbox-muted">{m.product.illustrative_terms}</p>
                <ul className="fb-fin-rules">
                  {m.rules.map((r) => (
                    <li key={r.rule} className={r.passed ? "is-pass" : "is-fail"}>
                      <span aria-hidden="true">{r.passed ? "✓" : "✗"}</span>
                      <span>{r.detail}{r.evidence.length > 0 && <span className="fb-cash-fx"> · {r.evidence.map((e) => e.label).join(", ")}</span>}</span>
                    </li>
                  ))}
                </ul>
                <p className="fb-fin-explain">{m.explanation}</p>
                {prepared[m.product.id] ? (
                  <div className="fb-fin-done">
                    Application pack drafted and waiting for the owner.{" "}
                    <button type="button" className="fb-cash-more" onClick={() => show("inbox")}>Open review inbox</button>
                  </div>
                ) : (
                  canPrepare && m.eligible && (
                    <button className="fb-btn fb-btn-outline" type="button" disabled={busy !== null} onClick={() => void prepare(m.product.id)}>
                      {busy === m.product.id ? "Preparing…" : "Prepare application pack"}
                    </button>
                  )
                )}
              </article>
            ))}
          </div>
          <p className="fb-inbox-muted">{data.disclaimer}</p>
        </>
      )}
    </section>
  );
}

// ── Sharing: lender and auditor grants ──────────────────────────────────────

function Grants({ kind, scopeId }: { kind: GrantKind; scopeId: string }) {
  const [grants, setGrants] = useState<ExternalGrant[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [days, setDays] = useState(7);
  const [exact, setExact] = useState(false);
  const [busy, setBusy] = useState(false);
  const [newLink, setNewLink] = useState<string | null>(null);
  const who = kind === "lender" ? "a lender" : "an external auditor";

  useEffect(() => {
    let active = true;
    fetchGrants(kind, scopeId)
      .then((g) => active && setGrants(g))
      .catch((e) => active && setError(errorText(e)));
    return () => { active = false; };
  }, [kind, scopeId]);

  const share = async (event: FormEvent) => {
    event.preventDefault();
    if (!EMAIL_PATTERN.test(email)) {
      setError("Enter a valid email address.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const grant = await createGrant(kind, scopeId, { grantee_email: email, expires_in_days: days, allow_exact_values: exact });
      setGrants((g) => [grant, ...g]);
      setNewLink(window.location.origin + grant.share_path);
      setEmail("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (grantId: string) => {
    try {
      const revoked = await revokeGrant(kind, scopeId, grantId);
      setGrants((g) => g.map((x) => (x.id === grantId ? revoked : x)));
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <div className="fb-fin-grants">
      <div className="fb-inbox-label">Who can see it</div>
      {grants.length === 0 && <p className="fb-inbox-muted">Not shared with anyone.</p>}
      {grants.map((g) => (
        <div key={g.id} className="fb-fin-grant">
          <span>
            <strong>{kind === "lender" ? "Lender" : "Auditor"}</strong> · {kind === "auditor" ? "read-only" : g.allow_exact_values ? "exact values" : "ranges only"}
            <br />
            <span className="fb-inbox-muted">{g.status === "active" ? `Ends ${when(g.expires_at)}` : g.status === "revoked" ? "Revoked" : "Expired"}</span>
          </span>
          {g.status === "active" && (
            <button className="fb-btn fb-btn-outline fb-fin-revoke" type="button" onClick={() => void revoke(g.id)}>Revoke</button>
          )}
        </div>
      ))}
      <form className="fb-fin-share" onSubmit={(e) => void share(e)}>
        <label className="fb-cash-field">
          <span>Share with {who}</span>
          <input type="email" required placeholder="name@bank.example" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="fb-cash-field fb-fin-days">
          <span>For (days)</span>
          <input type="number" min={1} max={30} value={days} onChange={(e) => setDays(Math.max(1, Math.min(30, Number(e.target.value) || 1)))} />
        </label>
        {kind === "lender" && (
          <label className="fb-fin-check"><input type="checkbox" checked={exact} onChange={(e) => setExact(e.target.checked)} />Show exact values (otherwise ranges)</label>
        )}
        <button className="fb-btn fb-btn-solid" type="submit" disabled={busy}>{busy ? "Sharing…" : "Share"}</button>
      </form>
      {newLink && (
        <div className="fb-fin-done" role="status">
          Shared. Send {kind === "lender" ? "the lender" : "the auditor"} this link: <a href={newLink} target="_blank" rel="noreferrer"><code>{newLink}</code></a>. Access ends automatically and you can revoke it at any time.
        </div>
      )}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
    </div>
  );
}

// ── Passport ────────────────────────────────────────────────────────────────

function PassportCard({ passport, isOwner }: { passport: Passport; isOwner: boolean }) {
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const check = async () => {
    setChecking(true);
    setError(null);
    try {
      setResult(await verifyPassport(passport));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setChecking(false);
    }
  };

  const download = () => {
    const blob = new Blob([JSON.stringify(passport, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${passport.id}-v${passport.version}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="fb-cash-card">
      <div className="fb-cash-card-head">
        <h2>Financing Readiness Passport · v{passport.version}</h2>
        {passport.anchor?.anchored_at && <span className="fb-inbox-pill is-approved">Digest anchored</span>}
      </div>
      <p className="fb-inbox-muted">{passport.company_label} · issued {when(passport.issued_at)}</p>
      <dl className="fb-fin-metrics">
        {passport.metrics.map((m) => (
          <div key={m.key}>
            <dt>{m.label}</dt>
            <dd>{m.value}<span className="fb-cash-fx">{m.evidence.length > 0 && ` · ${m.evidence.map((e) => e.label).join(", ")}`}</span></dd>
          </div>
        ))}
      </dl>
      <p className="fb-fin-hash">SHA-256 <code title={passport.sha256}>{shortHash(passport.sha256)}</code>{passport.anchor && <> · anchored in <code>{passport.anchor.repository_path}</code></>}</p>
      <div className="fb-inbox-actions">
        <button className="fb-btn fb-btn-outline" type="button" disabled={checking} onClick={() => void check()}>
          {checking ? "Checking…" : "Check it like a lender would"}
        </button>
        <button className="fb-btn fb-btn-outline" type="button" onClick={download}>Download document</button>
      </div>
      {result && (
        <div className={"fb-fin-verify is-" + result.status} role="status">
          {result.status === "verified" && <><strong>Verified.</strong> This document matches what FinBrain issued, and the audit chain is {result.chain_intact ? "intact" : "broken"}.</>}
          {result.status === "mismatch" && <><strong>Does not match.</strong> Changed: {result.mismatched_fields.join(", ") || "the document"}.</>}
          {result.status === "unknown_passport" && <><strong>Unknown Passport.</strong> FinBrain never issued this document.</>}
        </div>
      )}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
      {isOwner && <Grants kind="lender" scopeId={passport.id} />}
    </section>
  );
}

function AuditPackCard({ pack, isOwner }: { pack: AuditPack; isOwner: boolean }) {
  return (
    <section className="fb-cash-card">
      <div className="fb-cash-card-head">
        <h2>Audit pack · {pack.period}</h2>
        <span className="fb-inbox-muted">Prepared {when(pack.created_at)}</span>
      </div>
      <p className="fb-inbox-muted">Read-only evidence for an external auditor. Each item carries its own SHA-256.</p>
      <ul className="fb-fin-items">
        {pack.items.map((item) => (
          <li key={item.key}>
            <span><strong>{item.label}</strong><br /><span className="fb-inbox-muted">{item.description}</span></span>
            <code title={item.sha256}>{shortHash(item.sha256)}</code>
          </li>
        ))}
      </ul>
      {isOwner && <Grants kind="auditor" scopeId={pack.id} />}
    </section>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function Financing() {
  const { t } = useI18n();
  const { identity } = useAuth();
  const role = identity?.role ?? "";
  const isOwner = role === "owner_director";
  const [passport, setPassport] = useState<Passport | null>(null);
  const [pack, setPack] = useState<AuditPack | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([fetchPassports(), fetchAuditPacks()])
      .then(([passports, packs]) => {
        if (!active) return;
        setPassport(passports.at(-1) ?? null);
        setPack(packs.at(-1) ?? null);
      })
      .catch((e) => active && setError(errorText(e)));
    return () => { active = false; };
  }, []);

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="financing" />
      <AppTopBar current="financing" />
      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.cash")}</div>
        <h1>{t("nav.financing")}</h1>
        <p>{t("fin.desc")}</p>
      </header>
      <div className="fb-page-body">
        <div className="fb-cash">
          <ScorecardCard />
          <Matches canPrepare={PACK_ROLES.has(role)} />
          {error && <div className="fb-callout" role="alert">{error}</div>}
          {passport && <PassportCard passport={passport} isOwner={isOwner} />}
          {pack && <AuditPackCard pack={pack} isOwner={isOwner} />}
          {!isOwner && (passport || pack) && <p className="fb-inbox-muted">Only the owner can share these with a lender or auditor.</p>}
        </div>
      </div>
    </div>
  );
}
