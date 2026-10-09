import { useState, type ReactNode } from "react";
import { useAppState, type Screen } from "../lib/appState";
import { PAGE_TITLES } from "../lib/screens";
import { useAuth } from "../auth/AuthProvider";
import { PARENT_SCREEN, canOpen } from "../lib/access";
import { useI18n } from "../lib/i18n";
import { PERSONAS } from "../lib/personas";
import { useActiveSection, useScrollY } from "../lib/interactivity";
import { useUiChrome } from "../lib/uiChrome";
import { LogoMark, Wordmark } from "./Logo";
import { NotificationBell } from "./NotificationBell";

const MARKETING_SECTIONS = ["landing-flow", "landing-agents", "landing-proof", "landing-why", "landing-pricing", "landing-faq"];

export function LandingNav() {
  const { show } = useAppState();
  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView();
  return (
    <nav className="fb-nav">
      <Wordmark onClick={() => show("landing")} />
      <div className="fb-nav-links">
        <span tabIndex={0} role="button" onClick={() => scrollTo("landing-flow")}>Product</span>
        <span tabIndex={0} role="button" onClick={() => scrollTo("landing-agents")}>AI Agents</span>
        <span tabIndex={0} role="button" onClick={() => scrollTo("landing-proof")}>Proof</span>
        <span tabIndex={0} role="button" onClick={() => scrollTo("landing-why")}>Why Us</span>
        <span tabIndex={0} role="button" onClick={() => scrollTo("landing-pricing")}>Pricing</span>
      </div>
      <div className="fb-nav-actions">
        <span style={{ cursor: "pointer", color: "var(--ink-soft)" }} tabIndex={0} role="button" onClick={() => show("login")}>Log in</span>
        <button className="fb-btn fb-btn-solid" onClick={() => show("signup")}>Get Started</button>
      </div>
    </nav>
  );
}

const MARKETING_NAV_ITEMS = [
  { id: "landing-flow", label: "Product" },
  { id: "landing-agents", label: "AI Agents" },
  { id: "landing-proof", label: "Proof" },
  { id: "landing-why", label: "Why Us" },
  { id: "landing-pricing", label: "Pricing" },
  { id: "landing-faq", label: "FAQ" },
];

export function MarketingNav() {
  const { show } = useAppState();
  const scrollY = useScrollY();
  const active = useActiveSection(MARKETING_SECTIONS);
  const [menuOpen, setMenuOpen] = useState(false);
  const scrollTo = (id: string) => {
    setMenuOpen(false);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };
  const linkClass = (id: string) => (active === id ? "is-current" : undefined);
  return (
    <>
      <nav className={"fb-mkt-nav" + (scrollY > 12 ? " is-scrolled" : "")}>
        <button className="fb-mkt-wordmark" onClick={() => show("landing")}>
          <LogoMark large />FINBRAIN OS
        </button>
        <div className="fb-mkt-nav-links">
          {MARKETING_NAV_ITEMS.map((item) => (
            <span key={item.id} className={linkClass(item.id)} tabIndex={0} role="button" onClick={() => scrollTo(item.id)}>{item.label}</span>
          ))}
        </div>
        <div className="fb-mkt-nav-actions">
          <span tabIndex={0} role="button" onClick={() => show("login")}>Log in</span>
          <button className="fb-mkt-btn is-accent" onClick={() => show("signup")}>Get Started</button>
          <button
            className={"fb-mkt-nav-toggle" + (menuOpen ? " is-open" : "")}
            type="button"
            aria-expanded={menuOpen}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen((v) => !v)}
          >
            <span /><span /><span />
          </button>
        </div>
        {menuOpen && (
          <div className="fb-mkt-nav-mobile-menu" role="menu">
            {MARKETING_NAV_ITEMS.map((item) => (
              <span key={item.id} className={linkClass(item.id)} tabIndex={0} role="menuitem" onClick={() => scrollTo(item.id)}>{item.label}</span>
            ))}
          </div>
        )}
      </nav>
      {/* Rendered as a sibling of <nav>, not a child: .fb-mkt-nav has
          backdrop-filter, which (per spec, like transform/filter) makes it
          the containing block for any position:fixed descendant -- so a
          fixed backdrop nested inside it would resolve inset:0 against the
          nav's own small box instead of the viewport. The menu itself stays
          inside <nav>; its position:absolute is anchored fine by the nav's
          own position:sticky, which that quirk doesn't affect. */}
      {menuOpen && <div className="fb-mkt-nav-backdrop" onClick={() => setMenuOpen(false)} />}
    </>
  );
}

