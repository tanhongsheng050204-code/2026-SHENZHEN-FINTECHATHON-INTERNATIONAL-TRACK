import { useEffect, useState } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { AgentCardView } from "../components/AgentCardView";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import { friendlyLoadError } from "../api/client";
import {
  fetchPositions,
  fetchWorkspace,
  ringgit,
  type JobFunction,
  type PositionSummary,
  type PositionWorkspace,
} from "../api/topicE";

export default function Positions() {
  const { t } = useI18n();
  const { show } = useAppState();
  const [positions, setPositions] = useState<PositionSummary[]>([]);
  const [selected, setSelected] = useState<JobFunction | null>(null);
  const [workspace, setWorkspace] = useState<PositionWorkspace | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchPositions()
      .then((list) => {
        if (!active) return;
        setPositions(list);
        const first = list.find((p) => p.job_function === "finance" && p.enabled) ?? list.find((p) => p.enabled);
        setSelected(first?.job_function ?? null);
      })
      .catch((e: Error) => active && setError(friendlyLoadError(e.message)));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!selected) return;
    let active = true;
    fetchWorkspace(selected)
      .then((w) => active && setWorkspace(w))
      .catch((e: Error) => active && setError(friendlyLoadError(e.message)));
    return () => { active = false; };
  }, [selected]);

  const choose = (job: JobFunction) => {
    setWorkspace(null);
    setSelected(job);
  };

  const cash = workspace?.cash_contribution;

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="positions" />
      <AppTopBar current="positions" />
      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.workforce")}</div>
        <h1>{t("nav.positions")}</h1>
        <p>{t("pos.desc")}</p>
      </header>
      <div className="fb-page-body">
        <div className="fb-cash">
          {error && <div className="fb-callout" role="alert">{error}</div>}

          <nav className="fb-inbox-tabs" aria-label="Positions">
            {positions.map((p) => (
              <button
                key={p.job_function}
                type="button"
                aria-current={selected === p.job_function ? "page" : undefined}
                className={(selected === p.job_function ? "is-current" : "") + (p.enabled ? "" : " is-designed")}
                onClick={() => choose(p.job_function)}
              >
                {p.display_name}{!p.enabled && " · designed"}
              </button>
            ))}
          </nav>

          {selected && !workspace && !error && <div className="fb-callout">Loading the workspace…</div>}

          {workspace && (
            <>
              {workspace.data_mode === "stub" && <div className="fb-callout">{t("cash.stub")}</div>}
              <div className="fb-cash-kpis">
                <div className="fb-cash-kpi is-good">
                  <span className="fb-cash-kpi-label">Expected in</span>
                  <span className="fb-cash-kpi-value">{ringgit(cash?.inflow_total ?? "0")}</span>
                  <span className="fb-cash-kpi-sub">Next 90 days, from this position</span>
                </div>
                <div className="fb-cash-kpi is-attn">
                  <span className="fb-cash-kpi-label">Expected out</span>
                  <span className="fb-cash-kpi-value">{ringgit(cash?.outflow_total ?? "0")}</span>
                  <span className="fb-cash-kpi-sub">{Number(cash?.at_risk_total ?? 0) > 0 ? `${ringgit(cash?.at_risk_total ?? "0")} at risk` : "Nothing flagged at risk"}</span>
                </div>
                <button type="button" className="fb-cash-kpi fb-pos-inbox" onClick={() => show("inbox")}>
                  <span className="fb-cash-kpi-label">Waiting for review</span>
                  <span className="fb-cash-kpi-value">{workspace.inbox_count}</span>
                  <span className="fb-cash-kpi-sub">Open review inbox →</span>
                </button>
              </div>

              {workspace.skill_results.length > 0 && (
                <section className="fb-cash-card">
                  <h2>What the agents found</h2>
                  <div className="fb-pos-results">
                    {workspace.skill_results.map((r) => (
                      <div key={r.skill_id} className={"fb-pos-result is-" + r.status}>
                        <span className="fb-cash-kpi-label">{r.title}</span>
                        {r.value && <span className="fb-pos-value">{r.value}</span>}
                        <span className="fb-inbox-muted">{r.summary}</span>
                        {r.evidence.length > 0 && <span className="fb-cash-fx">{r.evidence.map((e) => e.label).join(", ")}</span>}
                      </div>
                    ))}
                  </div>
                </section>
              )}

              <section className="fb-cash-card">
                <h2>{workspace.agents.length === 1 ? "Agent" : "Agents"} for {workspace.display_name}</h2>
                <div className="fb-agent-grid">
                  {workspace.agents.map((a) => <AgentCardView key={a.id} agent={a} />)}
                </div>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
