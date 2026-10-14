// The start of a company that has no records yet: say so plainly and offer the
// next step, instead of showing the demo company's figures as if they were its own.
import { Sidebar, AppTopBar } from "./Nav";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import type { Screen } from "../lib/screens";

const STEPS = [
  { title: "Import your bank statement", body: "A CSV export from your bank gives DuitDuit your opening balance and every line in and out. Bills, payroll and sales can follow." },
  { title: "Add or upload invoices", body: "e-Invoicing reads invoices you upload and checks them against MyInvois rules." },
  { title: "Invite your team", body: "Give Finance, Sales or HR their own access. Each sees only what their role allows." },
];

export function NoRecordsYet({ current }: { current: Screen }) {
  const { show } = useAppState();
  const { tx } = useI18n();
  return (
    <div className="fb-root fb-shell">
      <Sidebar current={current} />
      <AppTopBar current={current} />
      <div className="fb-page-body">
        <section className="fd-card dd-norecords" aria-labelledby="dd-norecords-title">
          <h1 id="dd-norecords-title">{tx("Your company has no records yet")}</h1>
          <p>{tx("Forecasts, collections, financing matches and agent proposals are built from your own records. Once you import them, this page fills in. Nothing here is sample data.")}</p>
          <ol>
            {STEPS.map((s) => (
              <li key={s.title}>
                <strong>{tx(s.title)}</strong>
                <span>{tx(s.body)}</span>
              </li>
            ))}
          </ol>
          <div className="dd-norecords-actions">
            <button type="button" className="fb-btn fb-btn-solid" onClick={() => show("ingestion")}>{tx("Import your data")}</button>
            <button type="button" className="fb-btn fb-btn-outline" onClick={() => show("einvoice")}>{tx("Go to e-Invoicing")}</button>
            <button type="button" className="fb-btn fb-btn-outline" onClick={() => show("team")}>{tx("Invite your team")}</button>
          </div>
          <p className="dd-norecords-note">{tx("Want to see DuitDuit with a full set of figures first? Sign out and choose Open the demo company on the login page.")}</p>
        </section>
      </div>
    </div>
  );
}