export function ContextNav() {
  const { contextBack, returnTo, show } = useAppState();
  const backLabel = returnTo === "login" ? "← Back to login" : returnTo === "signup" ? "← Back to sign up" : "← Back to site";
  const ctaLabel = returnTo === "signup" ? "Continue signing up" : "Start free trial";
  return (
    <nav className="fb-nav">
      <Wordmark onClick={() => show("landing")} />
      <div className="fb-nav-links">
        <span tabIndex={0} role="button" onClick={contextBack}>{backLabel}</span>
      </div>
      <div className="fb-nav-actions">
        <span style={{ cursor: "pointer", color: "var(--ink-soft)" }} tabIndex={0} role="button" onClick={() => show("login")}>Log in</span>
        <button className="fb-btn fb-btn-solid" onClick={() => show("signup")}>{ctaLabel}</button>
      </div>
    </nav>
  );
}

const NAV_ICONS: Record<string, ReactNode> = {
  home: <><path d="M3 11l9-7 9 7" /><path d="M5 10v9a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1v-9" /></>,
  agents: <path d="M4 4h13a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3H9l-5 3v-3a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z" />,
  customers: <><circle cx="9" cy="7" r="3.2" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" /><circle cx="17.5" cy="8.5" r="2.4" /><path d="M15.3 12.3A5.2 5.2 0 0 1 21.5 17" /></>,
  einvoice: <path d="M6 2h9l3 3v17H6z M9 8h6M9 12h6M9 16h4" />,
  finance: <path d="M4 19V9M10 19V5M16 19v-7M22 19H2" />,
  audit: <path d="M12 3 20 6.5v5.3c0 4.7-3.2 8.9-8 10.2-4.8-1.3-8-5.5-8-10.2V6.5z" />,
  approvals: <path d="M9 12l2 2 4-4M12 3l8 4v5c0 4.5-3.2 8.5-8 10-4.8-1.5-8-5.5-8-10V7z" />,
  ingestion: <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 9l5-5 5 5M12 4v13" />,
  inbox: <path d="M22 12h-6l-2 3h-4l-2-3H2M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />,
  positions: <path d="M3 7h18v13H3zM8 7V4h8v3M3 12h18" />,
  autonomy: <path d="M12 2v3M5 8h14v11H5zM9 13h.01M15 13h.01M9 17h6" />,
  cashflow: <path d="M3 17l6-6 4 4 8-8M15 7h6v6" />,
  financing: <path d="M3 21h18M5 21V10l7-5 7 5v11M9 21v-6h6v6" />,
  team: <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M13 7a4 4 0 1 1-8 0a4 4 0 1 1 8 0M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />,
  trust: <path d="M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4" />,
  company: <path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16M16 9h2a2 2 0 0 1 2 2v10M2 21h20M8 7h4M8 11h4M8 15h4" />,
};

// Primary navigation, organised around the owner's day: today, asking and
// approving first, then money, daily work and the company. Pages that belong
// together (Workflows inside Review inbox, Financial intelligence inside Cash &
// finance, Audit & access inside Trust & audit) are tabs of their parent page.
const NAV_GROUPS: { label: string | null; items: { screen: Screen; key: string }[] }[] = [
  { label: null, items: [
    { screen: "home", key: "nav.home" },
    { screen: "agents", key: "nav.aiAgents" },
    { screen: "inbox", key: "nav.inbox" },
  ] },
  { label: "nav.group.money", items: [
    { screen: "cashflow", key: "nav.cashFinance" },
    { screen: "customers", key: "nav.customers" },
    { screen: "einvoice", key: "nav.einvoicing" },
    { screen: "financing", key: "nav.financing" },
  ] },
  { label: "nav.group.work", items: [
    { screen: "positions", key: "nav.positions" },
    { screen: "ingestion", key: "nav.ingestion" },
  ] },
  { label: "nav.group.company", items: [
    { screen: "team", key: "nav.team" },
    { screen: "autonomy", key: "nav.autonomy" },
    { screen: "company", key: "nav.company" },
    { screen: "trust", key: "nav.trustAudit" },
  ] },
];

