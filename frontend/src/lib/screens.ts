// Every screen id: the app's routes and the URL paths that restore them.
export const SCREENS = [
  "landing", "login", "signup", "onboarding", "security", "legal",
  "home", "agents", "customers", "einvoice", "einvoice-detail", "finance", "audit", "approvals", "ingestion", "settings",
  // Topic E pages
  "inbox", "positions", "autonomy", "cashflow", "financing", "team", "trust",
] as const;

export type Screen = (typeof SCREENS)[number];
