import { useEffect, useRef, useState } from "react";
import { useAppState } from "../lib/appState";
import { BriefingCard } from "./BriefingCard";
import { SCREENS, type Screen } from "../lib/screens";
import { friendlyLoadError } from "../api/client";
import {
  decideReviewAction,
  errorCode,
  ringgit,
  runAgents,
  runPlaybook,
  type AgentRunEvent,
  type AssistantPlan,
  type PlaybookId,
  type PlaybookResult,
} from "../api/topicE";

const LEVEL_TEXT: Record<string, string> = {
  L1: "Draft",
  L2: "External action",
  L3: "Money movement",
};

/**
 * Carries out what DuitDuit understood, the way the person agreed to:
 * pages open, goals stream from the agents, and inbox decisions wait for an
 * explicit Confirm. Money items also go through the authenticator step-up
 * that the decision endpoint requires.
 */
export function AssistantReply({ plan, onNavigate }: { plan: AssistantPlan; onNavigate?: () => void }) {
  const { show } = useAppState();
  const started = useRef(false);

  useEffect(() => {
    if (plan.kind !== "navigate" || !plan.screen || started.current) return;
    started.current = true;
    if (!(SCREENS as readonly string[]).includes(plan.screen)) return;
    const timer = window.setTimeout(() => {
      onNavigate?.();
      show(plan.screen as Screen);
    }, 700);
    return () => window.clearTimeout(timer);
  }, [plan, show, onNavigate]);

  if (plan.kind === "run_goal" && plan.goal) return <GoalRun goal={plan.goal} message={plan.message} />;
  if (plan.kind === "decide") return <DecisionCard plan={plan} />;
  if (plan.kind === "briefing") return <BriefingCard onNavigate={onNavigate} />;
  if (plan.kind === "playbook" && plan.playbook) return <PlaybookCard key={plan.playbook} id={plan.playbook} onNavigate={onNavigate} />;
  return (
    <div className="fb-assistant">
      <p>{plan.message}</p>
    </div>
  );
}

const STEP_STATUS = { done: "Done", attention: "Needs you", not_measured: "Not measured" };
// The step whose answer is the point of the playbook, shown first as its headline.
const HEADLINE_STEP: Partial<Record<PlaybookId, string>> = {
  bank_meeting: "Cash forecast",
  chase_late_payers: "Receivables",
  pay_everyone: "Can we pay?",
};
const SCREEN_LABEL: Record<string, string> = {
  cashflow: "Open Cash & finance",
  financing: "Open Financing & Passport",
  inbox: "Open review inbox",
};

/** A playbook may prepare inbox proposals; it never decides or sends them. */
export function PlaybookCard({ id, onNavigate }: { id: PlaybookId; onNavigate?: () => void }) {
  const { show } = useAppState();
  const [result, setResult] = useState<PlaybookResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<Promise<PlaybookResult> | null>(null);

  useEffect(() => {
    let active = true;
    // Reuse the request when StrictMode reattaches the effect. No extra draft POST.
    request.current ??= runPlaybook(id);
    request.current.then((value) => active && setResult(value))
      .catch((e) => active && setError(friendlyLoadError(errorCode(e))));
    return () => { active = false; };
  }, [id]);

  const open = (screen: string) => {
    if (!(SCREENS as readonly string[]).includes(screen)) return;
    onNavigate?.();
    show(screen as Screen);
  };

  if (error) return <div className="fb-inbox-error" role="alert">{error} Open the review inbox to check whether any drafts were prepared before the error.</div>;
  if (!result) return <p className="fb-inbox-muted" role="status">Preparing your playbook…</p>;

  const headline = result.steps.find((step) => step.label === HEADLINE_STEP[result.playbook]);
  const count = (status: string) => result.steps.filter((step) => step.status === status).length;
  const drafts = result.inbox_item_ids.length;
  const showNext = result.next_screen && !(result.next_screen === "inbox" && drafts > 0);

  return (
    <div className="fb-assistant fb-playbook" role="region" aria-label={result.title}>
      <p className="fb-playbook-title"><strong>{result.title}</strong></p>
      <p className={"fb-playbook-headline is-" + (headline?.status ?? (count("attention") ? "attention" : "done"))}>
        {headline
          ? headline.text
          : `${count("done")} of ${result.steps.length} checks done · ${count("attention")} need you · ${count("not_measured")} not measured`}
      </p>
      <p className="fb-inbox-muted">{result.synthetic && <strong>Synthetic demo data · </strong>}{result.data_note}</p>
      <ol className="fb-playbook-steps">
        {result.steps.filter((step) => step !== headline).map((step) => (
          <li key={step.label} className={`is-${step.status}`}>
            <div><strong>{step.label}</strong><span className={`fb-playbook-status is-${step.status}`}>{STEP_STATUS[step.status]}</span></div>
            <p>{step.text}</p>
          </li>
        ))}
      </ol>
      <div className="fb-assistant-actions">
        {drafts > 0 && <button type="button" className="fb-btn fb-btn-solid" onClick={() => open("inbox")}>Review {drafts} draft{drafts === 1 ? "" : "s"} in the inbox →</button>}
        {showNext && <button type="button" className="fb-btn fb-btn-outline" onClick={() => open(result.next_screen!)}>{SCREEN_LABEL[result.next_screen!] ?? "Open"} →</button>}
      </div>
    </div>
  );
}

