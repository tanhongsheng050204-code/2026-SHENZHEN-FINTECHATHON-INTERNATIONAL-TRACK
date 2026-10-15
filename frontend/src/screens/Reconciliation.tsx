import { useEffect, useState } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { SectionTabs } from "../components/SectionTabs";
import { MaskedText } from "../components/MaskedText";
import { useAuth } from "../auth/AuthProvider";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import { focusInboxItem } from "../lib/inboxFocus";
import { friendlyLoadError } from "../api/client";
import { errorCode, ringgit } from "../api/topicE";
import { explainBankLine, fetchReconciliation, type ReconciliationResponse } from "../api/insights";
import "../components/records.css";
import "./SecurityActivity.css";

// A description stored whole as one protected token says nothing to a reader.
const OPAQUE = /^[A-Z]+_[0-9a-f]{10}$/;

function monthBefore(period: string, step: number): string {
  const [y, m] = period.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + step, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

/** Bank lines for one month, each with the record it matches; unmatched ones go to Finance. */
export default function Reconciliation() {
  const { t, tx } = useI18n();
  const { show, askRole } = useAppState();
  const { identity } = useAuth();
  const role = identity?.role ?? askRole;
  const canSend = role === "owner_director" || role === "finance_ops";
  const [period, setPeriod] = useState<string | undefined>(undefined);
  const [sheet, setSheet] = useState<ReconciliationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchReconciliation(period)
      .then((value) => { if (active) { setSheet(value); setError(null); } })
      .catch((e) => active && setError(friendlyLoadError(errorCode(e))));
    return () => { active = false; };
  }, [period]);

  const send = async (ref: string) => {
    setBusy(ref);
    try {
      const actionId = await explainBankLine(ref);
      setSheet((s) => s && { ...s, items: s.items.map((i) => (i.ref === ref ? { ...i, review_action_id: actionId } : i)) });
    } catch (e) {
      setError(friendlyLoadError(errorCode(e)));
    } finally {
      setBusy(null);
    }
  };

  const unmatched = sheet ? sheet.lines - sheet.matched : 0;
  const share = sheet && sheet.lines ? Math.round((sheet.matched / sheet.lines) * 100) : null;

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="reconciliation" />
      <AppTopBar current="reconciliation" />
      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.money")}</div>
        <h1>{t("nav.cashFinance")}</h1>
        <p>{tx("Each bank line for the month, with the record it matches. Lines with no record go to Finance to explain; nothing is changed here.")}</p>
        <SectionTabs section="money" current="reconciliation" />
      </header>
      <div className="fb-page-body">
        {error && <div className="fb-callout" role="alert">{error}</div>}
        {sheet && (
          <>
            <div className="dd-recon-month">
              <button type="button" className="rc-mini" onClick={() => setPeriod(monthBefore(sheet.period, -1))}>{tx("← Previous month")}</button>
              <strong>{sheet.label}</strong>
              <button type="button" className="rc-mini" onClick={() => setPeriod(monthBefore(sheet.period, 1))}>{tx("Next month →")}</button>
            </div>
            <div className="dd-board-summary">
              <div><span>{tx("Bank lines")}</span><strong>{sheet.lines}</strong></div>
              <div><span>{tx("Matched")}</span><strong>{share === null ? tx("Not measured") : `${sheet.matched} · ${share}%`}</strong></div>
              <div><span>{tx("To explain")}</span><strong className={unmatched ? "is-late" : undefined}>{unmatched}</strong></div>
            </div>
          </>
        )}
        <section className="fb-cash-card">
          <div className="sa-head"><h2>{tx("Bank lines")}</h2></div>
          {!sheet && !error && <p className="rc-note">{tx("Checking…")}</p>}
          {sheet && sheet.lines === 0 && <p className="rc-note">{tx("No bank lines for this month. Import a bank statement on Data sources to reconcile it.")}</p>}
          <ul className="rc-list">
            {sheet?.items.map((line) => (
              <li key={line.ref}>
                <span className={"rc-chip " + (line.status === "matched" ? "is-green" : "is-amber")}>
                  {line.status === "matched" ? tx("Matched") : tx("No record")}
                </span>
                <div className="rc-list-main">
                  <strong>{line.matched_to ? tx(line.matched_to) : tx(line.direction === "credit" ? "Money in, no record" : "Money out, no record")}</strong>
                  <span>
                    {new Date(line.posted_on + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" })}
                    {" · "}{line.direction === "credit" ? "+" : "−"}{ringgit(line.amount)}
                    {OPAQUE.test(line.description) ? "" : <> · <MaskedText text={line.description} /></>}
                  </span>
                </div>
                {line.status === "unmatched" && (line.review_action_id ? (
                  <button type="button" className="rc-mini" onClick={() => { focusInboxItem(line.review_action_id!); show("inbox"); }}>{tx("In review inbox →")}</button>
                ) : canSend ? (
                  <button type="button" className="rc-mini" disabled={busy === line.ref} onClick={() => void send(line.ref)}>{busy === line.ref ? tx("Sending…") : tx("Ask Finance to explain")}</button>
                ) : null)}
              </li>
            ))}
          </ul>
          {sheet && <p className="rc-note">{tx("A line matches a settled record in the same direction, for the same amount to the cent, at most {n} days apart. Nothing is matched on a guess.", { n: sheet.window_days })}</p>}
        </section>
      </div>
    </div>
  );
}
