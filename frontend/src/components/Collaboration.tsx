import type { ReactNode } from "react";
import type { JobFunction, ReviewAction } from "../api/topicE";
import { useI18n } from "../lib/i18n";
import { JOB_LABELS } from "../lib/jobFunctions";
import "./Collaboration.css";

// Who is involved in a review item, shown the way a team tool shows it: the agent
// that drafted it, the position that decides, and what has happened so far. Built
// only from the item's own fields; approvers appear by step, never by name or id.

const AGENT_LABELS: Record<string, string> = {
  receivables: "Collections agent",
  financing: "Financing agent",
  cashflow: "Cash-flow agent",
  cash: "Cash-flow agent",
  supervisor: "Supervisor",
};

function agentLabel(agentId: string): string {
  return AGENT_LABELS[agentId] ?? `${agentId.charAt(0).toUpperCase()}${agentId.slice(1).replace(/_/g, " ")} agent`;
}

export function Avatar({ job, label, size = "sm" }: { job?: JobFunction | "agent"; label: string; size?: "sm" | "md" }) {
  return (
    <i className={`dd-avatar is-${job ?? "agent"} is-${size}`} aria-hidden="true" title={label}>
      {job === "agent" || !job ? <AgentGlyph /> : label.charAt(0)}
    </i>
  );
}

function AgentGlyph() {
  return (
    <svg viewBox="0 0 16 16" width="10" height="10" fill="currentColor" aria-hidden="true">
      <path d="M8 1.5l1.6 3.9 3.9 1.6-3.9 1.6L8 12.5 6.4 8.6 2.5 7l3.9-1.6z" />
    </svg>
  );
}

/** Drafted by an agent, decided by a position: two chips joined by an arrow. */
export function Handoff({ action }: { action: ReviewAction }) {
  const reviewer = JOB_LABELS[action.reviewer_job_function];
  return (
    <span className="dd-handoff" aria-label={`Drafted by the ${agentLabel(action.agent_id)}, decided by ${reviewer}`}>
      <Avatar job="agent" label={agentLabel(action.agent_id)} />
      <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true"><path d="M2 6h8M7 3l3 3-3 3" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
      <Avatar job={action.reviewer_job_function} label={reviewer} />
    </span>
  );
}

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-MY", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** What has happened to an item so far, oldest first, and who it is waiting for. */
export function ActivityTimeline({ action }: { action: ReviewAction }) {
  const { tx } = useI18n();
  const reviewer = JOB_LABELS[action.reviewer_job_function];
  const money = action.autonomy_level === "L3";
  const entries: { key: string; avatar: ReactNode; text: string; at?: string; tone?: string }[] = [
    { key: "drafted", avatar: <Avatar job="agent" label={agentLabel(action.agent_id)} />, text: `${agentLabel(action.agent_id)} drafted this`, at: action.created_at },
  ];
  action.approvals.forEach((approval, i) => {
    entries.push({
      key: `approval-${i}`,
      avatar: <Avatar job={i === 0 ? action.reviewer_job_function : "owner"} label={i === 0 ? reviewer : "Owner"} />,
      text: money ? (i === 0 ? `Maker approved (${reviewer})` : "Checker approved, a different person, with an authenticator code") : `Approved by ${reviewer}`,
      at: approval.approved_at,
      tone: i === 1 ? "is-gold" : "is-done",
    });
  });
  if (action.status === "rejected") entries.push({ key: "rejected", avatar: <Avatar job={action.reviewer_job_function} label={reviewer} />, text: `Rejected by ${reviewer}`, tone: "is-stop" });
  if (action.status === "edited") entries.push({ key: "edited", avatar: <Avatar job={action.reviewer_job_function} label={reviewer} />, text: `Edited and approved by ${reviewer}`, tone: "is-done" });
  if (action.status === "approved" && action.approvals.length === 0) entries.push({ key: "approved", avatar: <Avatar job={action.reviewer_job_function} label={reviewer} />, text: `Approved by ${reviewer}`, tone: "is-done" });
  if (action.status === "pending" || action.status === "awaiting_second_approval") {
    const waitingFor = action.status === "awaiting_second_approval" ? "a checker: a different person, with an authenticator code" : reviewer;
    entries.push({ key: "waiting", avatar: <Avatar job={action.status === "awaiting_second_approval" ? "owner" : action.reviewer_job_function} label={reviewer} />, text: `Waiting for ${waitingFor}`, tone: "is-waiting" });
  }

  return (
    <ol className="dd-timeline" aria-label={tx("Activity")}>
      {entries.map((e) => (
        <li key={e.key} className={e.tone}>
          {e.avatar}
          <span className="dd-timeline-text">{tx(e.text)}</span>
          {e.at && <time dateTime={e.at}>{when(e.at)}</time>}
        </li>
      ))}
    </ol>
  );
}