function GoalRun({ goal, message }: { goal: string; message: string }) {
  const { show } = useAppState();
  const [events, setEvents] = useState<AgentRunEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    runAgents(goal, (event) => setEvents((list) => [...list, event]))
      .catch((e) => setError(friendlyLoadError(errorCode(e))))
      .finally(() => setDone(true));
  }, [goal]);

  const inInbox = events.filter((e) => e.action_id).length;
  return (
    <div className="fb-assistant">
      <p>{message}</p>
      <ol className="fb-agent-run" aria-live="polite">
        {events.map((e) => (
          <li key={e.sequence} className={"is-" + e.type}>
            <strong>{e.agent_id.replace(/_/g, " ")}</strong> · {e.message}
          </li>
        ))}
      </ol>
      {!done && events.length === 0 && <p className="fb-inbox-muted">The agents are working…</p>}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
      {done && inInbox > 0 && (
        <button type="button" className="fb-cash-more" onClick={() => show("inbox")}>Review {inInbox} item{inInbox === 1 ? "" : "s"} →</button>
      )}
    </div>
  );
}

type ItemState = "waiting" | "working" | "done" | "failed";

function DecisionCard({ plan }: { plan: AssistantPlan }) {
  const [state, setState] = useState<"ask" | "running" | "finished" | "cancelled">("ask");
  const [results, setResults] = useState<Record<string, { state: ItemState; note?: string }>>({});
  const verb = plan.decision === "reject" ? "Reject" : "Approve";

  const confirm = async () => {
    setState("running");
    for (const item of plan.items) {
      setResults((r) => ({ ...r, [item.id]: { state: "working" } }));
      try {
        const response = await decideReviewAction(item.id, {
          decision: plan.decision ?? "approve",
          reason: "Confirmed by the person through the DuitDuit assistant",
        });
        setResults((r) => ({ ...r, [item.id]: { state: "done", note: response.action.status.replace(/_/g, " ") } }));
      } catch (e) {
        setResults((r) => ({ ...r, [item.id]: { state: "failed", note: friendlyLoadError(errorCode(e)) } }));
      }
    }
    setState("finished");
  };

  return (
    <div className="fb-assistant fb-assistant-confirm" role="group" aria-label={`${verb} ${plan.items.length} items`}>
      <p>{plan.message}</p>
      <ul className="fb-assistant-items">
        {plan.items.map((item) => (
          <li key={item.id}>
            <span className={"fb-inbox-level is-" + item.autonomy_level.toLowerCase()}>{item.autonomy_level} · {LEVEL_TEXT[item.autonomy_level] ?? "Review"}</span>
            <span className="fb-assistant-item-title">{item.title}</span>
            {item.amount && <span className="fb-inbox-muted">{ringgit(item.amount)}</span>}
            {results[item.id] && (
              <span className={"fb-assistant-result is-" + results[item.id].state}>
                {results[item.id].state === "working" ? "…" : results[item.id].note}
              </span>
            )}
          </li>
        ))}
      </ul>
      {plan.needs_step_up && state === "ask" && (
        <p className="fb-inbox-muted">Money items also ask for your authenticator code. A second person still has to check them.</p>
      )}
      {state === "ask" && (
        <div className="fb-assistant-actions">
          <button type="button" className="fb-btn fb-btn-solid" onClick={() => void confirm()}>Confirm: {verb.toLowerCase()} {plan.items.length}</button>
          <button type="button" className="fb-btn fb-btn-outline" onClick={() => setState("cancelled")}>Cancel</button>
        </div>
      )}
      {state === "cancelled" && <p className="fb-inbox-muted">Cancelled. Nothing was changed.</p>}
      {state === "finished" && <p className="fb-inbox-muted">Done. Each decision is recorded as yours.</p>}
    </div>
  );
}
