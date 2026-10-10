import { useEffect, useState } from "react";
import { useAppState } from "../lib/appState";
import { useAuth } from "../auth/AuthProvider";
import { authMode, demoAvailable, demoSignIn } from "../api/session";
import { MarketingNav } from "../components/Nav";
import { Wordmark } from "../components/Logo";
import { Guilloche } from "../components/Guilloche";
import { RunwayFilm } from "../components/RunwayFilm";
import { CookieConsentBanner, SupportWidget } from "../components/MarketingWidgets";

// Every figure below is the synthetic demo company's, from seed/topic_e.py.

const FAQ_ITEMS = [
  {
    q: "Is this a real product, or a demo?",
    a: "It is a working prototype. The forecast, financing matches, analysis, review inbox and audit trail all run on real code. The company you see is synthetic, and every page says so.",
  },
  {
    q: "Where does the forecast come from?",
    a: "From your own records: a bank statement for the opening balance, then the bills, purchase orders, payroll, payouts and invoices you import. Each line on the forecast links back to the record it came from.",
  },
  {
    q: "Is a financing match an offer of credit?",
    a: "No. DuitDuit checks published rules against your records and shows which product categories fit and why. Terms are illustrative; confirm them with the provider.",
  },
  {
    q: "Can it send money or messages on its own?",
    a: "No. Agents draft. Anything that leaves the company waits in your review inbox, and money needs a second person and a fresh authenticator code.",
  },
  {
    q: "Can DuitDuit submit e-invoices to LHDN?",
    a: "It prepares MyInvois-ready e-invoices and flags missing fields such as a supplier TIN before submission. Live submission to LHDN is not connected in this prototype.",
  },
  {
    q: "Which languages does it support?",
    a: "English, Bahasa Malaysia and Chinese in the interface, and goals typed in any of the three reach the right agent.",
  },
];

function FaqAccordion() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  return (
    <div className="lx-faq">
      {FAQ_ITEMS.map((item, i) => {
        const open = openIndex === i;
        return (
          <div className={"lx-faq-item" + (open ? " is-open" : "")} key={item.q}>
            <button type="button" className="lx-faq-q" aria-expanded={open} onClick={() => setOpenIndex(open ? null : i)}>
              {item.q}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
            </button>
            <div className="lx-faq-a" hidden={!open}><p>{item.a}</p></div>
          </div>
        );
      })}
    </div>
  );
}

function AlertStack() {
  return (
    <ul className="lx-mini lx-alerts" aria-label="Example alerts">
      <li className="is-risk"><strong>Lowest balance in 30 days: RM20,560</strong><span>Below your RM50,000 minimum on day 23</span></li>
      <li className="is-attn"><strong>3 items below their reorder level</strong><span>Sent to purchasing and the owner</span></li>
      <li><strong>Morning briefing sent at 8:00</strong><span>By Telegram, with ranges instead of amounts</span></li>
    </ul>
  );
}

function MatchList() {
  return (
    <ul className="lx-mini lx-matches" aria-label="Example financing matches">
      <li><span>Import trade financing</span><em className="is-ok">Eligible</em></li>
      <li><span>Government-guaranteed SME financing</span><em className="is-ok">Eligible</em></li>
      <li>
        <span>Invoice financing</span><em className="is-near">One step away</em>
        <small>Validate 7 more e-invoices (3 of 19 validated; 50% needed)</small>
      </li>
    </ul>
  );
}

function PnlBars() {
  const months = [
    { m: "Jul", net: 20_000 },
    { m: "Aug", net: 23_800 },
    { m: "Sep", net: 39_200 },
  ];
  return (
    <div className="lx-mini lx-pnl" role="img" aria-label="Net result by month: July RM20,000, August RM23,800, September RM39,200">
      <span className="lx-pnl-title">Net result by month</span>
      <div className="lx-pnl-bars">
        {months.map((row) => (
          <div key={row.m} className="lx-pnl-col">
            <span className="lx-pnl-net">RM{row.net.toLocaleString("en-MY")}</span>
            <span className="lx-pnl-bar" style={{ height: `${(row.net / 40_000) * 100}%` }} />
            <span className="lx-pnl-m">{row.m}</span>
          </div>
        ))}
      </div>
      <p className="lx-pnl-note">Net result rose RM15,400 (+64.7%) in September, on RM249,400 of revenue.</p>
    </div>
  );
}

