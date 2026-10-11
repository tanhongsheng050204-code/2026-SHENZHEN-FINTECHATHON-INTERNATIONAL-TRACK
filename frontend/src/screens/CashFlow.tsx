import { useEffect, useMemo, useState } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { SectionTabs } from "../components/SectionTabs";
import { useAuth } from "../auth/AuthProvider";
import { useI18n } from "../lib/i18n";
import { JOB_LABELS } from "../lib/jobFunctions";
import { ApiError, friendlyLoadError } from "../api/client";
import {
  fetchCashSignals,
  fetchForecast,
  fetchForecastCheck,
  ringgit,
  runScenario,
  type CashSignal,
  type CashSignalsResponse,
  type ForecastCheckResponse,
  type ForecastHorizon,
  type ForecastPoint,
  type ForecastResponse,
  type JobFunction,
} from "../api/topicE";

const HORIZONS: ForecastHorizon[] = [30, 60, 90];
const DRIVER_PREVIEW = 10;
const SCENARIO_ROLES = new Set(["finance_ops", "owner_director"]);

function lowestLikely(points: ForecastPoint[]): ForecastPoint | null {
  return points.reduce<ForecastPoint | null>(
    (low, p) => (low === null || Number(p.likely) < Number(low.likely) ? p : low),
    null,
  );
}

function shortDate(iso: string): string {
  return new Date(iso + "T00:00:00").toLocaleDateString("en-MY", { day: "numeric", month: "short" });
}

function compactRinggit(value: number): string {
  const abs = Math.abs(value);
  const text = abs >= 1000 ? `${Math.round(abs / 1000)}k` : `${Math.round(abs)}`;
  return (value < 0 ? "−RM" : "RM") + text;
}

// ── Chart ───────────────────────────────────────────────────────────────────

const W = 720;
const H = 260;
const PAD = { left: 56, right: 12, top: 14, bottom: 28 };

