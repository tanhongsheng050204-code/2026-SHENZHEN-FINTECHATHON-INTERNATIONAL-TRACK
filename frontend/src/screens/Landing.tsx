import { useEffect, useState } from "react";
import { useAppState } from "../lib/appState";
import { useAuth } from "../auth/AuthProvider";
import { authMode, demoAvailable, demoSignIn } from "../api/session";
import { MegaNav } from "../components/MegaNav";
import { MarketingFooter } from "../components/MarketingFooter";
import { Guilloche } from "../components/Guilloche";
import { HeroApp } from "../components/landing/HeroApp";
import { SourcesGrid } from "../components/landing/SourcesGrid";
import { DayRail } from "../components/landing/DayRail";
import { Desks } from "../components/landing/Desks";
import { ChainProof } from "../components/landing/ChainProof";
import "./Landing.css";
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
    <div className="fb-root fb-mkt lx lv">
      <button type="button" className="lv-announce" onClick={() => (demoOpen ? void openDemo() : goToSecurity("landing"))}>
        {demoOpen ? "Judging DuitDuit? Open the synthetic demo company in one click" : "How DuitDuit keeps every decision with a person"}
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 8h9M8.5 4.5 12 8l-3.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      <MegaNav />

      <header className="lv-hero">
        <Guilloche className="lv-hero-guilloche" />
        <p className="lv-pill">Finance copilot for Malaysian SMEs</p>
        <h1>See the cash gap three weeks before it hits.</h1>
        <p className="lv-lede">
          DuitDuit reads your bank, bills, payroll and invoices, warns you before cash runs short, finds financing that fits and drafts the fix. Nothing moves until you approve it.
        </p>
        <div className="lx-ctas lv-ctas">
          {demoOpen ? (
            <button className="lx-btn is-primary" type="button" onClick={() => void openDemo()} disabled={demoBusy}>
              {demoBusy ? "Opening the demo company…" : "Open the demo company"}
            </button>
          ) : (
            <button className="lx-btn is-primary" type="button" onClick={() => show("signup")}>Get started</button>
          )}
          <button className="lx-btn is-quiet" type="button" onClick={() => document.getElementById("landing-product")?.scrollIntoView({ behavior: "smooth" })}>See how it works</button>
        </div>
        <div className="lv-hero-stage">
          <HeroApp />
          <p className="lv-fine">A replay of the app's own screens and figures, with the synthetic demo company.</p>
        </div>
      </header>

      <section className="lv-frame" aria-labelledby="lv-sources-title">
        <h2 id="lv-sources-title" className="lv-two-tone"><span>Reads what you already have.</span> Bank files, bills, payroll and e-invoices, with names and amounts protected before any AI sees them.</h2>
        <SourcesGrid />
      </section>

      <section className="lv-frame" id="landing-product" aria-labelledby="lx-product-title">
        <h2 id="lx-product-title" className="lv-two-tone"><span>One day at a small importer.</span> Cash flow, financing and analysis, all from the same records, so the numbers agree from page to page.</h2>
        <DayRail />
      </section>

      <section className="lv-frame" aria-labelledby="lv-desks-title">
        <h2 id="lv-desks-title" className="lv-two-tone"><span>Every position has a desk.</span> Agents prepare the work for each role. People decide, and money always needs two of them.</h2>
        <Desks />
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
          <ChainProof />
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

      <section className="lx-closing lv-closing">
        <h2>Finance work that waits for you.</h2>
        <p>Agents prepare it. You decide. Every step is on the record.</p>
        <div className="lx-ctas">
          {demoOpen ? (
            <button className="lx-btn is-primary" type="button" onClick={() => void openDemo()} disabled={demoBusy}>Open the demo company</button>
          ) : (
            <button className="lx-btn is-primary" type="button" onClick={() => show("signup")}>Get started</button>
          )}
          <button className="lx-btn is-quiet" type="button" onClick={() => show("login")}>Log in</button>
        </div>
      </section>

      <MarketingFooter />

      <CookieConsentBanner onReadMore={() => goToLegal("privacy", "landing")} />
      <SupportWidget topics={supportTopics} onEmail={() => { window.location.href = "mailto:hello@duitduit.example"; }} />
    </div>
  );
}
