import type { Role } from "../api/client";
import type { Screen } from "./screens";

// Which roles may open each page. Mirrors the backend's role checks so the
// sidebar never offers a page that would only answer "no access". The backend
// remains the authority; this only hides what a person cannot use.
const EVERYONE: Role[] = ["general_employee", "finance_ops", "owner_director", "compliance"];
const FINANCE_READ: Role[] = ["finance_ops", "owner_director", "compliance"];
const FINANCE_WORK: Role[] = ["finance_ops", "owner_director"];
const OVERSIGHT: Role[] = ["owner_director", "compliance"];

const SCREEN_ROLES: Partial<Record<Screen, Role[]>> = {
  home: EVERYONE,
  agents: EVERYONE,
  inbox: EVERYONE,
  positions: EVERYONE,
  autonomy: EVERYONE,
  customers: EVERYONE,
  settings: EVERYONE,
  cashflow: FINANCE_READ,
  finance: FINANCE_READ,
  financing: FINANCE_READ,
  einvoice: FINANCE_READ,
  "einvoice-detail": FINANCE_READ,
  company: FINANCE_READ,
  approvals: FINANCE_READ,
  ingestion: FINANCE_WORK,
  team: OVERSIGHT,
  trust: OVERSIGHT,
  audit: ["compliance"],
};

export function canOpen(screen: Screen, role: Role | null | undefined): boolean {
  const allowed = SCREEN_ROLES[screen];
  if (!allowed) return true;
  return role ? allowed.includes(role) : false;
}

// Pages that live inside another page's tabs: the sidebar highlights the parent.
export const PARENT_SCREEN: Partial<Record<Screen, Screen>> = {
  approvals: "inbox",
  finance: "cashflow",
  audit: "trust",
  "einvoice-detail": "einvoice",
};
