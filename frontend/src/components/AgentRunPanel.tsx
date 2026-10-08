import { useState, type FormEvent } from "react";
import { useAppState } from "../lib/appState";
import { friendlyLoadError } from "../api/client";
import { errorCode, runAgents, type AgentRunEvent } from "../api/topicE";

// Goals the built agents can route: cash, collections and financing.
const EXAMPLE_GOALS = ["Can I cover payroll this month?", "Which customers are late paying?", "Which loans can we apply for?"];

/**
 * Hand a goal to the agents: the supervisor plans, the agents propose, and the
 * steps stream in as they happen. Proposals land in the review inbox; nothing
 * is sent or paid until a person approves.
 */
export function AgentRunPanel({ compact = false }: { compact?: boolean }) {
  const { show } = useAppState();
  const [goal, setGoal] = useState("Can I cover payroll this month?");
  const [events, setEvents] = useState<AgentRunEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (event: FormEvent) => {
    event.preventDefault();
    setRunning(true);
    setEvents([]);
    setError(null);
    try {
      await runAgents(goal, (e) => setEvents((list) => [...list, e]));
    } catch (e) {
      setError(friendlyLoadError(errorCode(e)));
    } finally {
      setRunning(false);
    }
  };

  const proposals = events.filter((e) => e.action_id !== null).length;

  return (
    <section className={"fb-cash-card fb-run-panel" + (compact ? " is-compact" : "")} aria-labelledby="fb-run-title">
      <h2 id="fb-run-title">Have the agents work on it</h2>
      <p className="fb-inbox-muted">Ask a question in the chat below for an answer. Give the agents a goal here and they prepare the work for you to review.</p>
      <form className="fb-cash-whatif" onSubmit={(e) => void run(e)}>
        <label className="fb-cash-field fb-agent-goal">
          <span>Goal</span>
          <input value={goal} maxLength={500} onChange={(e) => setGoal(e.target.value)} />
        </label>
        <button className="fb-btn fb-btn-solid" type="submit" disabled={running || goal.trim() === ""}>{running ? "Working…" : "Run"}</button>
      </form>
      <div className="fb-pos-tools" aria-label="Example goals">
        {EXAMPLE_GOALS.map((example) => (
          <button key={example} type="button" className="fb-pos-tool" disabled={running} onClick={() => setGoal(example)}>{example}</button>
        ))}
      </div>
      {error &&<div className="fb-inbox-error" role="alert">{error}</div>}
      {events.length > 0 && (
        <ol className="fb-agent-run" aria-live="polite">
          {events.map((e) => (
            <li key={e.sequence} className={"is-" + e.type}>
              <strong>{e.agent_id.replace(/_/g, " ")}</strong> · {e.message}
            </li>
          ))}
        </ol>
      )}
      {!running && proposals > 0 && (
        <div className="fb-fin-done">
          {proposals} proposal{proposals === 1 ? "" : "s"} waiting for review.{" "}
          <button type="button" className="fb-cash-more" onClick={() => show("inbox")}>Open review inbox</button>
        </div>
      )}
    </section>
  );
}
