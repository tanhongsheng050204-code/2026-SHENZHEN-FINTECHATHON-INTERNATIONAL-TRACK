import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  fetchAutomationRuns,
  fetchAutomations,
  removeAutomation,
  runAutomations,
  saveAutomation,
  type Automation,
  type AutomationAction,
  type AutomationRun,
  type AutomationTrigger,
  type SkipReason,
} from "../api/collaboration";
import { ApiError, friendlyLoadError } from "../api/client";
import type { JobFunction } from "../api/topicE";
import { useI18n } from "../lib/i18n";
import { JOB_LABELS } from "../lib/jobFunctions";
import { RecordPanel } from "./RecordPanel";
import "./records.css";

const TRIGGERS: Record<AutomationTrigger, string> = {
  invoice_due_within_days: "An invoice falls due within {n} days",
  invoice_overdue_days: "An invoice is at least {n} days overdue",
  cash_shortfall_within_days: "Cash falls below the minimum within {n} days",
  bill_due_within_days: "A supplier bill falls due within {n} days",
};
const ACTIONS: Record<AutomationAction, string> = {
  draft_reminder: "Draft one reminder per invoice (L2, a person approves)",
  reminder_sequence: "Run a reminder sequence: friendly at N days, firm at N+7, a call at N+21",
  ask_review: "Ask a position to review it (L1)",
};
const INVOICE_TRIGGERS: AutomationTrigger[] = ["invoice_overdue_days", "invoice_due_within_days"];
const SKIPS: Record<SkipReason, string> = {
  on_hold: "{n} on hold: disputed, promised or customer paused",
  waiting_for_decision: "{n} already have a reminder waiting for a person to decide",
  stopped_after_rejection: "{n} stopped because a person rejected a step",
};
const REVIEWERS: JobFunction[] = ["finance", "owner", "operations", "procurement", "sales"];

function errorText(error: unknown): string {
  const code = error instanceof ApiError ? error.code : "";
  if (code === "reminders_need_an_overdue_trigger") return "Payment reminders can only follow an invoice trigger, and a sequence only an overdue one.";
  return friendlyLoadError(code);
}

function allowed(trigger: AutomationTrigger, action: AutomationAction): boolean {
  if (action === "ask_review") return true;
  if (action === "reminder_sequence") return trigger === "invoice_overdue_days";
  return INVOICE_TRIGGERS.includes(trigger);
}

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-MY", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** What one automation did, run by run, and why it skipped what it skipped. */
function RunHistory({ automation, title, onClose }: { automation: Automation; title: string; onClose: () => void }) {
  const { tx } = useI18n();
  const [runs, setRuns] = useState<AutomationRun[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    fetchAutomationRuns(automation.id).then((r) => active && setRuns(r)).catch((e) => active && setError(errorText(e)));
    return () => { active = false; };
  }, [automation.id]);
  return (
    <RecordPanel kicker={tx("Automation · run history")} title={title} onClose={onClose}>
      <p className="rc-note">{tx("A run is kept when it prepared something or skipped for a new reason. Checked every 15 minutes on working days (Monday to Friday); Run now works any day.")}</p>
      {error && <p className="fb-inbox-error" role="alert">{error}</p>}
      {runs === null && !error && <p className="rc-note">{tx("Loading…")}</p>}
      {runs?.length === 0 && <p className="rc-note">{tx("Nothing has happened yet: no invoice has reached this rule.")}</p>}
      {runs && runs.length > 0 && (
        <ol className="rc-timeline">
          {runs.map((run) => (
            <li key={run.at} className={run.proposed.length ? "is-proposed" : undefined}>
              <time dateTime={run.at}>{when(run.at)}</time>
              {run.proposed.length > 0 && <div>{tx("Prepared {n} for review in the review inbox.", { n: run.proposed.length })}</div>}
              {(Object.keys(run.skipped) as SkipReason[]).map((reason) => (
                <div key={reason} className="rc-note">{tx(SKIPS[reason], { n: run.skipped[reason] ?? 0 })}</div>
              ))}
            </li>
          ))}
        </ol>
      )}
    </RecordPanel>
  );
}

/**
 * "When this happens, prepare that." Every automation ends in a proposal in the
 * review inbox; none sends, pays or changes a record by itself.
 */