export function Sidebar({ current, backTo, backLabel }: { current?: Screen; backTo?: () => void; backLabel?: string }) {
  const { show, approvalsCount, reviewInboxCount, askRole } = useAppState();
  const { identity } = useAuth();
  const role = identity?.role ?? askRole;
  const active = current ? (PARENT_SCREEN[current] ?? current) : undefined;
  const waiting = approvalsCount + reviewInboxCount;
  const groups = NAV_GROUPS
    .map((group) => ({ ...group, items: group.items.filter((item) => canOpen(item.screen, role)) }))
    .filter((group) => group.items.length > 0);
  const { t } = useI18n();
  const { sidebarOpen, openSidebar, closeSidebar } = useUiChrome();

  const navigate = (screen: Screen) => {
    closeSidebar();
    show(screen);
  };

  return (
    <>
      {!sidebarOpen && (
        <button
          className="fb-sidebar-toggle"
          type="button"
          onClick={openSidebar}
          aria-label="Open navigation"
          aria-expanded={sidebarOpen}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
        </button>
      )}
      {sidebarOpen && <div className="fb-sidebar-backdrop" onClick={closeSidebar} />}

      <aside className={"fb-sidebar" + (sidebarOpen ? " is-open" : "")}>
        <div className="fb-sidebar-top">
          <Wordmark onClick={() => navigate("landing")} />
          <button className="fb-sidebar-close" type="button" onClick={closeSidebar} aria-label="Close navigation">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
        </div>

        {backTo ? (
          <button className="fb-sidebar-back" type="button" onClick={backTo}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
            {backLabel}
          </button>
        ) : (
          <nav className="fb-sidebar-nav">
            {groups.map((group) => (
              <div className="fb-sidebar-group" key={group.label ?? "primary"}>
                {group.label && <div className="fb-sidebar-group-label">{t(group.label)}</div>}
                {group.items.map((link) => (
                  <button
                    key={link.screen}
                    className={"fb-sidebar-link" + (active === link.screen ? " is-current" : "")}
                    aria-current={active === link.screen ? "page" : undefined}
                    type="button"
                    onClick={() => navigate(link.screen)}
                  >
                    <span className="fb-sidebar-icon">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{NAV_ICONS[link.screen]}</svg>
                    </span>
                    <span className="fb-sidebar-label">{t(link.key)}</span>
                    {link.screen === "inbox" && waiting > 0 && (
                      <span className="fb-nav-badge" aria-label={`${waiting} waiting for you`}>{waiting}</span>
                    )}
                  </button>
                ))}
              </div>
            ))}
          </nav>
        )}

        {!backTo && (
          <div className="fb-sidebar-footer">
            <button
              className={"fb-sidebar-link" + (active === "settings" ? " is-current" : "")}
              type="button"
              onClick={() => navigate("settings")}
            >
              <span className="fb-sidebar-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </span>
              <span className="fb-sidebar-label">{t("nav.settings")}</span>
            </button>
          </div>
        )}
      </aside>
    </>
  );
}

export function AppTopBar({ current }: { current: Screen }) {
  const { show, askRole, displayName } = useAppState();
  const { openAsk, openPalette } = useUiChrome();
  const { identity, signOut } = useAuth();
  const { t } = useI18n();
  const [profileOpen, setProfileOpen] = useState(false);
  const activeRole = identity?.role ?? askRole;
  const email = identity?.email ?? "Authenticated user";
  const profileLabel = displayName || email;

  return (
    <div className="fb-topbar">
      <div className="fb-topbar-crumb">
        {current === "home" ? (
          <span className="fb-topbar-current">{PAGE_TITLES.home}</span>
        ) : (
          <>
            <span className="fb-topbar-home-link" tabIndex={0} role="button" onClick={() => show("home")} aria-label={`Go to ${PAGE_TITLES.home}`} title={`Go to ${PAGE_TITLES.home}`}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 11l9-7 9 7" /><path d="M5 10v9a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1v-9" /></svg>
            </span>
            <span className="fb-topbar-sep">/</span>
            <span className="fb-topbar-current">{PAGE_TITLES[current] ?? current}</span>
          </>
        )}
      </div>

      <button className="fb-topbar-search" type="button" onClick={openPalette}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
        <span>Search pages and actions…</span>
        <span className="fb-topbar-kbd">⌘K</span>
      </button>

      <div className="fb-topbar-actions">
        <NotificationBell />
        <button className="fb-topbar-ask" type="button" onClick={openAsk}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M4 4h13a3 3 0 0 1 3 3v7a3 3 0 0 1-3 3H9l-5 3v-3a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3z" /></svg>
          <span>Ask FinBrain</span>
        </button>

        <div
          className="fb-topbar-profile"
          onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node)) setProfileOpen(false);
          }}
        >
          <button className="fb-topbar-profile-trigger" type="button" onClick={() => setProfileOpen((v) => !v)} aria-haspopup="true" aria-expanded={profileOpen}>
            <span className="fb-topbar-avatar" aria-hidden="true">{profileLabel[0]?.toUpperCase() ?? "?"}</span>
            <span className="fb-topbar-profile-text">
              <span className="fb-topbar-profile-email">{profileLabel}</span>
              <span className="fb-topbar-profile-role">{PERSONAS[activeRole].label}</span>
            </span>
            <svg className="fb-topbar-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
          </button>
          {profileOpen && (
            <div className="fb-topbar-profile-menu" role="menu">
              <button className="fb-sidebar-link" type="button" onClick={() => { setProfileOpen(false); show("settings"); }}>{t("nav.settings")}</button>
              <button className="fb-sidebar-logout" type="button" onClick={() => void signOut().then(() => show("landing"))}>{t("nav.logout")}</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
