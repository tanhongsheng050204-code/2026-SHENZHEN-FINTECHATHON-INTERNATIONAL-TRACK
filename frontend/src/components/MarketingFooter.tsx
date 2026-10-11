import { useAppState } from "../lib/appState";
import { Wordmark } from "./Logo";

/** The public site's footer, shared by the landing page and the resource pages. */
export function MarketingFooter() {
  const { show, goToSecurity, goToLegal } = useAppState();
  return (
    <footer className="lx-footer lv-footer">
      <div className="lv-footer-brand">
        <Wordmark />
        <p>Finance copilot for Malaysian SMEs. A prototype built for the 2026 Shenzhen FinTech competition, shown with a synthetic company.</p>
      </div>
      <nav aria-label="Product">
        <h3>Product</h3>
        <button type="button" onClick={() => show("landing")}>Overview</button>
        <button type="button" onClick={() => show("pricing")}>Pricing</button>
        <button type="button" onClick={() => show("signup")}>Create a company</button>
      </nav>
      <nav aria-label="Resources">
        <h3>Resources</h3>
        <button type="button" onClick={() => show("help")}>Help center</button>
        <button type="button" onClick={() => show("changelog")}>Changelog</button>
        <button type="button" onClick={() => goToSecurity("landing")}>Security</button>
      </nav>
      <nav aria-label="Company">
        <h3>Company</h3>
        <button type="button" onClick={() => goToLegal("privacy", "landing")}>Privacy policy</button>
        <button type="button" onClick={() => goToLegal("terms", "landing")}>Terms of service</button>
        <a href="mailto:hello@duitduit.example">Email the team</a>
      </nav>
    </footer>
  );
}
