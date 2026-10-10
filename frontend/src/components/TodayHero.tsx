import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { canOpen } from "../lib/access";
import { useAppState } from "../lib/appState";
import {
  fetchAnalysis,
  fetchBriefing,
  fetchForecast,
  fetchReviewInbox,
  ringgit,
  type AnalysisResponse,
  type ForecastResponse,
  type ReviewAction,
} from "../api/topicE";

const OPEN = new Set(["pending", "awaiting_second_approval", "edited"]);

function longDate(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-MY", { day: "numeric", month: "short" });
}

/** The 90-day likely balance against the minimum, drawn once when it loads. */
function Runway({ forecast }: { forecast: ForecastResponse }) {
  const W = 420;
  const H = 150;
  const values = forecast.points.map((p) => Number(p.likely));
  const minimum = Number(forecast.minimum_balance);
  const top = Math.max(...values, minimum) * 1.08;
  const bottom = Math.min(0, ...values);
  const x = (day: number) => (day / forecast.horizon_days) * W;
  const y = (v: number) => 8 + (1 - (v - bottom) / (top - bottom)) * (H - 16);
  const path = forecast.points.map((p, i) => `${i ? "L" : "M"}${x(p.day).toFixed(1)},${y(Number(p.likely)).toFixed(1)}`).join("");
  const dip = forecast.shortfall;
  return (
    <svg className="th-runway" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Likely cash balance over the next ${forecast.horizon_days} days against your ${ringgit(forecast.minimum_balance)} minimum`}>
      <rect className="th-runway-zone" x="0" y={y(minimum)} width={W} height={Math.max(0, H - y(minimum))} />
      <line className="th-runway-min" x1="0" x2={W} y1={y(minimum)} y2={y(minimum)} />
      <path className="th-runway-line" d={path} pathLength={1} />
      {dip && <circle className="th-runway-dip" cx={x(dip.day)} cy={y(Number(dip.likely_balance))} r="5" />}
    </svg>
  );
}

/**
 * The top of "Today": the one thing that matters most, said as a sentence, with
 * the two actions that follow from it, then what is waiting, last month's result
 * and today's alerts. Each part shows only what this person's role may see.
 */
export function TodayHero({ greeting }: { greeting: string }) {
  const { show, askAbout, askRole } = useAppState();
  const { identity } = useAuth();
  const role = identity?.role ?? askRole;
  const seesCash = canOpen("cashflow", role);
  const seesAnalysis = canOpen("analysis", role);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [waiting, setWaiting] = useState<ReviewAction[] | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [alerts, setAlerts] = useState<string[] | null>(null);

  useEffect(() => {
    let active = true;
    if (seesCash) fetchForecast(90).then((f) => active && setForecast(f)).catch(() => undefined);
    if (seesAnalysis) fetchAnalysis(3).then((a) => active && setAnalysis(a)).catch(() => undefined);
    fetchReviewInbox()
      .then((r) => active && setWaiting(r.actions.filter((a) => a.can_decide && OPEN.has(a.status))))
      .catch(() => active && setWaiting([]));
    fetchBriefing()
      .then((b) => active && setAlerts(b.lines.filter((l) => l.kind === "alerts").map((l) => l.text)))
      .catch(() => active && setAlerts([]));
    return () => { active = false; };
  }, [seesCash, seesAnalysis]);

  const shortfall = forecast?.shortfall ?? null;
  const last = analysis?.months[analysis.months.length - 1] ?? null;
  const count = waiting?.length ?? 0;
  // The briefing folds today's alerts into one line: "2 alerts: …" or "Alert: …".
  const alertLine = alerts && alerts.length > 0 ? alerts[0] : null;
  const alertCount = alertLine ? Number(/^(\d+) alerts:/.exec(alertLine)?.[1] ?? 1) : 0;
  const alertText = alertLine ? alertLine.replace(/^(\d+ alerts|Alert): /, "") : null;

  let headline: string;
  let detail: string;
  if (shortfall) {
    headline = `Cash falls ${ringgit(shortfall.gap)} below your minimum in ${shortfall.day} days.`;
    detail = `On ${longDate(shortfall.date)} the likely balance is ${ringgit(shortfall.likely_balance)}, under your ${ringgit(shortfall.minimum_balance)} minimum.`;
  } else if (forecast) {
    headline = "Cash stays above your minimum for the next 90 days.";
    detail = `Lowest likely point: ${ringgit(String(Math.min(...forecast.points.map((p) => Number(p.likely)))))}.`;
  } else if (count > 0) {
    headline = `${count} thing${count === 1 ? " is" : "s are"} waiting for your decision.`;
    detail = "Drafts and proposals your role can approve or reject.";
  } else {
    headline = "Nothing needs your decision right now.";
    detail = "New proposals from the agents will appear in your review inbox.";
  }

  return (
    <section className="th" aria-label="Today">
      <div className={"th-lead" + (shortfall ? " is-risk" : "")}>
        <div className="th-lead-copy">
          <p className="th-greeting">{greeting}</p>
          <h2 className="th-headline">{headline}</h2>
          <p className="th-detail">{detail}</p>
          <div className="th-actions">
            {seesCash ? (
              <>
                <button type="button" className="fb-btn fb-btn-solid" onClick={() => show("cashflow")}>See the forecast</button>
                <button type="button" className="fb-btn fb-btn-outline" onClick={() => askAbout("Can I pay everyone this month?")}>Ask what to do</button>
              </>
            ) : (
              <button type="button" className="fb-btn fb-btn-solid" onClick={() => show("inbox")}>Open review inbox</button>
            )}
          </div>
        </div>
        {forecast && <div className="th-lead-chart"><Runway forecast={forecast} /></div>}
      </div>

      <div className="th-tiles">
        <button type="button" className="th-tile" onClick={() => show("inbox")}>
          <span className="th-tile-label">Waiting for you</span>
          <span className="th-tile-value">{waiting === null ? "…" : count === 0 ? "All clear" : count}</span>
          <span className="th-tile-sub">
            {waiting && waiting.length > 0 ? waiting.slice(0, 2).map((a) => a.title).join("; ") : "Nothing to approve"}
          </span>
        </button>
        {seesAnalysis && (
          <button type="button" className="th-tile" onClick={() => show("analysis")}>
            <span className="th-tile-label">{last ? `Net result, ${last.label}` : "Last month"}</span>
            <span className={"th-tile-value" + (last && Number(last.net_result) < 0 ? " is-down" : "")}>{last ? ringgit(last.net_result) : "…"}</span>
            <span className="th-tile-sub">{last ? `${last.net_margin ?? "—"}% of ${ringgit(last.revenue)} revenue` : "Profit and loss from your records"}</span>
          </button>
        )}
        <button type="button" className="th-tile" onClick={() => show(seesCash ? "cashflow" : "inbox")}>
          <span className="th-tile-label">Alerts today</span>
          <span className={"th-tile-value" + (alertCount ? " is-attn" : "")}>{alerts === null ? "…" : alertCount === 0 ? "None" : alertCount}</span>
          <span className="th-tile-sub">{alertText ?? "Rules you set in Company settings"}</span>
        </button>
      </div>
    </section>
  );
}
