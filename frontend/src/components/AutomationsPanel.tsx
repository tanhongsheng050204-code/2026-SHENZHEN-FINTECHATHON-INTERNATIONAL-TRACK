import { useEffect, useState, type FormEvent } from "react";
import {
  fetchAutomations,
  removeAutomation,
  runAutomations,
  saveAutomation,
  type Automation,
  type AutomationAction,
  type AutomationTrigger,
} from "../api/collaboration";
import { ApiError, friendlyLoadError } from "../api/client";
import type { JobFunction } from "../api/topicE";
import { useI18n } from "../lib/i18n";
import { JOB_LABELS } from "../lib/jobFunctions";

const TRIGGERS: Record<AutomationTrigger, string> = {
  invoice_overdue_days: "An invoice is at least {n} days overdue",
  cash_shortfall_within_days: "Cash falls below the minimum within {n} days",
  bill_due_within_days: "A supplier bill falls due within {n} days",
};
const ACTIONS: Record<AutomationAction, string> = {
  draft_reminder: "Draft a payment reminder (L2, the owner approves)",
  ask_review: "Ask a position to review it (L1)",
};
const REVIEWERS: JobFunction[] = ["finance", "owner", "operations", "procurement", "sales"];

function errorText(error: unknown): string {
  const code = error instanceof ApiError ? error.code : "";
  if (code === "reminders_need_an_overdue_trigger") return "Payment reminders can only follow an overdue invoice.";
  return friendlyLoadError(code);
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

  useEffect(() => {
    let active = true;
    fetchAutomations().then((a) => active && setItems(a)).catch((e) => active && setError(errorText(e)));
    return () => { active = false; };
  }, []);

  const describe = (a: Automation) =>
    `${tx("When")} ${tx(TRIGGERS[a.trigger], { n: a.days }).toLowerCase()} → ${a.action === "draft_reminder" ? tx("draft a payment reminder") : tx("ask {who} to review it", { who: tx(JOB_LABELS[a.reviewer]) })}`;

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
        : tx("Nothing new matched right now."));
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <section className="fb-cash-card">
      <h2>{tx("Automations")}</h2>
      <p className="fb-inbox-muted">{tx("When something happens, DuitDuit prepares the next step for a person to approve. Automations are checked every 15 minutes; none sends, pays or changes anything by itself.")}</p>
      {items.length === 0 ? (
        <p className="fb-inbox-muted">{tx("No automations yet.")}</p>
      ) : (
        <ul className="fb-fin-items">
          {items.map((a) => (
            <li key={a.id}>
              <span><strong>{describe(a)}</strong></span>
              {isOwner && <button type="button" className="fb-btn fb-btn-outline fb-fin-revoke" onClick={() => void drop(a.id)}>{tx("Remove")}</button>}
            </li>
          ))}
        </ul>
      )}
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
                if (next !== "invoice_overdue_days") setAction("ask_review");
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
                  .filter((a) => a === "ask_review" || trigger === "invoice_overdue_days")
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
    </section>
  );
}
