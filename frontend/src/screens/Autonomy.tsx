import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { AgentCardView } from "../components/AgentCardView";
import { useAuth } from "../auth/AuthProvider";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import { JOB_LABELS } from "../lib/jobFunctions";
import { ApiError, friendlyLoadError } from "../api/client";
import {
  changeAutonomy,
  fetchAgents,
  fetchJourney,
  setKillSwitch,
  type AgentCard,
  type AgentListResponse,
  type JourneyResponse,
} from "../api/topicE";

const RUN_ROLES = new Set(["finance_ops", "owner_director"]);
const KILL_SWITCH_ROLES = new Set(["owner_director", "compliance"]);

// The external action each agent would take on its own once promoted to L2.
const PROMOTABLE_ACTION: Record<string, { action: string; label: string }> = {
  receivables: { action: "send_reminder", label: "send approved reminders" },
  customer_service: { action: "send_reply", label: "send replies" },
  sales: { action: "send_followup", label: "send follow-ups" },
};

const AUTONOMY_ERRORS: Record<string, string> = {
  promotion_not_recommended: "This agent hasn't earned it yet: its review record is not strong enough.",
  l3_not_delegable: "Money movement always needs two people; it can't be delegated.",
  agent_not_promotable: "This agent can't be promoted.",
};

const LADDER = [
  { level: "L0", name: "Watch", who: "Reads and reports only" },
  { level: "L1", name: "Draft", who: "The position holder reviews" },
  { level: "L2", name: "External", who: "The owner approves" },
  { level: "L3", name: "Money", who: "A maker, then a different checker" },
];

function errorText(error: unknown): string {
  const code = error instanceof ApiError ? error.code : error instanceof Error ? error.message : "";
  return AUTONOMY_ERRORS[code] ?? friendlyLoadError(code);
}

function Promote({ agent, onChange }: { agent: AgentCard; onChange: (a: AgentCard) => void }) {
  const target = PROMOTABLE_ACTION[agent.id];
  const [limit, setLimit] = useState("5000.00");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!target || !agent.metrics?.promotion_recommended) return null;
  if (agent.scoped_autonomy.some((s) => s.action === target.action)) return null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onChange(await changeAutonomy(agent.id, target.action, "L2", limit || null));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="fb-agent-promote" onSubmit={(e) => void submit(e)}>
      <span>Let it {target.label} on its own, up to</span>
      <label className="fb-cash-field">
        <span className="fb-sr-only">Limit in ringgit</span>
        <input inputMode="decimal" value={limit} onChange={(e) => setLimit(e.target.value.replace(/[^0-9.]/g, ""))} aria-label="Limit in ringgit" />
      </label>
      <button className="fb-btn fb-btn-solid" type="submit" disabled={busy}>{busy ? "Saving…" : "Grant L2"}</button>
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
    </form>
  );
}

