import { useCallback, useEffect, useState } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { SectionTabs } from "../components/SectionTabs";
import { RecordPanel } from "../components/RecordPanel";
import { useAuth } from "../auth/AuthProvider";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import { ApiError, friendlyLoadError } from "../api/client";
import { ringgit } from "../api/topicE";
import { isPlaceholderName } from "../lib/customerAggregation";
import {
  fetchAnomalies,
  fetchBenchmarks,
  sendAnomalyForReview,
  type AnomaliesResponse,
  type AnomalyFinding,
  type AnomalyKind,
  type BenchmarksResponse,
} from "../api/insights";
import "../components/records.css";
import "./SecurityActivity.css";

const KIND: Record<AnomalyKind, string> = {
  unusual_amount: "Unusual amount",
  possible_duplicate: "Possible duplicate bill",
  new_supplier_large: "Large first bill",
  possible_duplicate_payment: "Possible duplicate payment",
};
const HOW: Record<AnomalyKind, string> = {
  unusual_amount: "Modified z-score: how far the amount is from this supplier's median, in units of its median absolute deviation. Above 3.5 is flagged.",
  possible_duplicate: "Same supplier and amount as another bill, with the same bill number or due within 7 days of it.",
  new_supplier_large: "The supplier's only bill is at or above 90% of the company's other bills.",
  possible_duplicate_payment: "Two equal payments to the same payee within 3 days.",
};
const WORK_ROLES = new Set(["finance_ops", "owner_director"]);

/** Masked supplier names stay masked, and read as a person would expect. */
function readable(label: string, tx: (s: string) => string): string {
  const [first, ...rest] = label.split(" · ");
  const who = rest.join(" · ");
  return who ? `${first} · ${isPlaceholderName(who) ? tx("Protected supplier") : who}` : first;
}

function FindingPanel({ finding, canSend, onClose }: { finding: AnomalyFinding; canSend: boolean; onClose: () => void }) {
  const { tx } = useI18n();
  const { show } = useAppState();
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      await sendAnomalyForReview(finding.ref);
      setSent(true);
    } catch (e) {
      setError(friendlyLoadError(e instanceof ApiError ? e.code : ""));
    } finally {
      setBusy(false);
    }
  };
  return (
    <RecordPanel kicker={tx(KIND[finding.kind])} title={readable(finding.label, tx)} onClose={onClose}>
      <section className="rc-section">
        <h3>{tx("Why it was flagged")}</h3>
        <p className="sa-reason">{tx(finding.reason)}</p>
        <dl className="rc-attrs">
          <dt>{tx("Amount")}</dt><dd>{ringgit(finding.amount_myr)}</dd>
          <dt>{tx("Severity")}</dt><dd><span className={"rc-chip " + (finding.severity === "high" ? "is-red" : "is-amber")}>{finding.severity === "high" ? tx("High") : tx("Medium")}</span></dd>
          {finding.score !== null && <><dt>{tx("Score")}</dt><dd>{finding.score}</dd></>}
          <dt>{tx("Method")}</dt><dd className="sa-method">{tx(HOW[finding.kind])}</dd>
        </dl>
      </section>
      {canSend && (
        <div className="rc-actions">
          {sent ? (
            <button type="button" className="rc-action" onClick={() => show("inbox")}>{tx("Sent to Finance for review. Open the review inbox")}<small>→</small></button>
          ) : (
            <button type="button" className="rc-action is-primary" disabled={busy} onClick={() => void send()}>
              {tx("Ask Finance to check it")}<small>{tx("A review item; nothing is paid or changed")}</small>
            </button>
          )}
        </div>
      )}
      {error && <p className="fb-inbox-error" role="alert">{error}</p>}
      <p className="rc-note">{tx("Statistics on your own records, not a trained model: every flag can be checked by hand from the numbers it names.")}</p>
    </RecordPanel>
  );
}

