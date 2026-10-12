// Every screen id: the app's routes and the URL paths that restore them.
export const SCREENS = [
  "landing", "login", "signup", "onboarding", "security", "legal", "pricing", "changelog", "help",
  "home", "agents", "customers", "einvoice", "einvoice-detail", "finance", "audit", "approvals", "ingestion", "settings",
  // Topic E pages
  "inbox", "positions", "autonomy", "cashflow", "analysis", "collections", "financing", "team", "trust", "activity", "company",
] as const;

export type Screen = (typeof SCREENS)[number];

// Pages anyone can open without signing in.
export const PUBLIC_SCREENS: readonly Screen[] = ["landing", "login", "signup", "security", "legal", "pricing", "changelog", "help"];

// The browser-tab title for each screen; signed-in pages match the sidebar labels.
export const PAGE_TITLES: Record<Screen, string> = {
  landing: "SME Finance Copilot",
  login: "Sign in",
  signup: "Create account",
  onboarding: "Welcome",
  security: "Security",
  legal: "Legal",
  pricing: "Pricing",
  changelog: "Changelog",
  help: "Help center",
  home: "Today",
  agents: "Ask DuitDuit",
  customers: "Customers",
  einvoice: "e-Invoicing",
  "einvoice-detail": "e-Invoicing",
  finance: "Cash & finance",
  audit: "Trust & audit",
  approvals: "Review inbox",
  ingestion: "Data sources",
  settings: "My preferences",
  inbox: "Review inbox",
  positions: "Positions",
  autonomy: "Agents & autonomy",
  cashflow: "Cash & finance",
  analysis: "Financial analysis",
  collections: "Collections",
  financing: "Financing & Passport",
  team: "Team",
  trust: "Trust & audit",
  activity: "Security activity",
  company: "Company settings",
};