export default function Autonomy() {
  const { t } = useI18n();
  const { show } = useAppState();
  const { identity } = useAuth();
  const role = identity?.role ?? "";
  const [data, setData] = useState<AgentListResponse | null>(null);
  const [journey, setJourney] = useState<JourneyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([fetchAgents(), fetchJourney()])
      .then(([a, j]) => { if (active) { setData(a); setJourney(j); } })
      .catch((e) => active && setError(errorText(e)));
    return () => { active = false; };
  }, []);

  const hoursSaved = useMemo(
    () => journey?.functions.flatMap((f) => f.agents).reduce((sum, a) => sum + a.estimated_hours_saved, 0) ?? 0,
    [journey],
  );

  const toggleAll = async () => {
    if (!data) return;
    setBusy(true);
    try {
      setData(await setKillSwitch(!data.global_kill_switch_engaged));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleOne = async (agent: AgentCard) => {
    try {
      const next = await setKillSwitch(!agent.kill_switch_engaged, agent.id);
      setData((d) => (d ? { ...d, agents: d.agents.map((a) => (a.id === agent.id ? next.agents.find((x) => x.id === agent.id) ?? a : a)) } : d));
    } catch (e) {
      setError(errorText(e));
    }
  };

  const replace = (agent: AgentCard) =>
    setData((d) => (d ? { ...d, agents: d.agents.map((a) => (a.id === agent.id ? agent : a)) } : d));

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="autonomy" />
      <AppTopBar current="autonomy" />
      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.company")}</div>
        <h1>{t("nav.autonomy")}</h1>
        <p>{t("auto.desc")}</p>
      </header>
      <div className="fb-page-body">
        <div className="fb-cash">
          {error && <div className="fb-callout" role="alert">{error}</div>}
          {data?.data_mode === "stub" && <div className="fb-callout">{t("cash.stub")}</div>}

          {data && KILL_SWITCH_ROLES.has(role) && (
            <div className={"fb-agent-killswitch" + (data.global_kill_switch_engaged ? " is-engaged" : "")}>
              <span>
                <strong>{data.global_kill_switch_engaged ? "All agents are stopped." : "All agents are running."}</strong>{" "}
                Stopping them leaves your data untouched; people keep working as before.
              </span>
              <button className={"fb-btn " + (data.global_kill_switch_engaged ? "fb-btn-solid" : "fb-btn-outline fb-fin-revoke")} type="button" disabled={busy} onClick={() => void toggleAll()}>
                {data.global_kill_switch_engaged ? "Restart all agents" : "Stop all agents"}
              </button>
            </div>
          )}

          <section className="fb-cash-card" aria-label="Autonomy ladder">
            <h2>How much each agent may do</h2>
            <ol className="fb-agent-ladder">
              {LADDER.map((l) => (
                <li key={l.level} className={"is-" + l.level.toLowerCase()}>
                  <strong>{l.level} · {l.name}</strong>
                  <span>{l.who}</span>
                </li>
              ))}
            </ol>
            <p className="fb-inbox-muted">Agents earn autonomy from their review record. The owner grants it one action at a time, with a limit; money movement is never delegated.</p>
          </section>

          {journey && (
            <div className="fb-cash-kpis">
              <div className="fb-cash-kpi is-good">
                <span className="fb-cash-kpi-label">Estimated hours saved</span>
                <span className="fb-cash-kpi-value">{hoursSaved.toFixed(1)} h</span>
                <span className="fb-cash-kpi-sub">{journey.estimate_note}</span>
              </div>
              <div className="fb-cash-kpi is-attn">
                <span className="fb-cash-kpi-label">Agents</span>
                <span className="fb-cash-kpi-value">{data?.agents.filter((a) => a.build_status === "built").length ?? "—"} built</span>
                <span className="fb-cash-kpi-sub">{data?.agents.filter((a) => a.build_status === "designed").length ?? 0} designed for later</span>
              </div>
            </div>
          )}

          {RUN_ROLES.has(role) && (
            <div className="fb-callout">
              Agents take goals from <button type="button" className="fb-cash-more" onClick={() => show("agents")}>Ask FinBrain</button>, where their work streams in as it happens.
            </div>
          )}

          {data && (
            <section className="fb-cash-card">
              <h2>Every agent</h2>
              <div className="fb-agent-grid">
                {data.agents.map((agent) => (
                  <AgentCardView key={agent.id} agent={agent}>
                    <div className="fb-agent-foot">
                      {agent.job_function && <span className="fb-inbox-muted">Works for {JOB_LABELS[agent.job_function]}</span>}
                      {KILL_SWITCH_ROLES.has(role) && agent.build_status === "built" && (
                        <button className="fb-cash-more" type="button" onClick={() => void toggleOne(agent)}>
                          {agent.kill_switch_engaged ? "Restart this agent" : "Stop this agent"}
                        </button>
                      )}
                    </div>
                    {role === "owner_director" && <Promote agent={agent} onChange={replace} />}
                  </AgentCardView>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
