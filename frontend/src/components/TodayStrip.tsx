import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { canOpen } from "../lib/access";
import { useAppState } from "../lib/appState";
import { fetchForecast, fetchPositions, ringgit, type ForecastResponse, type PositionSummary } from "../api/topicE";

/**
 * The top of "Today": the three things a person acts on first — the cash
 * outlook (if their role sees it), what waits for their approval, and their
 * own positions. Each card opens the page where the work happens.
 */
export function TodayStrip() {
  const { show, askRole, approvalsCount, reviewInboxCount } = useAppState();
  const { identity } = useAuth();
  const role = identity?.role ?? askRole;
  const seesCash = canOpen("cashflow", role);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [positions, setPositions] = useState<PositionSummary[] | null>(null);

  useEffect(() => {
    let active = true;
    if (seesCash) fetchForecast(90).then((f) => active && setForecast(f)).catch(() => undefined);
    fetchPositions().then((p) => active && setPositions(p.filter((x) => x.enabled))).catch(() => undefined);
    return () => { active = false; };
  }, [seesCash]);

  const waiting = approvalsCount + reviewInboxCount;
  const shortfall = forecast?.shortfall ?? null;

  return (
    <section className="fb-today" aria-label="Today">
      {seesCash && (
        <button type="button" className={"fb-today-card " + (shortfall ? "is-alert" : "is-ok")} onClick={() => show("cashflow")}>
          <span className="fb-today-label">Cash outlook</span>
          {forecast === null ? (
            <span className="fb-today-value">…</span>
          ) : shortfall ? (
            <>
              <span className="fb-today-value">Short on day {shortfall.day}</span>
              <span className="fb-today-sub">{ringgit(shortfall.gap)} below your {ringgit(shortfall.minimum_balance)} minimum</span>
            </>
          ) : (
            <>
              <span className="fb-today-value">Above your minimum</span>
              <span className="fb-today-sub">For the next {forecast.horizon_days} days</span>
            </>
          )}
          <span className="fb-today-go">Open Cash &amp; finance →</span>
        </button>
      )}
      <button type="button" className={"fb-today-card " + (waiting > 0 ? "is-attn" : "is-ok")} onClick={() => show("inbox")}>
        <span className="fb-today-label">Waiting for you</span>
        <span className="fb-today-value">{waiting === 0 ? "Nothing to approve" : `${waiting} to review`}</span>
        <span className="fb-today-sub">Agent proposals, recommendations and outreach in one inbox</span>
        <span className="fb-today-go">Open review inbox →</span>
      </button>
      <button type="button" className="fb-today-card" onClick={() => show("positions")}>
        <span className="fb-today-label">Your positions</span>
        <span className="fb-today-value">{positions === null ? "…" : positions.length === 0 ? "None assigned" : `${positions.length} position${positions.length === 1 ? "" : "s"}`}</span>
        <span className="fb-today-sub">{positions?.slice(0, 3).map((p) => p.display_name).join(" · ")}</span>
        <span className="fb-today-go">Open your workspace →</span>
      </button>
    </section>
  );
}
