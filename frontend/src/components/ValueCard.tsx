// What DuitDuit did for this company, measured from its own records. Estimates
// and figures with no records behind them say so.
import { useEffect, useState } from "react";
import { fetchValue, type ValueReport } from "../api/insights";
import { useI18n } from "../lib/i18n";

const KIND_LABEL = { measured: "Measured", estimate: "Estimate", not_measured: "Not measured" } as const;

export function ValueCard() {
  const { tx } = useI18n();
  const [report, setReport] = useState<ValueReport | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    fetchValue().then((r) => active && setReport(r)).catch(() => active && setFailed(true));
    return () => { active = false; };
  }, []);
  if (failed) return null;
  return (
    <section className="fd-card dd-value" aria-labelledby="dd-value-title">
      <div className="fd-card-head">
        <div>
          <h2 id="dd-value-title">{tx("What DuitDuit did for you")}</h2>
          <p>{tx("Measured from your own records, except where it says estimate.")}{report?.synthetic ? ` ${tx("Synthetic demo company.")}` : ""}</p>
        </div>
      </div>
      {!report ? <p className="fd-empty">{tx("Loading…")}</p> : (
        <ul className="dd-value-grid">
          {report.metrics.map((m) => (
            <li key={m.key} className={"is-" + m.kind}>
              <span className="dd-value-label">{tx(m.label)}</span>
              <strong>{tx(m.value)}</strong>
              <span className="dd-value-detail">{tx(m.detail)}</span>
              {m.kind !== "measured" && <em>{tx(KIND_LABEL[m.kind])}</em>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
