// The answer to a question about a page ("Which loans can we apply for?",
// "Which invoices need fixes?"), shown in the chat from the same endpoint the
// page uses, with a button to open the page for the full detail.
import { useEffect, useState } from "react";
import { fetchEinvoiceReadiness, friendlyLoadError, type EinvoiceReadinessResponse } from "../api/client";
import { errorCode, fetchFinancingMatches, type FinancingMatchesResponse } from "../api/topicE";
import { useAppState } from "../lib/appState";
import { formatRm } from "../lib/customerAggregation";

type Topic = "financing" | "einvoice";

export function TopicAnswer({ screen, onNavigate }: { screen: Topic; onNavigate?: () => void }) {
  const { show } = useAppState();
  const [financing, setFinancing] = useState<FinancingMatchesResponse | null>(null);
  const [readiness, setReadiness] = useState<EinvoiceReadinessResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = screen === "financing"
      ? fetchFinancingMatches().then((value) => active && setFinancing(value))
      : fetchEinvoiceReadiness().then((value) => active && setReadiness(value));
    load.catch((e) => active && setError(friendlyLoadError(errorCode(e))));
    return () => { active = false; };
  }, [screen]);

  const open = () => {
    onNavigate?.();
    show(screen);
  };
  const openLabel = screen === "financing" ? "Open Financing & Passport →" : "Open e-Invoicing →";

  if (error) return <div className="fb-inbox-error" role="alert">{error}</div>;
  if (!financing && !readiness) return <p className="fb-inbox-muted" role="status">Reading your records…</p>;

  if (financing) {
    const ranked = [...financing.matches].sort((a, b) => Number(b.eligible) - Number(a.eligible) || b.fit_score - a.fit_score);
    const eligible = ranked.filter((m) => m.eligible).length;
    return (
      <div className="fb-assistant dd-topic">
        <p><strong>{eligible} of {ranked.length} financing products fit your records now.</strong>
          {financing.shortfall_gap && Number(financing.shortfall_gap) > 0 ? ` Gap to cover: ${formatRm(Number(financing.shortfall_gap))}.` : ""}</p>
        <ol className="dd-topic-list">
          {ranked.slice(0, 3).map((m) => (
            <li key={m.product.id}>
              <strong>{m.product.name}</strong>
              <span className="fb-inbox-muted"> · fit {m.fit_score} of 100 · {m.eligible ? "eligible" : `${m.steps_away} step${m.steps_away === 1 ? "" : "s"} away`}</span>
              <p>{m.next_step ? `Next: ${m.next_step}` : m.eligible ? `${m.explanation} Next: prepare its application pack on the page.` : m.explanation}</p>
            </li>
          ))}
        </ol>
        <p className="fb-inbox-muted">Nothing is applied for here. On the page you can prepare an application pack; the owner reviews it before anything is sent.</p>
        <div className="fb-assistant-actions"><button type="button" className="fb-btn fb-btn-solid" onClick={open}>{openLabel}</button></div>
      </div>
    );
  }

  const r = readiness!;
  const toFix = [...r.critical.records, ...r.warning.records];
  return (
    <div className="fb-assistant dd-topic">
      <p><strong>{r.critical.count} invoice{r.critical.count === 1 ? "" : "s"} need a fix before MyInvois submission</strong>, {r.warning.count} have warnings and {r.passing.count} pass.</p>
      {toFix.length > 0 && (
        <ol className="dd-topic-list">
          {toFix.slice(0, 5).map((record) => (
            <li key={record.id}>
              <strong>{record.invoice_no ?? "No invoice number"}</strong>
              <span className="fb-inbox-muted"> · {record.supplier_name}</span>
              {record.readiness_reason && <p>{record.readiness_reason}</p>}
            </li>
          ))}
        </ol>
      )}
      <p className="fb-inbox-muted">Open an invoice on the page to fix its fields or ask the supplier for a correction.</p>
      <div className="fb-assistant-actions"><button type="button" className="fb-btn fb-btn-solid" onClick={open}>{openLabel}</button></div>
    </div>
  );
}