const PILLARS = [
  {
    id: "cash",
    title: "Cash flow and alerts",
    body: "A 90-day forecast with a best and worst case, built from your bank, bills, payroll and invoices. Alerts fire when a rule you set is crossed, and the morning briefing tells each person what needs them.",
    facts: ["What-if scenarios before you move a payment", "Alerts to the right position, in the app, by email or Telegram", "Bank lines matched to records each month"],
    visual: <AlertStack />,
  },
  {
    id: "financing",
    title: "Financing that fits the gap",
    body: "Eight product categories in Malaysia and China, each checked rule by rule against your records. When a product is out of reach, DuitDuit names the smallest step that would change that.",
    facts: ["A credit scorecard on the same facts as the matches", "A Passport a lender can verify, shared for a fixed number of days", "No invented rates: terms are labelled illustrative"],
    visual: <MatchList />,
  },
  {
    id: "analysis",
    title: "Financial analysis you can check",
    body: "Monthly profit and loss, margins and where the money went, from the same records as the forecast. Every ratio shows its formula and the records it used.",
    facts: ["Days to get paid and days to pay suppliers", "Marketing return and largest customer's share", "Plain sentences on what changed this month"],
    visual: <PnlBars />,
  },
];

const PROTECTIONS = [
  { title: "Two people for every payment", body: "A money item needs a maker, a different checker and an authenticator code from the last five minutes." },
  { title: "Each role sees its own part", body: "Staff never see customer contacts or payroll lines. Each company's rows are walled off in the database." },
  { title: "Every decision is on a hash chain", body: "Proposals, approvals and shared links are recorded by kind and id, and the chain can be re-verified at any time." },
  { title: "Attacks are tested on every build", body: "42 offline tasks, including forged share links, instructions hidden in a spreadsheet and spoken tricks." },
];

const SHOTS = [
  { src: "/screenshots/today.jpg", title: "Today", caption: "What needs you, with the cash gap first." },
  { src: "/screenshots/analysis.jpg", title: "Financial analysis", caption: "Profit and loss and ratios with their formulas." },
  { src: "/screenshots/financing.jpg", title: "Financing", caption: "Matches, next steps and the scorecard." },
];

