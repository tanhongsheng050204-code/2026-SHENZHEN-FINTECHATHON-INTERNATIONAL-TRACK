import type { ReactNode } from "react";
import type { AgentCard } from "../api/topicE";
import { JOB_LABELS } from "../lib/jobFunctions";

const LEVEL_TEXT: Record<AgentCard["autonomy_level"], string> = {
  L0: "L0 · watch only",
  L1: "L1 · drafts for review",
  L2: "L2 · external, owner approves",
  L3: "L3 · money, two approvers",
};

/** One agent: purpose, autonomy, review record and its skills. */
export function AgentCardView({ agent, children }: { agent: AgentCard; children?: ReactNode }) {
  const m = agent.metrics;
  const designed = agent.build_status === "designed";
  return (
    <article className={"fb-agent" + (designed ? " is-designed" : "") + (agent.kill_switch_engaged ? " is-stopped" : "")}>
      <div className="fb-agent-head">
        <h3>{agent.name}</h3>
        <span className={"fb-inbox-level is-" + agent.autonomy_level.toLowerCase()}>{LEVEL_TEXT[agent.autonomy_level]}</span>
      </div>
      <p className="fb-inbox-muted">{agent.purpose}</p>
      <div className="fb-agent-meta">
        {agent.reviewer_job_function && <span>Reviewed by <strong>{JOB_LABELS[agent.reviewer_job_function]}</strong></span>}
        {designed && <span className="fb-inbox-pill is-muted">Designed, not built</span>}
        {agent.kill_switch_engaged && <span className="fb-inbox-pill is-rejected">Stopped</span>}
        {m?.promotion_recommended && <span className="fb-inbox-pill is-can">Ready for more autonomy</span>}
      </div>
      {m && m.proposals > 0 && (
        <div className="fb-agent-record" aria-label="Review record">
          <span><strong>{m.proposals}</strong> proposals</span>
          <span><strong>{m.unedited_approval_rate === null ? "—" : `${Math.round(m.unedited_approval_rate * 100)}%`}</strong> approved unchanged</span>
          <span><strong>{m.approved_edited}</strong> edited</span>
          <span><strong>{m.rejected}</strong> rejected</span>
        </div>
      )}
      {agent.scoped_autonomy.length > 0 && (
        <p className="fb-inbox-muted">
          Earned autonomy: {agent.scoped_autonomy.map((s) => `${s.action.replace(/_/g, " ")} at ${s.level}`).join(", ")}
        </p>
      )}
      <ul className="fb-agent-skills">
        {agent.skills.map((s) => (
          <li key={s.id} className={s.availability === "planned" ? "is-planned" : undefined}>
            <span>{s.name}</span>
            <span className={"fb-inbox-pill " + (s.availability === "available" ? "is-approved" : "is-muted")}>
              {s.availability === "available" ? "Available" : "Planned"}
            </span>
          </li>
        ))}
      </ul>
      {children}
    </article>
  );
}
