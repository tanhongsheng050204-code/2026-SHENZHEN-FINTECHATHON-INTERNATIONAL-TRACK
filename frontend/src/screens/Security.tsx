import { useAppState } from "../lib/appState";
import { ContextNav } from "../components/Nav";
import { Wordmark } from "../components/Logo";

const ITEMS = [
  {
    title: "Personal data is masked before it is stored",
    desc: "Names, contacts, account numbers and amounts are replaced by tokens encrypted with AES-GCM. A value is restored only for a role the policy allows, and staff never see customer contacts.",
    path: <><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></>,
  },
  {
    title: "Each company is walled off in the database",
    desc: "Requests run as restricted database roles under row-level security, so one company's rows are invisible to another, even by id. A lender's shared link only reaches that one company.",
    path: <><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" /><path d="M9.5 12l2 2 3.5-3.5" /></>,
  },
  {
    title: "Agents draft, people decide",
    desc: "Every proposal waits in the review inbox. Money needs a maker, a different checker and an authenticator code from the last five minutes. One switch stops every agent.",
    path: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 4-6 8-6s8 2 8 6" /><path d="M15 14.5l2 2 3.5-3.5" /></>,
  },
  {
    title: "Every decision is on a hash chain",
    desc: "Proposals, approvals, shared links and disclosures are recorded by kind and id, never by the words people typed, and the chain can be re-verified at any time.",
    path: <><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8M8 16h5" /></>,
  },
];

const STATUS = [
  ["PDPA-aligned data handling", "Built into the prototype"],
  ["Attack tests (42 offline tasks, mapped to OWASP agentic risks)", "Run on every build"],
  ["Independent penetration test", "Not started"],
  ["SOC 2 or ISO/IEC 27001 certification", "Not started"],
];

export default function Security() {
  const { goToSecurity, goToLegal } = useAppState();

  return (
    <div className="fb-root">
      <ContextNav />

      <div className="fb-page-body" style={{ maxWidth: "760px", paddingTop: "2.8rem" }}>
        <h1 className="fb-security-title">How DuitDuit protects your company's data</h1>
        <p className="fb-security-lede">This is a prototype. The controls below are built and tested; the certifications at the bottom are not done, and we say so.</p>

        <div className="fb-security-grid">
          {ITEMS.map((item) => (
            <div className="fb-security-item" key={item.title}>
              <svg className="fb-security-icon" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{item.path}</svg>
              <h3>{item.title}</h3>
              <p>{item.desc}</p>
            </div>
          ))}
        </div>

        <h2 className="fb-security-subtitle">Where things stand</h2>
        <div className="fb-settings-list">
          {STATUS.map(([what, state]) => (
            <div className="fb-settings-row" key={what}><span>{what}</span><span>{state}</span></div>
          ))}
        </div>

        <p className="fb-security-contact">Found a problem or have a question? <a href="mailto:security@duitduit.example" style={{ color: "var(--ink)" }}>security@duitduit.example</a></p>
      </div>

      <footer className="fb-footer">
        <div className="fb-footer-top">
          <div>
            <Wordmark />
            <p>Permission-aware AI for finance teams. This site is a prototype.</p>
          </div>
          <div className="fb-footer-links">
            <span tabIndex={0} role="button" onClick={() => goToSecurity()}>Security</span>
            <span tabIndex={0} role="button" onClick={() => goToLegal("privacy")}>Privacy Policy</span>
            <span tabIndex={0} role="button" onClick={() => goToLegal("terms")}>Terms of Service</span>
            <a href="mailto:hello@duitduit.example">Contact us</a>
          </div>
        </div>
        <div className="fb-footer-bottom">© 2026 DuitDuit. Prototype for demonstration purposes — not a live product.</div>
      </footer>
    </div>
  );
}
