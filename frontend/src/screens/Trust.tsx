import { useEffect, useState } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { SectionTabs } from "../components/SectionTabs";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import { friendlyLoadError } from "../api/client";
import { fetchGuardrailEvents, fetchPosture, type GuardrailEvent, type PostureResponse } from "../api/topicE";

// OWASP Top 10 for Agentic Applications (2026) codes used by the guardrails.
const OWASP_NAMES: Record<string, string> = {
  ASI01: "Agent goal hijack",
  ASI02: "Tool misuse and exploitation",
  ASI03: "Identity and privilege abuse",
  ASI04: "Agentic supply chain vulnerabilities",
  ASI05: "Unexpected code execution",
  ASI06: "Memory and context poisoning",
  ASI07: "Insecure inter-agent communication",
  ASI08: "Cascading failures",
  ASI09: "Human–agent trust exploitation",
  ASI10: "Rogue agents",
};

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-MY", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function Trust() {
  const { t } = useI18n();
  const { show } = useAppState();
  const [posture, setPosture] = useState<PostureResponse | null>(null);
  const [events, setEvents] = useState<GuardrailEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([fetchPosture(), fetchGuardrailEvents()])
      .then(([p, e]) => { if (active) { setPosture(p); setEvents(e); } })
      .catch((e: Error) => active && setError(friendlyLoadError(e.message)));
    return () => { active = false; };
  }, []);

  const attention = posture?.metrics.filter((m) => m.status !== "good").length ?? 0;
  const scoreTone =!posture ? "" : posture.score >= 85 ? "is-good" : posture.score >= 65 ? "is-attn" : "is-danger";

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="trust" />
      <AppTopBar current="trust" />
      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.company")}</div>
        <h1>{t("nav.trustAudit")}</h1>
        <p>{t("trust.desc")}</p>
        <SectionTabs section="trust" current="trust" />
      </header>
      <div className="fb-page-body">
        <div className="fb-cash">
          {error && <div className="fb-callout" role="alert">{error}</div>}
          {posture?.data_mode === "stub" && <div className="fb-callout">{t("cash.stub")}</div>}
          {posture && (
            <>
              <div className="fb-trust-top">
                <div className={"fb-cash-kpi fb-trust-score " + scoreTone}>
                  <span className="fb-cash-kpi-label">Security posture</span>
                  <span className="fb-cash-kpi-value">{posture.score}<small>/100</small></span>
                  <span className="fb-cash-kpi-sub">{attention === 0 ? "Every control is in place" : `${attention} control${attention === 1 ? " needs" : "s need"} attention`}</span>
                </div>
                <section className="fb-cash-card fb-trust-metrics">
                  <h2>Controls</h2>
                  <ul>
                    {posture.metrics.map((m) => (
                      <li key={m.key} className={"is-" + m.status}>
                        <span className="fb-trust-dot" aria-hidden="true" />
                        <span className="fb-trust-metric">
                          <span><strong>{m.label}</strong> · {m.value}</span>
                          <span className="fb-inbox-muted">{m.detail}</span>
                        </span>
                        {m.key === "inactive_accounts" && m.status !== "good" && (
                          <button className="fb-cash-more" type="button" onClick={() => show("team")}>Review on Team</button>
                        )}
                        <span className="fb-sr-only">{m.status === "good" ? "Good" : m.status === "attention" ? "Needs attention" : "At risk"}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              </div>

              <section className="fb-cash-card">
                <h2>What the guardrails stopped</h2>
                <p className="fb-inbox-muted">Each event is tagged with its OWASP Top 10 for Agentic Applications code.</p>
                {events.length === 0 && <p className="fb-inbox-muted">Nothing blocked recently.</p>}
                <ol className="fb-trust-events">
                  {events.map((e) => (
                    <li key={e.id}>
                      <div className="fb-trust-event-head">
                        <span className="fb-trust-code" title={OWASP_NAMES[e.owasp_code]}>{e.owasp_code}</span>
                        <span className={"fb-inbox-pill " + (e.outcome === "blocked" ? "is-approved" : e.outcome === "quarantined" ? "is-can" : "is-rejected")}>{e.outcome}</span>
                        <span className="fb-inbox-muted">{when(e.occurred_at)}{e.agent_id && ` · ${e.agent_id.replace(/_/g, " ")} agent`}</span>
                      </div>
                      <strong>{e.title}</strong>
                      <span className="fb-inbox-muted">{e.detail}</span>
                      <span className="fb-cash-fx">{OWASP_NAMES[e.owasp_code] ?? e.owasp_code}</span>
                    </li>
                  ))}
                </ol>
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
