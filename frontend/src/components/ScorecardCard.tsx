import { useEffect, useState } from "react";
import { friendlyLoadError } from "../api/client";
import { useI18n } from "../lib/i18n";
import { errorCode, fetchScorecard, type ScorecardResponse } from "../api/topicE";

const SOURCE_NAMES: Record<string, string> = {
  google_maps: "Google Maps",
  shopee: "Shopee",
  grabfood: "GrabFood",
  lazada: "Lazada",
};

/** The credit scorecard: total, grade, and every factor's points and reason. */
export function ScorecardCard() {
  const { tx } = useI18n();
  const [card, setCard] = useState<ScorecardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchScorecard().then((c) => active && setCard(c)).catch((e) => active && setError(friendlyLoadError(errorCode(e))));
    return () => { active = false; };
  }, []);

  if (error) return <div className="fb-callout" role="alert">{error}</div>;
  if (!card) return null;
  const span = card.max_score - card.min_score;
  const position = ((card.score - card.min_score) / span) * 100;

  return (
    <section className="fb-cash-card" aria-labelledby="fb-score-title">
      <div className="fb-cash-card-head">
        <h2 id="fb-score-title">{tx("Credit scorecard")}</h2>
        <span className="fb-inbox-pill is-muted">{tx(card.method === "expert_weights" ? "Published weights" : "Calibrated")}</span>
      </div>
      <div className="fb-score-top">
        <div className={"fb-score-grade is-" + card.grade.toLowerCase()} aria-label={tx("Grade {g}", { g: card.grade })}>{card.grade}</div>
        <div className="fb-score-total">
          <span className="fb-cash-kpi-value">{card.score}</span>
          <span className="fb-inbox-muted">{tx("out of {min}–{max}", { min: card.min_score, max: card.max_score })}</span>
          <div className="fb-score-bar" aria-hidden="true">
            <span style={{ left: `${Math.max(0, Math.min(100, position))}%` }} />
          </div>
        </div>
      </div>
      <div className="fb-cash-scroll">
        <table className="fb-cash-table">
          <thead><tr><th>{tx("Factor")}</th><th>{tx("Value")}</th><th className="is-num">{tx("Points")}</th><th>{tx("Why")}</th></tr></thead>
          <tbody>
            <tr><td colSpan={2}>{tx("Base")}</td><td className="is-num">{card.base_points}</td><td className="fb-inbox-muted">{tx("Every business starts here.")}</td></tr>
            {card.factors.map((f) => (
              <tr key={f.key}>
                <td className="is-label">{tx(f.label)}<br /><span className="fb-cash-fx">{f.evidence.map((e) => tx(e.label)).join(", ")}</span></td>
                <td>{tx(f.value)}</td>
                <td className="is-num">
                  <strong>{f.points}</strong><span className="fb-cash-fx"> / {f.max_points}</span>
                  <div className="fb-score-mini" aria-hidden="true"><span style={{ width: `${(f.points / f.max_points) * 100}%` }} /></div>
                </td>
                <td className="fb-inbox-muted">{tx(f.reason)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {card.public_signals.length > 0 && (
        <div>
          <div className="fb-inbox-label">{tx("Public signals")}</div>
          <ul className="fb-fin-items">
            {card.public_signals.map((s) => (
              <li key={s.source}>
                <span><strong>{SOURCE_NAMES[s.source] ?? s.source}</strong> · {tx(s.metric)}<br /><span className="fb-inbox-muted">{tx(s.trend)}{s.synthetic && " · " + tx("synthetic demo data")}</span></span>
                <span className={"fb-inbox-pill " + (s.status === "ok" ? "is-approved" : s.status === "watch" ? "is-can" : "is-rejected")}>{s.value}</span>
              </li>
            ))}
          </ul>
          <p className="fb-inbox-muted">{tx(card.public_data_note)}</p>
        </div>
      )}
      <p className="fb-inbox-muted">{tx(card.method_note)} {tx(card.disclaimer)}</p>
    </section>
  );
}
