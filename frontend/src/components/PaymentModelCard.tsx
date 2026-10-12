import { useEffect, useState } from "react";
import { fetchPaymentModel, type PaymentModelResponse } from "../api/insights";
import { useI18n } from "../lib/i18n";
import { isPlaceholderName, displayCase } from "../lib/customerAggregation";
import "./records.css";

/**
 * What DuitDuit has learned about when customers pay, and how well that held up
 * on past invoices. The forecast's worst case uses it.
 */
export function PaymentModelCard() {
  const { tx } = useI18n();
  const [model, setModel] = useState<PaymentModelResponse | null>(null);
  useEffect(() => {
    let active = true;
    fetchPaymentModel().then((m) => active && setModel(m)).catch(() => undefined);
    return () => { active = false; };
  }, []);
  if (!model) return null;
  const name = (label: string) => (isPlaceholderName(label) ? tx("Protected customer") : displayCase(label));
  return (
    <section className="fb-cash-card" aria-labelledby="fb-payment-model">
      <div className="sa-head">
        <h2 id="fb-payment-model">{tx("When customers really pay")}</h2>
        {model.backtest && (
          <span className="rc-chip is-blue">{tx("{pct}% of past invoices landed inside the worst case", { pct: model.backtest.coverage_pct })}</span>
        )}
      </div>
      {model.learned_from === 0 ? (
        <p className="rc-note">
          {tx("Not learned yet: no paid e-invoices to learn from. The forecast's worst case assumes {n} days later than likely.", { n: model.default_extra_days })}
        </p>
      ) : (
        <>
          <p className="rc-note">
            {tx("Learned from {n} paid e-invoices. The forecast's worst case for each invoice adds that customer's slow-payment spread; customers with few invoices lean on the company figure ({c} days).", { n: model.learned_from, c: model.company_extra_days })}
          </p>
          <ul className="rc-list">
            {model.customers.map((c) => (
              <li key={c.customer_id}>
                <div className="rc-list-main">
                  <strong>{name(c.label)}</strong>
                  <span>{tx("Usually {m} days late · worst case +{w} days · {n} paid invoices", { m: c.median_days_late, w: c.worst_extra_days, n: c.paid_invoices })}</span>
                </div>
              </li>
            ))}
          </ul>
          {model.backtest && (
            <p className="rc-note">{tx("Backtest: each past invoice was left out, the model refitted, and checked. {within} of {checked} landed inside their worst case.", { within: model.backtest.within, checked: model.backtest.checked })}{model.data_mode === "stub" ? ` ${tx("Measured on the synthetic demo company.")}` : ""}</p>
          )}
        </>
      )}
    </section>
  );
}
