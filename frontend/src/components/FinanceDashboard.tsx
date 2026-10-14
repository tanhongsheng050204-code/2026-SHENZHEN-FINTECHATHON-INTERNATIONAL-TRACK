// Home for the money roles: four key numbers, the cash forecast as the main chart,
// what waits for a decision, financing readiness, what comes next and which customers
// to watch. Every figure comes from the same endpoints as its own page; a card that
// could not load says so and offers a retry instead of showing an empty "all clear".
import { useEffect, useMemo, useState, type FormEvent } from "react";
import "./FinanceDashboard.css";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import { canOpen } from "../lib/access";
import { JOB_LABELS } from "../lib/jobFunctions";
import { displayCase, isPlaceholderName } from "../lib/customerAggregation";
import { useAuth } from "../auth/AuthProvider";
import type { CustomerSummary } from "../api/client";
import { fetchBoard, type CollectionsBoard } from "../api/collaboration";
import {
  fetchAnalysis,
  fetchForecast,
  fetchReviewInbox,
  fetchScorecard,
  ringgit,
  type AnalysisResponse,
  type ForecastResponse,
  type ReviewAction,
  type ScorecardResponse,
} from "../api/topicE";

const OPEN = new Set(["pending", "awaiting_second_approval", "edited"]);
const HORIZONS = [30, 60, 90] as const;
type Part = "forecast" | "analysis" | "inbox" | "board" | "score";