function Benchmark({ data }: { data: BenchmarksResponse }) {
  const { tx } = useI18n();
  const metric = data.metrics[0];
  return (
    <section className="fb-cash-card">
      <div className="sa-head">
        <h2>{tx("How you compare")}</h2>
        <span className="rc-chip is-blue">{tx("Differential privacy · ε = {e}", { e: data.epsilon })}</span>
      </div>
      <dl className="rc-attrs">
        <dt>{tx("Your customers pay")}</dt>
        <dd>{metric.your_value === null ? tx("Not measured: no paid e-invoices yet") : tx("{n} days late (median)", { n: metric.your_value })}</dd>
        <dt>{tx("Companies on DuitDuit")}</dt>
        <dd>{metric.peer_value === null ? tx("Not released: fewer than {n} companies have data", { n: data.min_companies }) : tx("{n} days late on average, with noise", { n: metric.peer_value })}</dd>
        {metric.noise_scale !== null && <><dt>{tx("Noise")}</dt><dd>{tx("Laplace, scale {s} days", { s: metric.noise_scale })}</dd></>}
      </dl>
      <p className="rc-note">{tx("No company's own figure can be worked out from the average: each company counts once, values are capped, random noise is added, and nothing is shown for fewer than five companies.")}</p>
    </section>
  );
}

export default function Signals() {
  const { t, tx } = useI18n();
  const { identity } = useAuth();
  const canSend = WORK_ROLES.has(identity?.role ?? "");
  const [scan, setScan] = useState<AnomaliesResponse | null>(null);
  const [bench, setBench] = useState<BenchmarksResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const close = useCallback(() => setOpen(null), []);

  useEffect(() => {
    let active = true;
    Promise.all([fetchAnomalies(), fetchBenchmarks()])
      .then(([a, b]) => { if (active) { setScan(a); setBench(b); } })
      .catch((e: Error) => active && setError(friendlyLoadError(e.message)));
    return () => { active = false; };
  }, []);

  const opened = scan?.findings.find((f) => f.ref === open) ?? null;
  const high = scan?.findings.filter((f) => f.severity === "high").length ?? 0;

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="signals" />
      <AppTopBar current="signals" />
      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.money")}</div>
        <h1>{t("nav.cashFinance")}</h1>
        <p>{tx("Bills and payments that look unusual against your own history, and how your collection speed compares with other companies, privately.")}</p>
        <SectionTabs section="money" current="signals" />
      </header>
      <div className="fb-page-body">
        {error && <div className="fb-callout" role="alert">{error}</div>}
        {scan && (
          <div className="dd-board-summary">
            <div><span>{tx("Flagged")}</span><strong className={scan.findings.length ? "is-late" : undefined}>{scan.findings.length}</strong></div>
            <div><span>{tx("High severity")}</span><strong>{high}</strong></div>
            <div><span>{tx("Checked")}</span><strong>{tx("{b} bills · {p} payments", { b: scan.bills_checked, p: scan.payments_checked })}</strong></div>
          </div>
        )}
        <div className="sa-grid">
          <section className="fb-cash-card">
            <div className="sa-head"><h2>{tx("Unusual activity")}</h2></div>
            {!scan && !error && <p className="rc-note">{tx("Checking…")}</p>}
            <ul className="rc-list">
              {scan?.findings.length === 0 && <li className="rc-list-empty">{tx("Nothing unusual among {b} bills and {p} payments.", { b: scan.bills_checked, p: scan.payments_checked })}</li>}
              {scan?.findings.map((f) => (
                <li key={f.ref}>
                  <span className={"rc-chip " + (f.severity === "high" ? "is-red" : "is-amber")}>{tx(KIND[f.kind])}</span>
                  <div className="rc-list-main"><strong>{readable(f.label, tx)}</strong><span>{ringgit(f.amount_myr)} · {tx(f.reason)}</span></div>
                  <button type="button" className="rc-mini" onClick={() => setOpen(f.ref)}>{tx("Open")}</button>
                </li>
              ))}
            </ul>
          </section>
          <div className="sa-side">{bench && <Benchmark data={bench} />}</div>
        </div>
      </div>
      {opened && <FindingPanel key={opened.ref} finding={opened} canSend={canSend} onClose={close} />}
    </div>
  );
}
