import { useEffect, useRef, useState } from "react";
import { useAppState } from "../lib/appState";
import { LogoMark } from "./Logo";
import "./MegaNav.css";

// The public site's menu bar, laid out like Attio's: two dropdown menus with
// columns of titled links, then plain links. Every product link opens the help
// article that explains it, so nothing here promises more than the app does.

type Item = { title: string; body?: string; go: () => void };
type Column = { heading: string; items: Item[] };

function helpAt(show: (s: "help") => void, id: string) {
  return () => {
    show("help");
    window.history.replaceState(window.history.state, "", `/help#${id}`);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  };
}

export function MegaNav() {
  const { show, goToSecurity, goToLegal } = useAppState();
  const [open, setOpen] = useState<"product" | "resources" | null>(null);
  const [mobile, setMobile] = useState(false);
  const bar = useRef<HTMLElement>(null);
  const help = (id: string) => helpAt(show, id);

  useEffect(() => {
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !bar.current?.contains(event.target as Node)) {
        setOpen(null);
        setMobile(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, []);

  const product: Column[] = [
    {
      heading: "Cash",
      items: [
        { title: "Cash forecast", body: "See the gap weeks before it hits", go: help("forecast") },
        { title: "Financial analysis", body: "Profit, loss and ratios with formulas", go: help("analysis") },
        { title: "Collections board", body: "Who owes what, at a glance", go: help("collections") },
      ],
    },
    {
      heading: "Agents & automations",
      items: [
        { title: "Ask DuitDuit", body: "Ask, or tell it what to prepare", go: help("assistant") },
        { title: "Review inbox", body: "Every proposal waits for a person", go: help("inbox") },
        { title: "Automations & sequences", body: "Follow-up prepared on time", go: help("automations") },
      ],
    },
    {
      heading: "Trust & connections",
      items: [
        { title: "Financing & Passport", body: "Matches a lender can verify", go: help("financing") },
        { title: "Data sources", body: "Bank, e-invoices, email, Telegram", go: help("data") },
        { title: "Team chat", body: "Slack and WhatsApp notices", go: help("chat") },
      ],
    },
  ];
  const productSide: Column[] = [
    {
      heading: "DuitDuit for",
      items: [
        { title: "Owners", go: help("roles") },
        { title: "Finance teams", go: help("roles") },
        { title: "Lenders", go: help("financing") },
      ],
    },
    {
      heading: "Get started",
      items: [
        { title: "Create a company", go: () => show("signup") },
        { title: "Pricing", go: () => show("pricing") },
      ],
    },
  ];
  const resources: Column[] = [
    {
      heading: "Support",
      items: [
        { title: "Help center", body: "How each part of DuitDuit works", go: () => show("help") },
        { title: "Security", body: "How your data is protected", go: () => goToSecurity("landing") },
        { title: "Changelog", body: "Everything we shipped, by day", go: () => show("changelog") },
      ],
    },
  ];
  const resourcesSide: Column[] = [
    {
      heading: "Company",
      items: [
        { title: "Privacy policy", go: () => goToLegal("privacy", "landing") },
        { title: "Terms of service", go: () => goToLegal("terms", "landing") },
        { title: "Email the team", go: () => window.location.assign("mailto:hello@duitduit.example") },
      ],
    },
  ];

  const pick = (item: Item) => {
    setOpen(null);
    setMobile(false);
    item.go();
  };

  const panel = (id: "product" | "resources", columns: Column[], side: Column[]) => (
    <div className={"mn-panel is-" + id} role="menu" id={`mn-${id}`}>
      <div className="mn-columns">
        {columns.map((column) => (
          <div key={column.heading} className="mn-column">
            <div className="mn-heading">{column.heading}</div>
            {column.items.map((item) => (
              <button key={item.title} type="button" role="menuitem" className="mn-item" onClick={() => pick(item)}>
                <span className="mn-item-title">{item.title}</span>
                {item.body && <span className="mn-item-body">{item.body}</span>}
              </button>
            ))}
          </div>
        ))}
      </div>
      <div className="mn-side">
        {side.map((column) => (
          <div key={column.heading} className="mn-column">
            <div className="mn-heading">{column.heading}</div>
            {column.items.map((item) => (
              <button key={item.title} type="button" role="menuitem" className="mn-side-item" onClick={() => pick(item)}>{item.title}</button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );

  const trigger = (id: "product" | "resources", label: string) => (
    <div className="mn-trigger-wrap" onMouseEnter={() => setOpen(id)} onMouseLeave={() => setOpen(null)}>
      <button type="button" className={"mn-trigger" + (open === id ? " is-open" : "")} aria-expanded={open === id} aria-controls={`mn-${id}`} onClick={() => setOpen(open === id ? null : id)}>
        {label}
        <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M3 4.5 6 7.5l3-3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </button>
      {open === id && (id === "product" ? panel("product", product, productSide) : panel("resources", resources, resourcesSide))}
    </div>
  );

  return (
    <nav className="mn" ref={bar} aria-label="Main">
      <button type="button" className="mn-brand" onClick={() => show("landing")}>
        <LogoMark large />DuitDuit
      </button>
      <div className="mn-links">
        {trigger("product", "Product")}
        {trigger("resources", "Resources")}
        <button type="button" className="mn-link" onClick={() => goToSecurity("landing")}>Security</button>
        <button type="button" className="mn-link" onClick={() => show("pricing")}>Pricing</button>
      </div>
      <div className="mn-actions">
        <button type="button" className="mn-signin" onClick={() => show("login")}>Log in</button>
        <button type="button" className="mn-start" onClick={() => show("signup")}>Get started</button>
        <button type="button" className={"mn-toggle" + (mobile ? " is-open" : "")} aria-expanded={mobile} aria-label={mobile ? "Close menu" : "Open menu"} onClick={() => setMobile((v) => !v)}>
          <span /><span /><span />
        </button>
      </div>
      {mobile && (
        <div className="mn-mobile" role="menu">
          {[...product, ...resources].flatMap((c) => c.items).map((item) => (
            <button key={item.title} type="button" role="menuitem" onClick={() => pick(item)}>{item.title}</button>
          ))}
          <button type="button" role="menuitem" onClick={() => pick({ title: "Pricing", go: () => show("pricing") })}>Pricing</button>
        </div>
      )}
    </nav>
  );
}