function ForecastChart({ forecast, scenario }: { forecast: ForecastResponse; scenario: ForecastResponse | null }) {
  const { tx } = useI18n();
  const minimum = Number(forecast.minimum_balance);
  const all = [...forecast.points, ...(scenario?.points ?? [])];
  const top = Math.max(...all.map((p) => Number(p.best)), minimum) * 1.08;
  const bottom = Math.min(0, ...all.map((p) => Number(p.worst)), minimum);
  const span = top - bottom || 1;
  const x = (day: number) => PAD.left + (day / forecast.horizon_days) * (W - PAD.left - PAD.right);
  const y = (value: number) => PAD.top + ((top - value) / span) * (H - PAD.top - PAD.bottom);
  const line = (points: ForecastPoint[], key: "best" | "likely" | "worst") =>
    points.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.day).toFixed(1)},${y(Number(p[key])).toFixed(1)}`).join(" ");
  const band =
    line(forecast.points, "best") +
    " " +
    [...forecast.points].reverse().map((p) => `L${x(p.day).toFixed(1)},${y(Number(p.worst)).toFixed(1)}`).join(" ") +
    " Z";
  const ticksY = [top / 1.08, (top / 1.08 + bottom) / 2, bottom].map((v) => Math.round(v));
  const ticksX = [0, 1, 2, 3].map((i) => Math.round((forecast.horizon_days * i) / 3));
  const low = lowestLikely(forecast.points);
  const shortfall = forecast.shortfall;

  const summary = shortfall
    ? `Likely balance falls to ${ringgit(shortfall.likely_balance)} on day ${shortfall.day}, ${ringgit(shortfall.gap)} below the ${ringgit(forecast.minimum_balance)} minimum.`
    : `Likely balance stays above the ${ringgit(forecast.minimum_balance)} minimum; lowest point ${low ? ringgit(low.likely) : "—"}.`;

  return (
    <svg className="fb-cash-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary}>
      {ticksY.map((v) => (
        <g key={v}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(v)} y2={y(v)} className="fb-cash-grid" />
          <text x={PAD.left - 8} y={y(v) + 4} textAnchor="end" className="fb-cash-axis">{compactRinggit(v)}</text>
        </g>
      ))}
      {ticksX.map((d, i) => (
        <text key={d} x={x(d)} y={H - 8} textAnchor={i === 0 ? "start" : i === ticksX.length - 1 ? "end" : "middle"} className="fb-cash-axis">
          {d === 0 ? tx("Today") : tx("Day {n}", { n: d })}
        </text>
      ))}
      {bottom < 0 && <line x1={PAD.left} x2={W - PAD.right} y1={y(0)} y2={y(0)} className="fb-cash-zero" />}
      <path d={band} className="fb-cash-band" />
      <line x1={PAD.left} x2={W - PAD.right} y1={y(minimum)} y2={y(minimum)} className="fb-cash-minimum" />
      <text x={W - PAD.right - 4} y={y(minimum) - 6} textAnchor="end" className="fb-cash-minimum-label">{tx("Minimum {amount}", { amount: ringgit(minimum) })}</text>
      <path d={line(forecast.points, "likely")} className="fb-cash-likely" />
      {scenario && <path d={line(scenario.points, "likely")} className="fb-cash-scenario" />}
      {shortfall && (
        <g>
          <circle cx={x(shortfall.day)} cy={y(Number(shortfall.likely_balance))} r={6} className="fb-cash-dot" />
          <text x={x(shortfall.day) + 10} y={y(Number(shortfall.likely_balance)) + 18} className="fb-cash-dot-label">
            {tx("Day {n}", { n: shortfall.day })} · {ringgit(shortfall.likely_balance)}
          </text>
        </g>
      )}
    </svg>
  );
}

// ── Tables ──────────────────────────────────────────────────────────────────

function signalDay(s: CashSignal): number {
  return s.likely_day ?? s.best_day;
}

function DriverAmount({ signal }: { signal: CashSignal }) {
  const { tx } = useI18n();
  if (signal.kind === "risk") return <span className="fb-cash-kind is-risk">{tx("Note only")}</span>;
  const sign = signal.kind === "inflow" ? "+" : "−";
  return <span className={"fb-cash-amount is-" + signal.kind}>{sign}{ringgit(signal.amount_myr)}</span>;
}

function byPosition(signals: CashSignalsResponse) {
  const rows = new Map<JobFunction, { inflow: number; outflow: number; risk: number; count: number }>();
  for (const a of signals.by_agent) {
    const row = rows.get(a.job_function) ?? { inflow: 0, outflow: 0, risk: 0, count: 0 };
    row.inflow += Number(a.inflow_total);
    row.outflow += Number(a.outflow_total);
    row.risk += Number(a.at_risk_total);
    row.count += a.signal_count;
    rows.set(a.job_function, row);
  }
  return [...rows.entries()].sort((a, b) => b[1].count - a[1].count);
}

// ── Forecast check ──────────────────────────────────────────────────────────

/** How earlier forecasts compared with the bank balance on the days they forecast. */
function ForecastCheck({ check }: { check: ForecastCheckResponse }) {
  const { tx } = useI18n();
  return (
    <section className="fb-cash-card" aria-labelledby="fb-forecast-check">
      <h2 id="fb-forecast-check">{tx("Forecast check")}</h2>
      {check.status === "not_measured" ? (
        <p className="fb-inbox-muted">
          <strong>{tx("Not measured yet.")}</strong>{" "}
          {check.reason === "synthetic_company"
            ? tx("This is the synthetic demo company, so its forecast is not scored: any accuracy figure would be made up too.")
            : check.reason === "no_forecasts_kept"
              ? tx("No forecast has been kept yet. Today's will be the first.")
              : tx("Forecasts kept: {n}.", { n: check.forecasts_kept }) + (check.first_comparison_on ? " " + tx("First comparison: {date}.", { date: shortDate(check.first_comparison_on) }) : "")}
        </p>
      ) : (
        <div className="fb-cash-scroll">
          <table className="fb-cash-table">
            <thead><tr><th>{tx("Ahead")}</th><th className="is-num">{tx("Compared")}</th><th className="is-num">{tx("Off by, on average")}</th><th className="is-num">{tx("Inside the range")}</th></tr></thead>
            <tbody>
              {check.by_horizon.map((h) => (
                <tr key={h.horizon_days}>
                  <td>{tx("{n} days ahead", { n: h.horizon_days })}</td>
                  <td className="is-num">{h.compared}</td>
                  <td className="is-num">{h.mean_abs_error_myr === null ? "—" : ringgit(h.mean_abs_error_myr)}</td>
                  <td className="is-num">{h.compared ? tx("{inside} of {n}", { inside: h.within_range, n: h.compared }) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="fb-inbox-muted">{tx("Each day's forecast is saved on your audit chain and compared with your bank balance once a statement covering that day is imported.")}</p>
    </section>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function CashFlow() {
  const { t, tx } = useI18n();
  const { identity } = useAuth();
  const [check, setCheck] = useState<ForecastCheckResponse | null>(null);
  const [horizon, setHorizon] = useState<ForecastHorizon>(90);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [signals, setSignals] = useState<CashSignalsResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [scenario, setScenario] = useState<ForecastResponse | null>(null);
  const [eventId, setEventId] = useState("");
  const [shiftDays, setShiftDays] = useState(30);
  const [scenarioError, setScenarioError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [showAllDrivers, setShowAllDrivers] = useState(false);
  const canRunScenarios = SCENARIO_ROLES.has(identity?.role ?? "");

  useEffect(() => {
    let active = true;
    Promise.all([fetchForecast(horizon), fetchCashSignals(horizon)])
      .then(([f, s]) => {
        if (!active) return;
        setForecast(f);
        setSignals(s);
        setLoadError(null);
        setEventId((current) => current || (f.drivers.find((d) => d.kind !== "risk")?.id ?? ""));
      })
      .catch((error: Error) => active && setLoadError(friendlyLoadError(error.message)));
    return () => { active = false; };
  }, [horizon]);

  useEffect(() => {
    let active = true;
    fetchForecastCheck().then((c) => active && setCheck(c)).catch(() => undefined);
    return () => { active = false; };
  }, []);

  const drivers = useMemo(
    () => [...(forecast?.drivers ?? [])].sort((a, b) => signalDay(a) - signalDay(b)),
    [forecast],
  );
  const movable = drivers.filter((d) => d.kind !== "risk");
  const low = forecast ? lowestLikely(forecast.points) : null;
  const scenarioLow = scenario ? lowestLikely(scenario.points) : null;

  const run = async () => {
    setRunning(true);
    setScenarioError(null);
    try {
      setScenario(await runScenario(horizon, [{ event_id: eventId, shift_days: shiftDays }]));
    } catch (error) {
      const code = error instanceof ApiError ? error.code : "";
      setScenarioError(code.startsWith("unknown_event") ? tx("That event is no longer in the forecast.") : friendlyLoadError(code));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="cashflow" />
      <AppTopBar current="cashflow" />

      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.money")}</div>
        <h1>{t("nav.cashFinance")}</h1>
        <p>{t("cash.desc")}</p>
        <SectionTabs section="money" current="cashflow" />
      </header>

      <div className="fb-page-body">
        {forecast?.data_mode === "stub" && <div className="fb-callout">{t("cash.stub")}</div>}
        {loadError && <div className="fb-callout" role="alert">{loadError}</div>}
        {!forecast && !loadError && <div className="fb-callout">{tx("Loading the forecast…")}</div>}

        {forecast && (
          <div className="fb-cash">
            <div className="fb-inbox-tabs" role="group" aria-label={tx("Forecast horizon")}>
              {HORIZONS.map((h) => (
                <button key={h} type="button" aria-pressed={horizon === h} className={horizon === h ? "is-current" : undefined} onClick={() => { setHorizon(h); setScenario(null); }}>
                  {tx("{n} days", { n: h })}
                </button>
              ))}
            </div>

            <div className="fb-cash-kpis">
              <div className="fb-cash-kpi is-good">
                <span className="fb-cash-kpi-label">{tx("Opening balance")}</span>
                <span className="fb-cash-kpi-value">{ringgit(forecast.opening_balance)}</span>
                <span className="fb-cash-kpi-sub">{tx("As of {date}", { date: shortDate(forecast.as_of) })}</span>
              </div>
              <div className="fb-cash-kpi is-attn">
                <span className="fb-cash-kpi-label">{tx("Lowest likely point")}</span>
                <span className="fb-cash-kpi-value">{low ? ringgit(low.likely) : "—"}</span>
                <span className="fb-cash-kpi-sub">{low ? tx("Day {n} · {date}", { n: low.day, date: shortDate(low.date) }) : ""}</span>
              </div>
              <div className={"fb-cash-kpi " + (forecast.shortfall ? "is-danger" : "is-good")}>
                <span className="fb-cash-kpi-label">{tx("Gap to your minimum")}</span>
                <span className="fb-cash-kpi-value">{forecast.shortfall ? ringgit(forecast.shortfall.gap) : tx("None")}</span>
                <span className="fb-cash-kpi-sub">{tx("Minimum {amount}", { amount: ringgit(forecast.minimum_balance) })}</span>
              </div>
            </div>

            {forecast.alerts.map((alert) => (
              <div key={alert.id} className={"fb-cash-alert is-" + alert.severity} role={alert.severity === "critical" ? "alert" : undefined}>
                <strong>{tx(alert.title)}</strong>
                <span>{tx(alert.detail)}</span>
              </div>
            ))}

            <section className="fb-cash-card">
              <div className="fb-cash-card-head">
                <h2>{tx("{n}-day forecast", { n: horizon })}</h2>
                <div className="fb-cash-legend">
                  <span><i className="is-likely" />{tx("Likely")}</span>
                  <span><i className="is-band" />{tx("Best–worst range")}</span>
                  <span><i className="is-min" />{tx("Your minimum")}</span>
                  {scenario && <span><i className="is-scenario" />{tx("What-if")}</span>}
                </div>
              </div>
              <ForecastChart forecast={forecast} scenario={scenario} />
              <details className="fb-cash-table-toggle">
                <summary>{tx("Show as a table")}</summary>
                <div className="fb-cash-scroll">
                  <table className="fb-cash-table">
                    <thead><tr><th>{tx("Day")}</th><th>{tx("Date")}</th><th>{tx("Worst")}</th><th>{tx("Likely")}</th><th>{tx("Best")}</th></tr></thead>
                    <tbody>
                      {forecast.points.filter((p) => p.day % 7 === 0 || p.day === forecast.shortfall?.day).map((p) => (
                        <tr key={p.day}><td>{p.day}</td><td>{shortDate(p.date)}</td><td>{ringgit(p.worst)}</td><td>{ringgit(p.likely)}</td><td>{ringgit(p.best)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </section>

            {check && <ForecastCheck check={check} />}

            {canRunScenarios && (
              <section className="fb-cash-card">
                <h2>{tx("What if…")}</h2>
                <div className="fb-cash-whatif">
                  <label className="fb-cash-field">
                    <span>{tx("Event")}</span>
                    <select value={eventId} onChange={(e) => setEventId(e.target.value)}>
                      {movable.map((d) => <option key={d.id} value={d.id}>{tx("Day {n}", { n: signalDay(d) })} · {tx(d.label)} · {d.kind === "inflow" ? "+" : "−"}{ringgit(d.amount_myr)}</option>)}
                    </select>
                  </label>
                  <label className="fb-cash-field">
                    <span>{tx("Move by (days)")}</span>
                    <input type="number" min={-90} max={180} value={shiftDays} onChange={(e) => setShiftDays(Math.max(-90, Math.min(180, Number(e.target.value) || 0)))} />
                  </label>
                  <button className="fb-btn fb-btn-solid" type="button" disabled={running || !eventId} onClick={() => void run()}>
                    {running ? tx("Running…") : tx("Run scenario")}
                  </button>
                  {scenario && <button className="fb-btn fb-btn-outline" type="button" onClick={() => setScenario(null)}>{tx("Clear")}</button>}
                </div>
                {scenarioError && <div className="fb-inbox-error" role="alert">{scenarioError}</div>}
                {scenario && scenarioLow && low && (
                  <p className="fb-cash-compare" aria-live="polite">
                    {tx("Lowest likely point moves from {from} (day {fromDay}) to {to} (day {toDay}).", { from: ringgit(low.likely), fromDay: low.day, to: ringgit(scenarioLow.likely), toDay: scenarioLow.day })}{" "}
                    {scenario.shortfall ? tx("Still {gap} below your minimum.", { gap: ringgit(scenario.shortfall.gap) }) : tx("No shortfall in this scenario.")}
                  </p>
                )}
                <p className="fb-inbox-muted">{tx("Scenarios never change your books; they only show how the low point moves.")}</p>
              </section>
            )}

            {signals && (
              <section className="fb-cash-card">
                <h2>{tx("By position")}</h2>
                <div className="fb-cash-scroll">
                  <table className="fb-cash-table">
                    <thead><tr><th>{tx("Position")}</th><th className="is-num">{tx("In")}</th><th className="is-num">{tx("Out")}</th><th className="is-num">{tx("At risk")}</th></tr></thead>
                    <tbody>
                      {byPosition(signals).map(([job, row]) => (
                        <tr key={job}>
                          <td>{tx(JOB_LABELS[job])} <span className="fb-cash-fx">· {row.count}</span></td>
                          <td className="is-num">{row.inflow ? ringgit(row.inflow) : "—"}</td>
                          <td className="is-num">{row.outflow ? ringgit(row.outflow) : "—"}</td>
                          <td className="is-num">{row.risk ? ringgit(row.risk) : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            <section className="fb-cash-card">
              <h2>{tx("What moves the balance")}</h2>
              <div className="fb-cash-scroll">
                <table className="fb-cash-table">
                  <thead><tr><th>{tx("Item")}</th><th>{tx("Position")}</th><th>{tx("Likely day")}</th><th className="is-num">{tx("Amount")}</th></tr></thead>
                  <tbody>
                    {(showAllDrivers ? drivers : drivers.slice(0, DRIVER_PREVIEW)).map((d) => (
                      <tr key={d.id}>
                        <td className="is-label">{tx(d.label)}</td>
                        <td>{tx(JOB_LABELS[d.job_function])}</td>
                        <td>{signalDay(d)}</td>
                        <td className="is-num"><DriverAmount signal={d} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {drivers.length > DRIVER_PREVIEW && (
                <button className="fb-cash-more" type="button" aria-expanded={showAllDrivers} onClick={() => setShowAllDrivers((v) => !v)}>
                  {showAllDrivers ? tx("Show fewer") : tx("Show all {n} items", { n: drivers.length })}
                </button>
              )}
              <p className="fb-inbox-muted">{tx("Risk notes (like a complaint on an unpaid invoice) annotate the forecast; they never move the balance by themselves.")}</p>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
