import type { ReactNode } from "react";
import { Wordmark } from "./Logo";
import { useAppState } from "../lib/appState";
import "./AuthShell.css";

/**
 * The sign-in and sign-up frame, Attio-style: the wordmark at the top, one narrow
 * centred column, and the legal line at the foot. Nothing competes with the form.
 */
export function AuthShell({ children, from = "login" }: { children: ReactNode; from?: "login" | "signup" }) {
  const { show, goToLegal, goToSecurity } = useAppState();
  return (
    <div className="fb-root fb-mkt dd-auth">
      <header className="dd-auth-top">
        <Wordmark onClick={() => show("landing")} />
      </header>
      <main className="dd-auth-main">{children}</main>
      <footer className="dd-auth-foot">
        <p>
          By continuing you agree to the{" "}
          <button type="button" onClick={() => goToLegal("terms", from)}>Terms of service</button> and the{" "}
          <button type="button" onClick={() => goToLegal("privacy", from)}>Privacy policy</button>.
        </p>
        <nav aria-label="About">
          <span>© 2026 DuitDuit prototype</span>
          <button type="button" onClick={() => goToSecurity(from)}>How we protect your data</button>
        </nav>
      </footer>
    </div>
  );
}