function shortDate(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function longDate(iso: string) {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short", year: "numeric" });
}

function addDays(iso: string, days: number) {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function Loading() {
  return <div className="fb-skeleton-line" aria-hidden="true" style={{ width: "60%", height: "1.6rem" }} />;
}

function CashChart({ forecast }: { forecast: ForecastResponse }) {
  const { tx } = useI18n();
  const [horizon, setHorizon] = useState<number>(90);
  const [hover, setHover] = useState<number | null>(null);
  const W = 760;
  const H = 260;
  const points = forecast.points.filter((p) => p.day <= horizon);
  const minimum = Number(forecast.minimum_balance);
  const values = points.flatMap((p) => [Number(p.likely), Number(p.worst)]).concat(minimum, 0);
  const top = Math.max(...values) * 1.08;
  const bottom = Math.min(...values) - top * 0.04;
  const x = (day: number) => (day / horizon) * W;
  const y = (v: number) => H - ((v - bottom) / (top - bottom)) * H;
  const path = (key: "likely" | "worst") => points.map((p, i) => `${i ? "L" : "M"}${x(p.day).toFixed(1)} ${y(Number(p[key])).toFixed(1)}`).join(" ");
  const likely = path("likely");
  const area = `${likely} L${x(points[points.length - 1].day).toFixed(1)} ${H} L0 ${H} Z`;
  const shortfall = forecast.shortfall && forecast.shortfall.day <= horizon ? forecast.shortfall : null;
  const shown = hover === null ? null : points[Math.min(hover, points.length - 1)];
  const left = shown ? (x(shown.day) / W) * 100 : 0;
  const below = shown ? minimum - Number(shown.likely) : 0;
  const summary = shortfall
    ? tx("Cash falls {gap} below your minimum in {n} days.", { gap: ringgit(shortfall.gap), n: shortfall.day })
    : tx("Cash stays above your minimum for the next 90 days.");

  return (
    <section className="fd-card fd-chart" aria-labelledby="fd-chart-title">
      <div className="fd-card-head">
        <div>
          <h2 id="fd-chart-title">{tx("Cash forecast")}</h2>
          <p>{tx("Likely balance, worst case and your {minimum} minimum", { minimum: ringgit(forecast.minimum_balance) })}</p>
        </div>
        <div className="fd-seg" role="group" aria-label={tx("Forecast horizon")}>
          {HORIZONS.map((h) => (
            <button key={h} type="button" aria-pressed={h === horizon} onClick={() => { setHorizon(h); setHover(null); }}>
              {tx("{n} days", { n: h })}
            </button>
          ))}
        </div>
      </div>
      <div className="fd-plot" onMouseLeave={() => setHover(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={summary}>
          <line className="fd-zero" x1="0" x2={W} y1={y(0)} y2={y(0)} />
          <path className="fd-area" d={area} />
          <path className="fd-worst" d={path("worst")} />
          <path className="fd-likely" d={likely} />
          <line className="fd-min" x1="0" x2={W} y1={y(minimum)} y2={y(minimum)} />
          {shortfall && <circle className="fd-dip" cx={x(shortfall.day)} cy={y(Number(shortfall.likely_balance))} r="6" />}
          {shown && <line className="fd-cursor" x1={x(shown.day)} x2={x(shown.day)} y1="0" y2={H} />}
        </svg>
        {points.map((p, i) => {
          const a = i ? (x(points[i - 1].day) + x(p.day)) / 2 : 0;
          const b = i < points.length - 1 ? (x(p.day) + x(points[i + 1].day)) / 2 : W;
          return (
            <button
              key={p.day}
              type="button"
              className="fd-hit"
              style={{ left: `${(a / W) * 100}%`, width: `${((b - a) / W) * 100}%` }}
              onMouseEnter={() => setHover(i)}
              onFocus={() => setHover(i)}
              aria-label={`${shortDate(p.date)}: ${tx("Likely")} ${ringgit(p.likely)}`}
            />
          );
        })}
        {shown && (
          <div className="fd-tip" role="status" style={{ left: `${Math.min(Math.max(left, 3), 97)}%`, transform: left > 60 ? "translateX(calc(-100% - 10px))" : "translateX(10px)" }}>
            <strong>{tx("Day {n} · {date}", { n: shown.day, date: shortDate(shown.date) })}</strong>
            <span>{tx("Likely")} {ringgit(shown.likely)}</span>
            <span className="fd-tip-soft">{tx("Worst")} {ringgit(shown.worst)}</span>
            {below > 0 && <span className="fd-tip-flag">{tx("Still {gap} below your minimum.", { gap: ringgit(String(below)) })}</span>}
          </div>
        )}
      </div>
      <div className="fd-legend">
        <span><i className="fd-key is-likely" aria-hidden="true" />{tx("Likely")}</span>
        <span><i className="fd-key is-worst" aria-hidden="true" />{tx("Worst case")}</span>
        <span><i className="fd-key is-min" aria-hidden="true" />{tx("Your minimum")}</span>
        <span className="fd-legend-note">{summary}</span>
      </div>
    </section>
  );
}

export function FinanceDashboard({ greeting, customers, customersFailed }: { greeting: string; customers: CustomerSummary[] | null; customersFailed: boolean }) {
  const { show, askAbout, askRole } = useAppState();
  const { tx } = useI18n();
  const { identity } = useAuth();
  const role = identity?.role ?? askRole;
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [inbox, setInbox] = useState<ReviewAction[] | null>(null);
  const [board, setBoard] = useState<CollectionsBoard | null>(null);
  const [score, setScore] = useState<ScorecardResponse | null>(null);
  const [failed, setFailed] = useState<Set<Part>>(new Set());
  const [attempt, setAttempt] = useState(0);
  const [question, setQuestion] = useState("");

  useEffect(() => {
    let active = true;
    const fail = (part: Part) => () => { if (active) setFailed((s) => new Set(s).add(part)); };
    fetchForecast(90).then((f) => active && setForecast(f)).catch(fail("forecast"));
    fetchAnalysis(3).then((a) => active && setAnalysis(a)).catch(fail("analysis"));
    fetchReviewInbox().then((r) => active && setInbox(r.actions.filter((a) => a.can_decide && OPEN.has(a.status)))).catch(fail("inbox"));
    fetchBoard().then((b) => active && setBoard(b)).catch(fail("board"));
    if (canOpen("financing", role)) fetchScorecard().then((s) => active && setScore(s)).catch(fail("score"));
    return () => { active = false; };
  }, [attempt, role]);

  const retry = () => { setFailed(new Set()); setAttempt((n) => n + 1); };

  const lowest = useMemo(() => {
    if (!forecast || forecast.points.length === 0) return null;
    return forecast.points.reduce((low, p) => (Number(p.likely) < Number(low.likely) ? p : low));
  }, [forecast]);
  const owed = useMemo(() => {
    if (!board) return null;
    const open = board.columns.filter((c) => c.stage !== "paid").flatMap((c) => c.cards);
    return {
      total: open.reduce((sum, c) => sum + Number(c.amount), 0),
      overdue: open.filter((c) => c.days_overdue > 0).reduce((sum, c) => sum + Number(c.amount), 0),
      count: open.length,
    };
  }, [board]);
  const last = analysis?.months[analysis.months.length - 1] ?? null;
  const [allItems, setAllItems] = useState(false);
  const dated = useMemo(() => {
    if (!forecast) return [];
    return forecast.drivers
      .filter((d) => d.kind !== "risk" && d.likely_day !== null)
      .sort((a, b) => (a.likely_day ?? 0) - (b.likely_day ?? 0));
  }, [forecast]);
  const upcoming = allItems ? dated : dated.slice(0, 6);
  const watch = (customers ?? []).filter((c) => c.priority !== "healthy").sort((a, b) => b.attention_score - a.attention_score).slice(0, 3);

  const ask = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (question.trim()) askAbout(question.trim());
  };
  const notLoaded = (part: Part) => failed.has(part);
  const errorNote = (
    <button type="button" className="fd-retry" onClick={retry}>{tx("Couldn't load")} · {tx("Try again")}</button>
  );

  const gauge = score ? (() => {
    const frac = Math.min(1, Math.max(0, (score.score - score.min_score) / (score.max_score - score.min_score)));
    const angle = Math.PI * (1 - frac);
    return `M 20 100 A 80 80 0 0 1 ${(100 + 80 * Math.cos(angle)).toFixed(1)} ${(100 - 80 * Math.sin(angle)).toFixed(1)}`;
  })() : null;

  return (
    <div className="fd">
      <header className="fd-head">
        <div>
          <h1>{greeting}</h1>
          <p>{forecast ? tx("Your cash, what needs you, and what comes next. As of {date}.", { date: longDate(forecast.as_of) }) : tx("Your cash, what needs you, and what comes next.")}</p>
        </div>
        <form className="fd-ask" onSubmit={ask} role="search" aria-label={tx("Ask DuitDuit")}>
          <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder={tx("Ask DuitDuit, or tell it what to prepare")} aria-label={tx("Ask DuitDuit, or tell it what to prepare")} maxLength={500} />
          <button type="submit" disabled={!question.trim()}>{tx("Ask")}</button>
        </form>
      </header>

      <section className="fd-kpis" aria-label={tx("Key numbers")}>
        <button type="button" className="fd-card fd-kpi" onClick={() => show("cashflow")}>
          <span className="fd-kpi-label">{tx("Cash today")}</span>
          {forecast ? <strong>{ringgit(forecast.opening_balance)}</strong> : notLoaded("forecast") ? errorNote : <Loading />}
          {forecast && <span className="fd-badge">{tx("Opening balance")}</span>}
          {forecast && <span className="fd-kpi-note">{tx("As of {date}", { date: shortDate(forecast.as_of) })}</span>}
        </button>
        <button type="button" className="fd-card fd-kpi" onClick={() => show("cashflow")}>
          <span className="fd-kpi-label">{tx("Lowest in 90 days")}</span>
          {lowest ? <strong>{ringgit(lowest.likely)}</strong> : notLoaded("forecast") ? errorNote : <Loading />}
          {forecast && (forecast.shortfall
            ? <span className="fd-badge is-risk">{tx("{gap} below minimum", { gap: ringgit(forecast.shortfall.gap) })}</span>
            : <span className="fd-badge is-good">{tx("Above your minimum")}</span>)}
          {lowest && <span className="fd-kpi-note">{tx("On {date}", { date: shortDate(lowest.date) })}</span>}
        </button>
        <button type="button" className="fd-card fd-kpi" onClick={() => show("collections")}>
          <span className="fd-kpi-label">{tx("Owed to you")}</span>
          {owed ? <strong>{ringgit(owed.total.toFixed(2))}</strong> : notLoaded("board") ? errorNote : <Loading />}
          {owed && (owed.overdue > 0
            ? <span className="fd-badge is-risk">{tx("{amount} overdue", { amount: ringgit(owed.overdue.toFixed(2)) })}</span>
            : <span className="fd-badge is-good">{tx("None overdue")}</span>)}
          {owed && <span className="fd-kpi-note">{tx("{n} open invoices", { n: owed.count })}</span>}
        </button>
        <button type="button" className="fd-card fd-kpi" onClick={() => show("analysis")}>
          <span className="fd-kpi-label">{last ? tx("Net result, {month}", { month: last.label }) : tx("Last month")}</span>
          {last ? <strong>{ringgit(last.net_result)}</strong> : notLoaded("analysis") ? errorNote : <Loading />}
          {last && <span className="fd-badge">{tx("Profit and loss")}</span>}
          {last && <span className="fd-kpi-note">{tx("Revenue {amount}", { amount: ringgit(last.revenue) })}</span>}
        </button>
      </section>

      <div className="fd-row">
        {forecast ? <CashChart forecast={forecast} /> : (
          <section className="fd-card fd-chart" aria-label={tx("Cash forecast")}>
            {notLoaded("forecast") ? errorNote : <><Loading /><div className="fd-plot-skeleton" /></>}
          </section>
        )}

        <div className="fd-side">
          <section className="fd-card" aria-labelledby="fd-wait-title">
            <div className="fd-card-head">
              <h2 id="fd-wait-title">{tx("Waiting for you")}</h2>
              <button type="button" className="fd-link" onClick={() => show("inbox")}>{tx("Review inbox")}</button>
            </div>
            {inbox === null ? (notLoaded("inbox") ? errorNote : <Loading />) : inbox.length === 0 ? (
              <p className="fd-empty">{tx("Nothing needs your decision right now.")}</p>
            ) : (
              <ul className="fd-list">
                {inbox.slice(0, 3).map((a) => (
                  <li key={a.id}>
                    <button type="button" onClick={() => show("inbox")}>
                      <span className={"fd-level is-" + a.autonomy_level.toLowerCase()}>{a.autonomy_level}</span>
                      <span className="fd-list-main">
                        <strong>{tx(a.title)}</strong>
                        <span>{tx("For {who}", { who: tx(JOB_LABELS[a.reviewer_job_function] ?? a.reviewer_job_function) })}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {inbox && inbox.length > 3 && <p className="fd-more">{tx("{n} more in the review inbox", { n: inbox.length - 3 })}</p>}
            <p className="fd-fine">{tx("Nothing is sent or paid until a person approves.")}</p>
          </section>

        </div>
      </div>

      <div className="fd-row">
        <section className="fd-card fd-table-card" aria-labelledby="fd-next-title">
          <div className="fd-card-head">
            <h2 id="fd-next-title">{tx("Coming up: money in and out")}</h2>
            {dated.length > 6 ? (
              <button type="button" className="fd-link" aria-expanded={allItems} onClick={() => setAllItems((v) => !v)}>{allItems ? tx("Show fewer") : tx("Show all {n} items", { n: dated.length })}</button>
            ) : (
              <button type="button" className="fd-link" onClick={() => show("cashflow")}>{tx("See the forecast")}</button>
            )}
          </div>
          {!forecast ? (notLoaded("forecast") ? errorNote : <Loading />) : upcoming.length === 0 ? (
            <p className="fd-empty">{tx("Nothing is due in the next 90 days.")}</p>
          ) : (
            <div className="fd-table-wrap">
              <table className="fd-table">
                <thead>
                  <tr><th scope="col">{tx("Date")}</th><th scope="col">{tx("Item")}</th><th scope="col">{tx("Position")}</th><th scope="col" className="is-num">{tx("Amount")}</th></tr>
                </thead>
                <tbody>
                  {upcoming.map((d) => (
                    <tr key={d.id}>
                      <td className="fd-muted">{shortDate(addDays(forecast.as_of, d.likely_day ?? 0))}</td>
                      <td>{tx(d.label)}</td>
                      <td><span className="fd-pill">{tx(JOB_LABELS[d.job_function] ?? d.job_function)}</span></td>
                      <td className={"is-num " + (d.kind === "inflow" ? "is-in" : "is-out")}>{d.kind === "inflow" ? "+" : "−"}{ringgit(d.amount_myr)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <div className="fd-side">
            {canOpen("financing", role) && (
              <section className="fd-card fd-gauge-card" aria-labelledby="fd-fit-title">
                <div className="fd-card-head">
                  <h2 id="fd-fit-title">{tx("Financing readiness")}</h2>
                  <button type="button" className="fd-link" onClick={() => show("financing")}>{tx("Matches")}</button>
                </div>
                {score && gauge ? (
                  <>
                    <svg className="fd-gauge" viewBox="0 0 200 110" role="img" aria-label={tx("Credit scorecard {score} out of {min}–{max}, grade {g}", { score: score.score, min: score.min_score, max: score.max_score, g: score.grade })}>
                      <path className="fd-gauge-track" d="M 20 100 A 80 80 0 0 1 180 100" />
                      <path className="fd-gauge-fill" d={gauge} />
                    </svg>
                    <strong className="fd-gauge-value">{score.score}</strong>
                    <span className="fd-kpi-note">{tx("Grade {g}", { g: score.grade })} · {tx("out of {min}–{max}", { min: score.min_score, max: score.max_score })}</span>
                    <div className="fd-why">
                      <span className="fd-why-title">{tx("Why this score")}</span>
                      <span className="fd-why-row"><span>{tx("Base")}</span><b>+{score.base_points}</b></span>
                      {[...score.factors].sort((x, y) => (y.max_points - y.points) - (x.max_points - x.points)).slice(0, 4).map((f) => (
                        <span key={f.key} className="fd-why-row" title={tx(f.reason)}>
                          <span>{tx(f.label)} <em>{f.value}</em></span>
                          <b className={f.points < f.max_points ? "is-short" : undefined}>{f.points}/{f.max_points}</b>
                        </span>
                      ))}
                      <span className="fd-why-note">{tx("Biggest gaps first. Points come from published bands, not a trained model. The full scorecard is on Financing.")}</span>
                    </div>
                  </>
                ) : notLoaded("score") ? errorNote : <Loading />}
              </section>
            )}
        <section className="fd-card fd-side-card" aria-labelledby="fd-watch-title">
          <div className="fd-card-head">
            <h2 id="fd-watch-title">{tx("Customers to watch")}</h2>
            <button type="button" className="fd-link" onClick={() => show("customers")}>{tx("Customers")}</button>
          </div>
          {customers === null ? (customersFailed ? <p className="fd-empty">{tx("Couldn't load customer data.")}</p> : <Loading />) : watch.length === 0 ? (
            <p className="fd-empty">{tx("No customer has a warning sign today.")}</p>
          ) : (
            <ul className="fd-list">
              {watch.map((c) => {
                const name = isPlaceholderName(c.name) ? tx("Protected customer") : displayCase(c.name);
                return (
                  <li key={c.id}>
                    <button type="button" onClick={() => show("customers")}>
                      <span className="fd-avatar" aria-hidden="true">{name.charAt(0).toUpperCase()}</span>
                      <span className="fd-list-main">
                        <strong>{name}</strong>
                        <span>{c.risk_note ? c.risk_note : Number(c.overdue_total) > 0 ? tx("{amount} overdue", { amount: ringgit(c.overdue_total) }) : tx("{amount} outstanding", { amount: ringgit(c.outstanding_total) })}</span>
                      </span>
                      <span className={"fd-badge is-" + (c.priority === "urgent" || c.priority === "high" ? "risk" : "watch")}>{tx(c.priority === "urgent" ? "Urgent" : c.priority === "high" ? "High" : "Monitoring")}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
        </div>
      </div>
    </div>
  );
}
