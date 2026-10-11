import { useState } from "react";
import { MegaNav } from "../components/MegaNav";
import { MarketingFooter } from "../components/MarketingFooter";
import { useAppState } from "../lib/appState";
import "./Landing.css";
import "./PublicPages.css";

// Proposed prices only. They have not been tested with any customer, nothing is
// on sale, and the page says so above the plans.

type Plan = {
  name: string;
  monthly: number | null;
  unit: string;
  pitch: string;
  features: string[];
  cta: string;
  featured?: boolean;
};

const PLANS: Plan[] = [
  {
    name: "Starter",
    monthly: 0,
    unit: "per company / month",
    pitch: "For an owner trying DuitDuit on their own records.",
    features: ["90-day cash forecast and alerts", "Financial analysis", "Up to 2 people"],
    cta: "Create a company",
  },
  {
    name: "Team",
    monthly: 49,
    unit: "per person / month",
    pitch: "For small teams that review and approve together.",
    features: ["Review inbox with approval levels", "Comments, @mentions and saved views", "Up to 10 people"],
    cta: "Create a company",
  },
  {
    name: "Business",
    monthly: 99,
    unit: "per person / month",
    pitch: "For growing companies that automate collections.",
    features: ["Automations and reminder sequences", "Financing matches and the Passport", "Slack and WhatsApp notices"],
    cta: "Create a company",
    featured: true,
  },
  {
    name: "Lenders",
    monthly: null,
    unit: "per completed application",
    pitch: "For banks and financiers receiving verified Passports.",
    features: ["Verify any Passport against its audit trail", "Bands or exact values, as the owner allows", "Expiring, revocable links"],
    cta: "Email the team",
  },
];

function emailTeam() {
  window.location.assign("mailto:hello@duitduit.example");
}

export default function Pricing() {
  const { show } = useAppState();
  const [annual, setAnnual] = useState(true);
  return (
    <div className="fb-root fb-mkt lx lv pp">
      <MegaNav />
      <main className="pp-main">
        <header className="pp-head">
          <h1>Pricing</h1>
          <p className="pp-note" role="note">
            <strong>Proposed pricing, not on sale.</strong> These prices are a hypothesis for the business model. They have not been tested with customers, and nothing can be bought here.
          </p>
          <div className="pp-toggle" role="group" aria-label="Billing period">
            <button type="button" aria-pressed={!annual} className={!annual ? "is-on" : undefined} onClick={() => setAnnual(false)}>Monthly</button>
            <button type="button" aria-pressed={annual} className={annual ? "is-on" : undefined} onClick={() => setAnnual(true)}>Annual</button>
          </div>
        </header>
        <div className="pp-plans">
          {PLANS.map((plan) => {
            const price = plan.monthly === null ? null : annual ? Math.round(plan.monthly * 0.8) : plan.monthly;
            return (
              <section key={plan.name} className={"pp-plan" + (plan.featured ? " is-featured" : "")} aria-labelledby={`pp-${plan.name}`}>
                <h2 id={`pp-${plan.name}`}>{plan.name}</h2>
                <div className="pp-price">
                  {price === null ? <span className="pp-amount">Custom</span> : <span className="pp-amount">RM{price}</span>}
                  {price !== null && price > 0 && annual && <span className="pp-save">Save 20%</span>}
                </div>
                <div className="pp-unit">{plan.unit}{price !== null && price > 0 ? (annual ? ", billed annually" : ", billed monthly") : ""}</div>
                <p className="pp-pitch">{plan.pitch}</p>
                <ul>
                  {plan.features.map((f) => <li key={f}>{f}</li>)}
                </ul>
                <button
                  type="button"
                  className={"pp-cta" + (plan.featured ? " is-primary" : "")}
                  onClick={() => (plan.cta === "Email the team" ? emailTeam() : show("signup"))}
                >
                  {plan.cta}
                </button>
              </section>
            );
          })}
        </div>
        <p className="pp-foot">Every plan keeps the same protections: personal data is masked before any AI model sees it, nothing leaves the company without a person's approval, and money needs two people. Prices in ringgit, before tax. Not measured: what customers would pay.</p>
      </main>
      <MarketingFooter />
    </div>
  );
}
