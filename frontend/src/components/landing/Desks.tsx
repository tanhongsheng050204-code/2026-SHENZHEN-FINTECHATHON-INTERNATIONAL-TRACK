// Collaboration as it really works in DuitDuit: each position has its own desk,
// agents prepare work for it, and money needs a maker and a different checker.

const DESKS = [
  { initial: "O", tone: "is-owner", role: "Owner", today: "Approves reminders and lender sharing; checks every payment with a code" },
  { initial: "F", tone: "is-finance", role: "Finance", today: "Gets the cash forecast, collections drafts and month-end checklist" },
  { initial: "S", tone: "is-sales", role: "Sales", today: "Sees its customers and pipeline, never their contact details" },
  { initial: "C", tone: "is-compliance", role: "Compliance", today: "Watches the agents, re-verifies the audit chain, approves security changes" },
];

const MONEY = [
  { who: "Finance", tone: "is-finance", act: "prepares a supplier payment" },
  { who: "Owner", tone: "is-owner", act: "checks it, with an authenticator code", gold: true },
  { who: "Compliance", tone: "is-compliance", act: "can see the record on the hash chain" },
];

export function Desks() {
  return (
    <div className="lv-desks">
      <ul className="lv-desk-row">
        {DESKS.map((d) => (
          <li key={d.role}>
            <i className={"lv-avatar " + d.tone} aria-hidden="true">{d.initial}</i>
            <strong>{d.role}</strong>
            <span>{d.today}</span>
          </li>
        ))}
      </ul>
      <ol className="lv-money" aria-label="How a payment is approved">
        {MONEY.map((m) => (
          <li key={m.who} className={m.gold ? "is-gold" : undefined}>
            <i className={"lv-avatar " + m.tone} aria-hidden="true">{m.who[0]}</i>
            <span><strong>{m.who}</strong> {m.act}</span>
          </li>
        ))}
      </ol>
      <p className="lv-desk-note">The same person can never be both maker and checker of a payment. Agents never move money.</p>
    </div>
  );
}
