import { useEffect, useState } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { SectionTabs } from "../components/SectionTabs";
import { useI18n } from "../lib/i18n";
import { friendlyLoadError } from "../api/client";
import { errorCode, fetchAnalysis, ringgit, type AnalysisResponse, type PnlMonth, type Ratio } from "../api/topicE";

const ROWS: { key: keyof PnlMonth; label: string; strong?: boolean; cost?: boolean }[] = [
  { key: "revenue", label: "Revenue", strong: true },
  { key: "purchases", label: "Purchases", cost: true },
  { key: "gross_profit", label: "Gross profit", strong: true },
  { key: "payroll", label: "Payroll", cost: true },
  { key: "rent_and_bills", label: "Rent and bills", cost: true },
  { key: "marketing", label: "Marketing", cost: true },
  { key: "marketplace_fees", label: "Marketplace fees", cost: true },
  { key: "net_result", label: "Net result", strong: true },
];

function ratioValue(r: Ratio): string {
  if (r.value === null) return "Not measured";
  if (r.unit === "percent") return `${r.value}%`;
  if (r.unit === "ringgit") return `RM${r.value}`;
  if (r.unit === "day") return `Day ${r.value}`;
  return `${r.value} days`;
}

function Bars({ months }: { months: PnlMonth[] }) {
  const max = Math.max(...months.flatMap((m) => [Number(m.revenue), Number(m.total_costs)]), 1);
  return (
    <div className="fb-fa-bars" role="img" aria-label="Revenue, costs and net result by month">
      {months.map((m) => (
        <div key={m.month} className="fb-fa-bar-group">
          <div className="fb-fa-bar-pair">
            <span className="fb-fa-bar is-revenue" style={{ height: `${(Number(m.revenue) / max) * 100}%` }} title={`Revenue ${ringgit(m.revenue)}`} />
            <span className="fb-fa-bar is-costs" style={{ height: `${(Number(m.total_costs) / max) * 100}%` }} title={`Costs ${ringgit(m.total_costs)}`} />
          </div>
          <span className="fb-fa-bar-label">{m.label.split(" ")[0].slice(0, 3)}</span>
          <span className={"fb-fa-bar-net " + (Number(m.net_result) >= 0 ? "is-up" : "is-down")}>{ringgit(m.net_result)}</span>
        </div>
      ))}
    </div>
  );
}

/** Business financial analysis: profit and loss, ratios with formulas, and what changed. */
export default function Analysis() {
  const { t } = useI18n();
  const [data, setData] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchAnalysis(3)
      .then((d) => active && setData(d))
      .catch((e) => active && setError(friendlyLoadError(errorCode(e))));
    return () => { active = false; };
  }, []);

  const latest = data?.months[data.months.length - 1];

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="analysis" />
      <AppTopBar current="analysis" />

      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.money")}</div>
        <h1>{t("nav.cashFinance")}</h1>
        <p>Profit and loss, margins and ratios from your own records, each with its formula.</p>
        <SectionTabs section="money" current="analysis" />
      </header>

      <div className="fb-page-body">
        {error && <div className="fb-callout" role="alert">{error}</div>}
        {!data && !error && <div className="fb-callout">Loading the analysis…</div>}
        {data && (
          <div className="fb-cash">
            <div className="fb-callout">
              {data.synthetic && <strong>Synthetic demo company · </strong>}
              {data.basis}
            </div>

            {latest && (
              <div className="fb-cash-kpis">
                <div className="fb-cash-kpi is-good">
                  <span className="fb-cash-kpi-label">Revenue · {latest.label}</span>
                  <span className="fb-cash-kpi-value">{ringgit(latest.revenue)}</span>
                  <span className="fb-cash-kpi-sub">Sales received and marketplace payouts</span>
                </div>
                <div className="fb-cash-kpi is-attn">
                  <span className="fb-cash-kpi-label">Gross margin</span>
                  <span className="fb-cash-kpi-value">{latest.gross_margin === null ? "—" : `${latest.gross_margin}%`}</span>
                  <span className="fb-cash-kpi-sub">Revenue minus purchases</span>
                </div>
                <div className={"fb-cash-kpi " + (Number(latest.net_result) >= 0 ? "is-good" : "is-danger")}>
                  <span className="fb-cash-kpi-label">Net result</span>
                  <span className="fb-cash-kpi-value">{ringgit(latest.net_result)}</span>
                  <span className="fb-cash-kpi-sub">{latest.net_margin === null ? "" : `${latest.net_margin}% of revenue`}</span>
                </div>
              </div>
            )}

            {data.changes.length > 0 && (
              <section className="fb-cash-card">
                <h2>What changed</h2>
                <ul className="fb-fa-changes">
                  {data.changes.map((c) => <li key={c}>{c}</li>)}
                </ul>
              </section>
            )}

            <section className="fb-cash-card">
              <div className="fb-cash-card-head">
                <h2>Profit and loss</h2>
                <div className="fb-cash-legend">
                  <span><i className="fb-fa-key is-revenue" />Revenue</span>
                  <span><i className="fb-fa-key is-costs" />Costs</span>
                </div>
              </div>
              <Bars months={data.months} />
              <div className="fb-cash-scroll">
                <table className="fb-cash-table fb-fa-table">
                  <thead>
                    <tr><th scope="col">RM</th>{data.months.map((m) => <th key={m.month} scope="col">{m.label}</th>)}</tr>
                  </thead>
                  <tbody>
                    {ROWS.map((row) => (
                      <tr key={row.key} className={row.strong ? "is-strong" : undefined}>
                        <th scope="row">{row.cost ? `− ${row.label}` : row.label}</th>
                        {data.months.map((m) => <td key={m.month}>{ringgit(m[row.key] as string)}</td>)}
                      </tr>
                    ))}
                    <tr>
                      <th scope="row">Net margin</th>
                      {data.months.map((m) => <td key={m.month}>{m.net_margin === null ? "—" : `${m.net_margin}%`}</td>)}
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <section className="fb-cash-card">
              <h2>Where the money went</h2>
              <ul className="fb-fa-expenses">
                {data.expenses.map((e) => (
                  <li key={e.label}>
                    <span>{e.label}</span>
                    <span className="fb-fa-expense-bar"><i style={{ width: `${e.share ?? 0}%` }} /></span>
                    <span>{ringgit(e.amount)}{e.share !== null && <small> · {e.share}%</small>}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="fb-cash-card">
              <h2>Ratios</h2>
              <div className="fb-fa-ratios">
                {data.ratios.map((r) => (
                  <div key={r.key} className={"fb-fa-ratio" + (r.status === "not_measured" ? " is-muted" : "")}>
                    <span className="fb-cash-kpi-label">{r.label}</span>
                    <span className="fb-fa-ratio-value">{ratioValue(r)}</span>
                    <span className="fb-fa-ratio-formula">{r.formula}</span>
                    <span className="fb-fa-ratio-sources">From: {r.sources.join(", ")}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
