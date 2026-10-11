import { MegaNav } from "../components/MegaNav";
import { MarketingFooter } from "../components/MarketingFooter";
import "./Landing.css";
import "./PublicPages.css";

// Written from the repository's commit history: each line is a change that was
// committed on that day. Nothing here is planned work.

const DAYS: { date: string; title: string; items: string[] }[] = [
  {
    date: "12 Oct 2026",
    title: "Reminder sequences, AI connections, and Finance sees the whole inbox",
    items: [
      "Connect Claude or another AI tool over MCP with a read-only company key: it can read the forecast, the inbox, the collections board and financing matches, and change nothing.",
      "Chinese AI tools can connect too: the MCP tools describe themselves in English and Chinese, and the set-up works with any client that speaks MCP over Streamable HTTP.",
      "Pricing, Changelog and Help pages, Attio-style menus, and a product tour and feature grid on the landing page.",
      "Automations can run a reminder sequence: a friendly reminder, a firm one a week later, then a call task for Finance. Each step waits for a person.",
      "Finance and staff now see, and can decide, items that agents and other people prepared, under the database's row-level security.",
    ],
  },
  {
    date: "11 Oct 2026",
    title: "Working together, and a clean start every day",
    items: [
      "Comments and @mentions on review items, with personal details hidden before saving.",
      "A collections board: drag an unpaid invoice to Reminder to prepare a reminder for approval.",
      "Automations, saved views, a risk note per customer and a money timeline on each customer.",
      "Slack and WhatsApp notices that say how many items wait, with no titles, amounts or names.",
      "The shared demo company starts clean every day, and each day's forecast is kept so it can be scored against the bank balance.",
      "Today, cash, financing and the inbox read in Chinese.",
      "A new look across the landing page, sign-in and the app, and a phone layout for every screen.",
      "Security scans (OWASP ZAP) run on every build.",
    ],
  },
  {
    date: "10 Oct 2026",
    title: "Analysis, playbooks and the morning briefing",
    items: [
      "Monthly profit and loss, six ratios with their formulas, and what changed month on month.",
      "Four playbooks: prepare for the bank meeting, chase late payers, pay everyone, close the month.",
      "A daily briefing in the app, with opt-in email and Telegram pushes.",
      "Alert rules that check the company's records and fire, and bank lines matched to records.",
      "Every financing product that is not yet eligible names its next step.",
    ],
  },
  {
    date: "9 Oct 2026",
    title: "Agents, the review inbox and the Passport",
    items: [
      "A supervisor that routes a goal to the cash, receivables and financing agents.",
      "A persisted review inbox with approval levels and earned autonomy.",
      "The Financing Readiness Passport, audit packs and expiring links for lenders and auditors.",
      "An explainable credit scorecard, and a 42-task evaluation run on every build.",
    ],
  },
  {
    date: "8 Oct 2026",
    title: "The Topic E foundations",
    items: [
      "The cash-flow forecast with scenarios, financing matches, company settings with safety floors, and the team and trust pages.",
    ],
  },
];

export default function Changelog() {
  return (
    <div className="fb-root fb-mkt lx lv pp">
      <MegaNav />
      <main className="pp-main pp-narrow">
        <header className="pp-head is-left">
          <h1>Changelog</h1>
          <p className="pp-lede">What changed in DuitDuit, day by day.</p>
        </header>
        <ol className="cl-list">
          {DAYS.map((day) => (
            <li key={day.date} className="cl-day">
              <time className="cl-date">{day.date}</time>
              <div>
                <h2>{day.title}</h2>
                <ul>{day.items.map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
            </li>
          ))}
        </ol>
      </main>
      <MarketingFooter />
    </div>
  );
}
