import { useEffect, useMemo, useState } from "react";
import { MegaNav } from "../components/MegaNav";
import { MarketingFooter } from "../components/MarketingFooter";
import "./Landing.css";
import "./PublicPages.css";

// How each part of DuitDuit works, written from the code. Where something is not
// built or not measured, the article says so.

type Article = { id: string; group: string; title: string; body: string[] };

const ARTICLES: Article[] = [
  {
    id: "start",
    group: "Getting started",
    title: "Create your company",
    body: [
      "Choose Log in, then Create a company. You get a 6-digit code by email, then set up an authenticator app such as Google Authenticator. Owners, finance and compliance always use one.",
      "Import a bank statement first: the forecast starts from its latest balance. Then add bills, payroll, invoices and payouts from Data sources.",
    ],
  },
  {
    id: "roles",
    group: "Getting started",
    title: "Roles and positions",
    body: [
      "Each person has a role (owner, finance, compliance or employee) and one or more positions, such as Finance, Sales or HR. The review inbox shows each person the items for the positions they hold.",
      "Employees never see customer contact details or payroll lines. Compliance can read every item and decides none.",
    ],
  },
  {
    id: "forecast",
    group: "Cash",
    title: "Cash forecast",
    body: [
      "A 90-day forecast with a likely line and a best-to-worst range, against the minimum balance you set. Each line comes from a record you imported, and you can move any item with What if… to see how the low point changes.",
      "Forecast check: each day's forecast is kept and compared with your bank balance once a statement covers that day. Until then its accuracy is shown as not measured.",
    ],
  },
  {
    id: "analysis",
    group: "Cash",
    title: "Financial analysis",
    body: [
      "Monthly profit and loss on a cash basis, an expense breakdown, six ratios with their formulas and what changed since last month.",
    ],
  },
  {
    id: "collections",
    group: "Cash",
    title: "Collections board",
    body: [
      "Every unpaid invoice sits in one column: Later, Due in 14 days, Overdue, Reminder waiting for approval, or Paid in the last 30 days.",
      "Drag a card to Reminder, or press Ask for a reminder. The Collections agent drafts the reminder and it waits in the review inbox. Nothing is sent from the board.",
    ],
  },
  {
    id: "assistant",
    group: "Agents & automations",
    title: "Ask DuitDuit",
    body: [
      "Ask a question in plain language, or tell it what to prepare: \"Can I pay everyone this month?\", \"Prepare me for the bank meeting\", \"Chase the late payers\", \"Close the month\". Answers cite their sources and never show more than your role allows.",
    ],
  },
  {
    id: "inbox",
    group: "Agents & automations",
    title: "Review inbox and approval levels",
    body: [
      "Agents only draft. L1 items are drafts a position reviews; L2 items leave the company and the owner approves them; L3 items move money and need two different people and a fresh authenticator code.",
      "Each item has a comment thread. @mention a position to ask for a look; a mention is a notification, never an approval. Names, emails and phone numbers are hidden before a comment is saved.",
    ],
  },
  {
    id: "automations",
    group: "Agents & automations",
    title: "Automations and reminder sequences",
    body: [
      "In Company settings → Automations, choose a trigger (an invoice N days overdue, cash falling short within N days, a bill due within N days) and what to prepare: a reminder, a reminder sequence, or a review for a position.",
      "A reminder sequence sends nothing by itself: it proposes a friendly reminder, then a firm one a week later, then a call task for Finance, each only after a person decided the last.",
    ],
  },
  {
    id: "financing",
    group: "Trust & connections",
    title: "Financing matches and the Passport",
    body: [
      "Financing matches check each product's published rules against your records and name the next step for any product you do not yet qualify for. Matches are not offers of credit.",
      "The Financing Readiness Passport shows a lender your figures as ranges, through an expiring link you can revoke. The lender can check it against your audit trail without signing in.",
    ],
  },
  {
    id: "data",
    group: "Trust & connections",
    title: "Data sources",
    body: [
      "Upload bank statements, bills, invoice registers and payroll as spreadsheets, forward email and Telegram messages, and add e-invoices. Personal details are masked before anything is stored or shown to an AI model.",
      "Not connected yet: live bank feeds, point-of-sale systems and WhatsApp messages.",
    ],
  },
  {
    id: "chat",
    group: "Trust & connections",
    title: "Team chat notices",
    body: [
      "DuitDuit can post one line to Slack or WhatsApp when the number of items waiting for review changes, with a link to the inbox. It never includes titles, amounts or names.",
      "The server operator sets these up. WhatsApp needs a WhatsApp Business account with an approved template and has not been tested with a live account.",
    ],
  },
  {
    id: "security",
    group: "Security",
    title: "How your data is protected",
    body: [
      "Personal details are tokenized and encrypted before storage, each company's rows are walled off in the database, and every decision is recorded on a hash chain that can be re-verified.",
      "Security scans and 20 adversarial test tasks run on every build. There has been no independent penetration test yet.",
    ],
  },
];

function useHash(): string {
  const [hash, setHash] = useState(() => window.location.hash.slice(1));
  useEffect(() => {
    const update = () => setHash(window.location.hash.slice(1));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return hash;
}

export default function Help() {
  const hash = useHash();
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const shown = useMemo(
    () => (q ? ARTICLES.filter((a) => (a.title + " " + a.body.join(" ")).toLowerCase().includes(q)) : ARTICLES),
    [q],
  );
  const groups = [...new Set(shown.map((a) => a.group))];

  useEffect(() => {
    if (hash) document.getElementById(`help-${hash}`)?.scrollIntoView({ block: "start" });
  }, [hash]);

  return (
    <div className="fb-root fb-mkt lx lv pp">
      <MegaNav />
      <main className="pp-main pp-help">
        <header className="pp-head is-left">
          <h1>Help center</h1>
          <p className="pp-lede">How each part of DuitDuit works.</p>
          <label className="hc-search">
            <span className="fb-sr-only">Search the help center</span>
            <input type="search" placeholder="Search, for example “reminder”" value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
        </header>
        <div className="hc-layout">
          <nav className="hc-toc" aria-label="Articles">
            {groups.map((group) => (
              <div key={group}>
                <div className="hc-toc-group">{group}</div>
                {shown.filter((a) => a.group === group).map((a) => (
                  <a key={a.id} href={`#${a.id}`} className={hash === a.id ? "is-current" : undefined}>{a.title}</a>
                ))}
              </div>
            ))}
          </nav>
          <div className="hc-articles">
            {shown.length === 0 && <p className="pp-lede">No article matches “{query}”.</p>}
            {shown.map((a) => (
              <article key={a.id} id={`help-${a.id}`} className={"hc-article" + (hash === a.id ? " is-current" : "")}>
                <div className="hc-group">{a.group}</div>
                <h2>{a.title}</h2>
                {a.body.map((p) => <p key={p}>{p}</p>)}
              </article>
            ))}
          </div>
        </div>
      </main>
      <MarketingFooter />
    </div>
  );
}
