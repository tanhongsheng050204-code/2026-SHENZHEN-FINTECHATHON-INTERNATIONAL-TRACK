import { useEffect, useState, type FormEvent } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { ScorecardCard } from "../components/ScorecardCard";
import { useAuth } from "../auth/AuthProvider";
import { useAppState } from "../lib/appState";
import { SCREENS, type Screen } from "../lib/screens";
import { useI18n } from "../lib/i18n";
import { ApiError, friendlyLoadError } from "../api/client";
import {
  createGrant,
  fetchAuditPacks,
  fetchFinancingMatches,
  fetchGrants,
  fetchPassports,
  issuePassport,
  prepareApplicationPack,
  prepareAuditPack,
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
  const { tx } = useI18n();
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
        <h2>{tx("Financing matches")}</h2>
        <div className="fb-inbox-tabs" role="group" aria-label={tx("Jurisdiction")}>
          {(["MY", "CN"] as Jurisdiction[]).map((j) => (
            <button key={j} type="button" aria-pressed={jurisdiction === j} className={jurisdiction === j ? "is-current" : undefined} onClick={() => setJurisdiction(j)}>
              {tx(j === "MY" ? "Malaysia" : "China")}
            </button>
          ))}
        </div>
      </div>
      {data?.shortfall_gap && <p className="fb-fin-gap">{tx("Gap to cover:")} <strong>{ringgit(data.shortfall_gap)}</strong></p>}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
      {!data && !error && <p className="fb-inbox-muted">{tx("Loading matches…")}</p>}
      {data && (
        <>
          <div className="fb-fin-matches">
            {data.matches.map((m, i) => (
              <article key={m.product.id} className={"fb-fin-match" + (i === 0 && m.eligible ? " is-best" : "")}>
                <div className="fb-fin-match-head">
                  {i === 0 && m.eligible && <span className="fb-inbox-pill is-can">{tx("Best fit")}</span>}
                  <span className={"fb-inbox-pill " + (m.eligible ? "is-approved" : m.steps_away === 1 && m.next_screen ? "is-can" : "is-rejected")}>{tx(m.eligible ? "Eligible" : m.steps_away === 1 && m.next_screen ? "One step away" : "Not eligible yet")}</span>
                  <span className="fb-fin-score" aria-label={tx("Fit score {n} out of 100", { n: m.fit_score })}>{m.fit_score}<small>/100</small></span>
                </div>
                <h3>{tx(m.product.name)}</h3>
                <p className="fb-inbox-muted">{tx(m.product.illustrative_terms)}</p>
                {m.product.source_url && (
                  <p className="fb-fine">
                    <a href={m.product.source_url} target="_blank" rel="noopener noreferrer">{tx("Read the public source")}</a>
                    {m.product.last_verified && tx(", checked {date}", { date: new Date(m.product.last_verified).toLocaleDateString("en-MY", { day: "numeric", month: "short", year: "numeric" }) })}
                    {tx(". Synthetic demo product; no partnership with the scheme's owner.")}
                  </p>
                )}
                <ul className="fb-fin-rules">
                  {m.rules.map((r) => (
                    <li key={r.rule} className={r.passed ? "is-pass" : "is-fail"}>
                      <span aria-hidden="true">{r.passed ? "✓" : "✗"}</span>
                      <span>{tx(r.detail)}{r.evidence.length > 0 && <span className="fb-cash-fx"> · {r.evidence.map((e) => tx(e.label)).join(", ")}</span>}</span>
                    </li>
                  ))}
                </ul>
                <p className="fb-fin-explain">{tx(m.explanation)}</p>
                {m.next_step && (
                  <p className="fb-fin-next">
                    <strong>{tx("Next step:")}</strong> {tx(m.next_step)}{" "}
                    {m.next_screen && (SCREENS as readonly string[]).includes(m.next_screen) && (
                      <button type="button" className="fb-cash-more" onClick={() => show(m.next_screen as Screen)}>{tx("Go →")}</button>
                    )}
                  </p>
                )}
                {prepared[m.product.id] ? (
                  <div className="fb-fin-done">
                    {tx("Application pack drafted and waiting for the owner.")}{" "}
                    <button type="button" className="fb-cash-more" onClick={() => show("inbox")}>{tx("Open review inbox")}</button>
                  </div>
                ) : (
                  canPrepare && m.eligible && (
                    <button className="fb-btn fb-btn-outline" type="button" disabled={busy !== null} onClick={() => void prepare(m.product.id)}>
                      {busy === m.product.id ? tx("Preparing…") : tx("Prepare application pack")}
                    </button>
                  )
                )}
              </article>
            ))}
          </div>
          <p className="fb-inbox-muted">{tx(data.disclaimer)}</p>
        </>
      )}
    </section>
  );
}

// ── Sharing: lender and auditor grants ──────────────────────────────────────