export function AutomationsPanel({ isOwner, canRun }: { isOwner: boolean; canRun: boolean }) {
  const { tx } = useI18n();
  const [items, setItems] = useState<Automation[]>([]);
  const [trigger, setTrigger] = useState<AutomationTrigger>("invoice_overdue_days");
  const [days, setDays] = useState(14);
  const [action, setAction] = useState<AutomationAction>("draft_reminder");
  const [reviewer, setReviewer] = useState<JobFunction>("finance");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<Automation | null>(null);
  const closeHistory = useCallback(() => setHistory(null), []);

  useEffect(() => {
    let active = true;
    fetchAutomations().then((a) => active && setItems(a)).catch((e) => active && setError(errorText(e)));
    return () => { active = false; };
  }, []);

  const then = (a: Automation) => {
    if (a.action === "ask_review") return tx("ask {who} to review it", { who: tx(JOB_LABELS[a.reviewer]) });
    if (a.action === "reminder_sequence") return tx("run the reminder sequence (friendly, firm, then a call)");
    return a.trigger === "invoice_due_within_days" ? tx("draft a courtesy reminder") : tx("draft one payment reminder");
  };
  const describe = (a: Automation) => `${tx(TRIGGERS[a.trigger], { n: a.days })} → ${then(a)}`;

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      const saved = await saveAutomation({ trigger, days, action, reviewer });
      setItems((list) => [...list, saved]);
    } catch (e) {
      setError(errorText(e));
    }
  };

  const drop = async (id: string) => {
    setError(null);
    try {
      await removeAutomation(id);
      setItems((list) => list.filter((a) => a.id !== id));
    } catch (e) {
      setError(errorText(e));
    }
  };

  const run = async () => {
    setError(null);
    setResult(null);
    try {
      const created = await runAutomations();
      setResult(created.length
        ? tx("{n} proposals are waiting in the review inbox. Nothing has been sent.", { n: created.length })
        : tx("Nothing new matched right now. Open History to see what was skipped and why."));
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <section className="fb-cash-card">
      <h2>{tx("Automations")}</h2>
      <p className="fb-inbox-muted">{tx("When something happens, DuitDuit prepares the next step for a person to approve. None sends, pays or changes anything by itself, and invoices that are disputed, promised or paused are skipped.")}</p>
      <ul className="rc-list">
        {items.length === 0 && <li className="rc-list-empty">{tx("No automations yet.")}</li>}
        {items.map((a) => (
          <li key={a.id}>
            <div className="rc-list-main">
              <strong>{describe(a)}</strong>
              <span><span className={"rc-chip " + (a.enabled ? "is-green" : "")}>{a.enabled ? tx("Active") : tx("Off")}</span></span>
            </div>
            <button type="button" className="rc-mini" onClick={() => setHistory(a)}>{tx("History")}</button>
            {isOwner && <button type="button" className="rc-mini" onClick={() => void drop(a.id)}>{tx("Remove")}</button>}
          </li>
        ))}
      </ul>
      {canRun && items.length > 0 && (
        <div className="fb-assistant-actions">
          <button type="button" className="fb-btn fb-btn-outline" onClick={() => void run()}>{tx("Run now")}</button>
          {result && <span className="fb-inbox-muted" role="status">{result}</span>}
        </div>
      )}
      {isOwner && (
        <form className="fb-cs-subform" onSubmit={(e) => void create(e)}>
          <div className="fb-cash-whatif">
            <label className="fb-cash-field">
              <span>{tx("When")}</span>
              <select value={trigger} onChange={(e) => {
                const next = e.target.value as AutomationTrigger;
                setTrigger(next);
                if (!allowed(next, action)) setAction(INVOICE_TRIGGERS.includes(next) ? "draft_reminder" : "ask_review");
              }}>
                {(Object.keys(TRIGGERS) as AutomationTrigger[]).map((t) => <option key={t} value={t}>{tx(TRIGGERS[t], { n: "N" })}</option>)}
              </select>
            </label>
            <label className="fb-cash-field">
              <span>{tx("N (days)")}</span>
              <input type="number" min={0} max={120} value={days} onChange={(e) => setDays(Math.max(0, Math.min(120, Number(e.target.value) || 0)))} />
            </label>
            <label className="fb-cash-field">
              <span>{tx("Then")}</span>
              <select value={action} onChange={(e) => setAction(e.target.value as AutomationAction)}>
                {(Object.keys(ACTIONS) as AutomationAction[])
                  .filter((a) => allowed(trigger, a))
                  .map((a) => <option key={a} value={a}>{tx(ACTIONS[a])}</option>)}
              </select>
            </label>
            {action === "ask_review" && (
              <label className="fb-cash-field">
                <span>{tx("Who reviews")}</span>
                <select value={reviewer} onChange={(e) => setReviewer(e.target.value as JobFunction)}>
                  {REVIEWERS.map((j) => <option key={j} value={j}>{tx(JOB_LABELS[j])}</option>)}
                </select>
              </label>
            )}
          </div>
          <button className="fb-btn fb-btn-solid fb-team-submit" type="submit">{tx("Add automation")}</button>
        </form>
      )}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
      {history && <RunHistory key={history.id} automation={history} title={describe(history)} onClose={closeHistory} />}
    </section>
  );
}
