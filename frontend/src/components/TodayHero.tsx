import { useEffect, useState, type FormEvent } from "react";
import "./TodayHero.css";
import { useAuth } from "../auth/AuthProvider";
import { canOpen } from "../lib/access";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
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
  const { tx } = useI18n();
  const { identity } = useAuth();
  const role = identity?.role ?? askRole;
  const seesCash = canOpen("cashflow", role);
  const seesAnalysis = canOpen("analysis", role);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [waiting, setWaiting] = useState<ReviewAction[] | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [alerts, setAlerts] = useState<string[] | null>(null);
  // What could not be loaded: never shown as "all clear" or "none".
  const [failed, setFailed] = useState<Set<"forecast" | "analysis" | "waiting" | "alerts">>(new Set());
  const [attempt, setAttempt] = useState(0);
  const [question, setQuestion] = useState("");

  useEffect(() => {
    let active = true;
    const fail = (part: "forecast" | "analysis" | "waiting" | "alerts") => () => {
      if (active) setFailed((current) => new Set(current).add(part));
    };
    if (seesCash) fetchForecast(90).then((f) => active && setForecast(f)).catch(fail("forecast"));
    if (seesAnalysis) fetchAnalysis(3).then((a) => active && setAnalysis(a)).catch(fail("analysis"));
    fetchReviewInbox()
      .then((r) => active && setWaiting(r.actions.filter((a) => a.can_decide && OPEN.has(a.status))))
      .catch(fail("waiting"));
    fetchBriefing()
      .then((b) => active && setAlerts(b.lines.filter((l) => l.kind === "alerts").map((l) => l.text)))
      .catch(fail("alerts"));
    return () => { active = false; };
  }, [seesCash, seesAnalysis, attempt]);

  const retry = () => {
    setFailed(new Set());
    setAttempt((n) => n + 1);
  };
  const notLoaded = tx("Couldn't load");

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
    headline = tx("Cash falls {gap} below your minimum in {n} days.", { gap: ringgit(shortfall.gap), n: shortfall.day });
    detail = tx("On {date} the likely balance is {balance}, under your {minimum} minimum.", { date: longDate(shortfall.date), balance: ringgit(shortfall.likely_balance), minimum: ringgit(shortfall.minimum_balance) });
  } else if (forecast) {
    headline = tx("Cash stays above your minimum for the next 90 days.");
    detail = tx("Lowest likely point: {amount}.", { amount: ringgit(String(Math.min(...forecast.points.map((p) => Number(p.likely))))) });
  } else if (failed.has("forecast")) {
    headline = tx("The cash forecast didn't load.");
    detail = tx("Your numbers are safe. Try again in a moment.");
  } else if (seesCash) {
    headline = tx("Checking your cash outlook…");
    detail = tx("The 90-day forecast from your records.");
  } else if (count > 0) {
    headline = count === 1 ? tx("1 thing is waiting for your decision.") : tx("{n} things are waiting for your decision.", { n: count });
    detail = tx("Drafts and proposals your role can approve or reject.");
  } else if (failed.has("waiting")) {
    headline = tx("Your review inbox didn't load.");
    detail = tx("Your numbers are safe. Try again in a moment.");
  } else if (waiting === null) {
    headline = tx("Checking what is waiting for you…");
    detail = tx("Drafts and proposals your role can approve or reject.");
  } else {
    headline = tx("Nothing needs your decision right now.");
    detail = tx("New proposals from the agents will appear in your review inbox.");
  }

  const suggestions = seesCash
    ? ["Can I pay everyone this month?", "Prepare me for the bank meeting", "Chase the late payers", "Close the month"].map((s) => tx(s))
    : ["What needs me today?", "Show my customers"].map((s) => tx(s));

  const ask = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = question.trim();
    if (text) askAbout(text);
  };

  return (
    <section className="th" aria-label="Today">
      <div className="th-ask-block">
        <h1 className="th-hello">{greeting}</h1>
        <form className="th-ask" onSubmit={ask} role="search" aria-label="Ask DuitDuit">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={tx("Ask DuitDuit, or tell it what to prepare")}
            aria-label={tx("Ask DuitDuit, or tell it what to prepare")}
            maxLength={500}
          />
          <button type="submit" aria-label={tx("Ask")} disabled={!question.trim()}>
            <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M8 13V3M3.5 7.5 8 3l4.5 4.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </button>
        </form>
        <div className="th-suggest" aria-label={tx("Suggestions")}>
          {suggestions.map((text) => (
            <button key={text} type="button" onClick={() => askAbout(text)}>{text}</button>
          ))}
        </div>
      </div>

      <div className={"th-lead" + (shortfall ? " is-risk" : "")}>
        <div className="th-lead-copy">
          <p className={"th-status" + (shortfall ? " is-risk" : "")}><i aria-hidden="true" />{shortfall ? tx("Below your minimum in {n} days", { n: shortfall.day }) : tx("Cash outlook")}</p>
          <h2 className="th-headline">{headline}</h2>
          <p className="th-detail">{detail}</p>
          <div className="th-actions">
            {seesCash ? (
              <>
                <button type="button" className="fb-btn fb-btn-solid" onClick={() => show("cashflow")}>{tx("See the forecast")}</button>
                <button type="button" className="fb-btn fb-btn-outline" onClick={() => askAbout(tx("Can I pay everyone this month?"))}>{tx("Ask what to do")}</button>
              </>
            ) : (
              <button type="button" className="fb-btn fb-btn-solid" onClick={() => show("inbox")}>{tx("Open review inbox")}</button>
            )}
            {failed.size > 0 && (
              <button type="button" className="fb-btn fb-btn-outline" onClick={retry}>{tx("Try again")}</button>
            )}
          </div>
        </div>
        {forecast && <div className="th-lead-chart"><Runway forecast={forecast} /></div>}
      </div>

      <div className="th-tiles">
        <button type="button" className="th-tile" onClick={() => show("inbox")}>
          <span className="th-tile-label">{tx("Waiting for you")}</span>
          <span className={"th-tile-value" + (failed.has("waiting") && waiting === null ? " is-attn" : "")}>
            {waiting === null ? (failed.has("waiting") ? notLoaded : "…") : count === 0 ? tx("All clear") : count}
          </span>
          <span className="th-tile-sub">
            {waiting === null
              ? (failed.has("waiting") ? tx("Open the review inbox to check") : tx("Checking your review inbox"))
              : waiting.length > 0 ? waiting.slice(0, 2).map((a) => tx(a.title)).join("; ") : tx("Nothing to approve")}
          </span>
        </button>
        {seesAnalysis && (
          <button type="button" className="th-tile" onClick={() => show("analysis")}>
            <span className="th-tile-label">{last ? tx("Net result, {month}", { month: last.label }) : tx("Last month")}</span>
            <span className={"th-tile-value" + (last && Number(last.net_result) < 0 ? " is-down" : "") + (!last && failed.has("analysis") ? " is-attn" : "")}>
              {last ? ringgit(last.net_result) : failed.has("analysis") ? notLoaded : "…"}
            </span>
            <span className="th-tile-sub">{last ? tx("{margin}% of {revenue} revenue", { margin: last.net_margin ?? "—", revenue: ringgit(last.revenue) }) : tx("Profit and loss from your records")}</span>
          </button>
        )}
        <button type="button" className="th-tile" onClick={() => show(seesCash ? "cashflow" : "inbox")}>
          <span className="th-tile-label">{tx("Alerts today")}</span>
          <span className={"th-tile-value" + (alertCount || (alerts === null && failed.has("alerts")) ? " is-attn" : "")}>
            {alerts === null ? (failed.has("alerts") ? notLoaded : "…") : alertCount === 0 ? tx("None") : alertCount}
          </span>
          <span className="th-tile-sub">{alertText ?? tx("Rules you set in Company settings")}</span>
        </button>
      </div>
    </section>
  );
}