function Grants({ kind, scopeId }: { kind: GrantKind; scopeId: string }) {
  const { tx } = useI18n();
  const [grants, setGrants] = useState<ExternalGrant[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [days, setDays] = useState(7);
  const [exact, setExact] = useState(false);
  const [busy, setBusy] = useState(false);
  const [newLink, setNewLink] = useState<{ grantId: string; url: string } | null>(null);
  const [revokedNote, setRevokedNote] = useState<string | null>(null);

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
      setError(tx("Enter a valid email address."));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const grant = await createGrant(kind, scopeId, { grantee_email: email, expires_in_days: days, allow_exact_values: exact });
      setGrants((g) => [grant, ...g]);
      setNewLink({ grantId: grant.id, url: window.location.origin + grant.share_path });
      setRevokedNote(null);
      setEmail("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (grantId: string) => {
    setError(null);
    try {
      const revoked = await revokeGrant(kind, scopeId, grantId);
      setGrants((g) => g.map((x) => (x.id === grantId ? revoked : x)));
      // The link shown after sharing is dead now: stop offering it.
      setNewLink((current) => (current?.grantId === grantId ? null : current));
      setRevokedNote(tx("Revoked. The link no longer opens, including in a tab that is already open once it reloads."));
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <div className="fb-fin-grants">
      <div className="fb-inbox-label">{tx("Who can see it")}</div>
      {grants.length === 0 && <p className="fb-inbox-muted">{tx("Not shared with anyone.")}</p>}
      {grants.map((g) => (
        <div key={g.id} className="fb-fin-grant">
          <span>
            <strong>{tx(kind === "lender" ? "Lender" : "Auditor")}</strong> · {tx(kind === "auditor" ? "read-only" : g.allow_exact_values ? "exact values" : "ranges only")}
            <br />
            <span className="fb-inbox-muted">{g.status === "active" ? tx("Ends {date}", { date: when(g.expires_at) }) : tx(g.status === "revoked" ? "Revoked" : "Expired")}</span>
          </span>
          {g.status === "active" && (
            <button className="fb-btn fb-btn-outline fb-fin-revoke" type="button" onClick={() => void revoke(g.id)}>{tx("Revoke")}</button>
          )}
        </div>
      ))}
      <form className="fb-fin-share" onSubmit={(e) => void share(e)}>
        <label className="fb-cash-field">
          <span>{tx(kind === "lender" ? "Share with a lender" : "Share with an external auditor")}</span>
          <input type="email" required placeholder="name@bank.example" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="fb-cash-field fb-fin-days">
          <span>{tx("For (days)")}</span>
          <input type="number" min={1} max={30} value={days} onChange={(e) => setDays(Math.max(1, Math.min(30, Number(e.target.value) || 1)))} />
        </label>
        {kind === "lender" && (
          <label className="fb-fin-check"><input type="checkbox" checked={exact} onChange={(e) => setExact(e.target.checked)} />{tx("Show exact values (otherwise ranges)")}</label>
        )}
        <button className="fb-btn fb-btn-solid" type="submit" disabled={busy}>{busy ? tx("Sharing…") : tx("Share")}</button>
      </form>
      {newLink && (
        <div className="fb-fin-done" role="status">
          {tx("Shared. Send this link:")} <a href={newLink.url} target="_blank" rel="noreferrer"><code>{newLink.url}</code></a>. {tx("Access ends automatically and you can revoke it at any time.")}
        </div>
      )}
      {revokedNote && <div className="fb-fin-done" role="status">{revokedNote}</div>}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
    </div>
  );
}

// ── Passport ────────────────────────────────────────────────────────────────

function PassportCard({ passport, isOwner }: { passport: Passport; isOwner: boolean }) {
  const { tx } = useI18n();
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
        <h2>{tx("Financing Readiness Passport · v{n}", { n: passport.version })}</h2>
        {passport.anchor?.anchored_at && <span className="fb-inbox-pill is-approved">{tx("Digest anchored")}</span>}
      </div>
      <p className="fb-inbox-muted">{passport.company_label} · {tx("issued {date}", { date: when(passport.issued_at) })}</p>
      <dl className="fb-fin-metrics">
        {passport.metrics.map((m) => (
          <div key={m.key}>
            <dt>{tx(m.label)}</dt>
            <dd>{m.value}<span className="fb-cash-fx">{m.evidence.length > 0 && ` · ${m.evidence.map((e) => tx(e.label)).join(", ")}`}</span></dd>
          </div>
        ))}
      </dl>
      <p className="fb-fin-hash">SHA-256 <code title={passport.sha256}>{shortHash(passport.sha256)}</code>{passport.anchor && <> · {tx("anchored in")} <code>{passport.anchor.repository_path}</code></>}</p>
      <div className="fb-inbox-actions">
        <button className="fb-btn fb-btn-outline" type="button" disabled={checking} onClick={() => void check()}>
          {checking ? tx("Checking…") : tx("Check it like a lender would")}
        </button>
        <button className="fb-btn fb-btn-outline" type="button" onClick={download}>{tx("Download document")}</button>
      </div>
      {result && (
        <div className={"fb-fin-verify is-" + result.status} role="status">
          {result.status === "verified" && <><strong>{tx("Verified.")}</strong> {tx(result.chain_intact ? "This document matches what DuitDuit issued, and the audit chain is intact." : "This document matches what DuitDuit issued, and the audit chain is broken.")}</>}
          {result.status === "mismatch" && <><strong>{tx("Does not match.")}</strong> {tx("Changed: {fields}.", { fields: result.mismatched_fields.join(", ") || "the document" })}</>}
          {result.status === "unknown_passport" && <><strong>{tx("Unknown Passport.")}</strong> {tx("DuitDuit never issued this document.")}</>}
        </div>
      )}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
      {isOwner && <Grants kind="lender" scopeId={passport.id} />}
    </section>
  );
}

function AuditPackCard({ pack, isOwner }: { pack: AuditPack; isOwner: boolean }) {
  const { tx } = useI18n();
  return (
    <section className="fb-cash-card">
      <div className="fb-cash-card-head">
        <h2>{tx("Audit pack · {period}", { period: pack.period })}</h2>
        <span className="fb-inbox-muted">{tx("Prepared {date}", { date: when(pack.created_at) })}</span>
      </div>
      <p className="fb-inbox-muted">{tx("Read-only evidence for an external auditor. Each item carries its own SHA-256.")}</p>
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

function currentQuarter(): string {
  const now = new Date();
  return `${now.getFullYear()}-Q${Math.floor(now.getMonth() / 3) + 1}`;
}

function Issue({ isOwner, hasPassport, onPassport, onPack, onError }: {
  isOwner: boolean;
  hasPassport: boolean;
  onPassport: (p: Passport) => void;
  onPack: (p: AuditPack) => void;
  onError: (message: string | null) => void;
}) {
  const { tx } = useI18n();
  const [busy, setBusy] = useState<"passport" | "pack" | null>(null);
  const [period, setPeriod] = useState(currentQuarter);

  const act = async (kind: "passport" | "pack") => {
    setBusy(kind);
    onError(null);
    try {
      if (kind === "passport") onPassport(await issuePassport());
      else onPack(await prepareAuditPack(period));
    } catch (e) {
      onError(errorText(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="fb-cash-card" aria-label={tx("Issue documents")}>
      <h2>{tx("Documents for lenders and auditors")}</h2>
      <p className="fb-inbox-muted">{tx("Each one is computed from your records, hashed, and written to your audit chain, so anyone you share it with can check it was not changed.")}</p>
      <div className="fb-cash-whatif">
        {isOwner && (
          <button className="fb-btn fb-btn-solid" type="button" disabled={busy !== null} onClick={() => void act("passport")}>
            {busy === "passport" ? tx("Issuing…") : tx(hasPassport ? "Issue a new Passport version" : "Issue a Passport")}
          </button>
        )}
        <label className="fb-cash-field">
          <span>{tx("Audit period")}</span>
          <input value={period} maxLength={7} onChange={(e) => setPeriod(e.target.value.toUpperCase())} aria-label={tx("Audit period, for example 2026-Q3")} />
        </label>
        <button className="fb-btn fb-btn-outline" type="button" disabled={busy !== null || !/^\d{4}(-Q[1-4])?$/.test(period)} onClick={() => void act("pack")}>
          {busy === "pack" ? tx("Preparing…") : tx("Prepare audit pack")}
        </button>
      </div>
    </section>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function Financing() {
  const { t, tx } = useI18n();
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
        <div className="fb-eyebrow">{t("nav.group.money")}</div>
        <h1>{t("nav.financing")}</h1>
        <p>{t("fin.desc")}</p>
      </header>
      <div className="fb-page-body">
        <div className="fb-cash">
          <ScorecardCard />
          <Matches canPrepare={PACK_ROLES.has(role)} />
          {error && <div className="fb-callout" role="alert">{error}</div>}
          {PACK_ROLES.has(role) && (
            <Issue isOwner={isOwner} hasPassport={passport !== null} onPassport={setPassport} onPack={setPack} onError={setError} />
          )}
          {passport && <PassportCard key={passport.id} passport={passport} isOwner={isOwner} />}
          {pack && <AuditPackCard key={pack.id} pack={pack} isOwner={isOwner} />}
          {!isOwner && (passport || pack) && <p className="fb-inbox-muted">{tx("Only the owner can share these with a lender or auditor.")}</p>}
        </div>
      </div>
    </div>
  );
}