export default function Landing() {
  const { show, goToSecurity, goToLegal } = useAppState();
  const { applySession } = useAuth();
  const [demoOpen, setDemoOpen] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);

  useEffect(() => {
    if (authMode !== "backend") return;
    let active = true;
    void demoAvailable().then((open) => active && setDemoOpen(open));
    return () => { active = false; };
  }, []);

  // One click into the synthetic company; on any failure the sign-in page explains it.
  const openDemo = async () => {
    setDemoBusy(true);
    try {
      await applySession(await demoSignIn());
      show("home");
    } catch {
      show("login");
    } finally {
      setDemoBusy(false);
    }
  };

  const supportTopics = [
    {
      label: "How the demo works",
      reply: "Sign in with a demo account to see the synthetic company: its forecast, financing matches, analysis and review inbox.",
      action: { label: "Log in", onClick: () => show("login") },
    },
    {
      label: "Security and PDPA",
      reply: "Personal identifiers are masked before they are stored, each role sees only its part, and every decision is on a hash chain.",
      action: { label: "Read about security", onClick: () => goToSecurity("landing") },
    },
  ];

  return (
    <div className="fb-root fb-mkt lx">
      <MarketingNav />

      <header className="lx-hero">
        <Guilloche className="lx-hero-guilloche" />
        <div className="lx-hero-copy">
          <p className="lx-kicker">Finance copilot for Malaysian SMEs</p>
          <h1>See the cash gap three weeks before it hits.</h1>
          <p className="lx-lede">
            DuitDuit reads your bank, bills, payroll and invoices, warns you before cash runs short, finds financing that fits and drafts the fix. Nothing moves until you approve it.
          </p>
          <div className="lx-ctas">
            {demoOpen ? (
              <button className="lx-btn is-primary" type="button" onClick={() => void openDemo()} disabled={demoBusy}>
                {demoBusy ? "Opening the demo company…" : "Open the demo company"}
              </button>
            ) : (
              <button className="lx-btn is-primary" type="button" onClick={() => show("signup")}>Get started</button>
            )}
            <button className="lx-btn is-quiet" type="button" onClick={() => document.getElementById("landing-product")?.scrollIntoView({ behavior: "smooth" })}>See how it works</button>
          </div>
        </div>
        <div className="lx-hero-film">
          <RunwayFilm />
        </div>
      </header>

      <section className="lx-section" id="landing-product" aria-labelledby="lx-product-title">
        <div className="lx-section-head">
          <h2 id="lx-product-title">Three jobs, one copilot</h2>
          <p>Each one reads the same records, so the numbers agree from page to page.</p>
        </div>
        {PILLARS.map((pillar, i) => (
          <article key={pillar.id} className={"lx-pillar" + (i % 2 ? " is-flipped" : "")}>
            <div className="lx-pillar-copy">
              <h3>{pillar.title}</h3>
              <p>{pillar.body}</p>
              <ul>{pillar.facts.map((fact) => <li key={fact}>{fact}</li>)}</ul>
            </div>
            <div className="lx-pillar-visual">{pillar.visual}</div>
          </article>
        ))}
        <p className="lx-fine">Figures from the synthetic demo company.</p>
      </section>

      <section className="lx-band" id="landing-security" aria-labelledby="lx-security-title">
        <Guilloche className="lx-band-guilloche" />
        <div className="lx-band-inner">
          <div className="lx-band-head">
            <h2 id="lx-security-title">Nothing moves without you.</h2>
            <p>Agents prepare the work. People decide, and every decision can be proven later.</p>
            <button type="button" className="lx-btn is-ghost" onClick={() => goToSecurity("landing")}>Read the security approach</button>
          </div>
          <dl className="lx-protections">
            {PROTECTIONS.map((p) => (
              <div key={p.title}>
                <dt>{p.title}</dt>
                <dd>{p.body}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section className="lx-section" id="landing-proof" aria-labelledby="lx-proof-title">
        <div className="lx-section-head">
          <h2 id="lx-proof-title">The real app, not a mockup</h2>
          <p>Screens from the running prototype, showing the synthetic demo company.</p>
        </div>
        <div className="lx-shots">
          {SHOTS.map((shot) => (
            <figure key={shot.src} className="lx-shot">
              <div className="lx-shot-frame"><img src={shot.src} alt={`${shot.title}: ${shot.caption}`} loading="lazy" width={1440} height={900} /></div>
              <figcaption><strong>{shot.title}</strong> {shot.caption}</figcaption>
            </figure>
          ))}
        </div>
      </section>

      <section className="lx-section is-narrow" id="landing-faq" aria-labelledby="lx-faq-title">
        <div className="lx-section-head">
          <h2 id="lx-faq-title">Questions owners ask</h2>
        </div>
        <FaqAccordion />
      </section>

      <section className="lx-closing">
        <h2>See your next 90 days.</h2>
        <div className="lx-ctas">
          <button className="lx-btn is-primary" type="button" onClick={() => show("signup")}>Get started</button>
          <button className="lx-btn is-quiet" type="button" onClick={() => show("login")}>Log in</button>
        </div>
      </section>

      <footer className="lx-footer">
        <div>
          <Wordmark />
          <p>Finance copilot for Malaysian SMEs. A prototype built for the 2026 Shenzhen FinTech competition.</p>
        </div>
        <nav aria-label="Footer">
          <button type="button" onClick={() => goToSecurity("landing")}>Security</button>
          <button type="button" onClick={() => goToLegal("privacy", "landing")}>Privacy policy</button>
          <button type="button" onClick={() => goToLegal("terms", "landing")}>Terms of service</button>
          <a href="mailto:hello@duitduit.example">Contact</a>
        </nav>
      </footer>

      <CookieConsentBanner onReadMore={() => goToLegal("privacy", "landing")} />
      <SupportWidget topics={supportTopics} onEmail={() => { window.location.href = "mailto:hello@duitduit.example"; }} />
    </div>
  );
}
