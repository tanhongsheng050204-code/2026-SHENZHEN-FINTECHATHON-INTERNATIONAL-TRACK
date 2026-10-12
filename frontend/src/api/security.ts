// Security activity, sign-ins, the incident register, the data protection officer
// and PDPA portability exports. The backend decides who may do what.
import { authenticatedFetch, parse } from "./client";

const JSON_HEADERS = { "Content-Type": "application/json" };

async function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  return parse<T>(
    await authenticatedFetch(path, {
      method,
      headers: body === undefined ? undefined : JSON_HEADERS,
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
}

export interface SignIn {
  at: string;
  browser: string;
  system: string;
  method: string;
  new_device: boolean;
}

export async function fetchMySignIns(): Promise<SignIn[]> {
  return (await parse<{ sign_ins: SignIn[] }>(await authenticatedFetch("/security/sign-ins"))).sign_ins;
}

export type Severity = "info" | "warning" | "critical";

export interface SecurityEvent {
  at: string;
  kind: string;
  severity: Severity;
  title: string;
  actor_role: string;
}

export async function fetchSecurityActivity(): Promise<SecurityEvent[]> {
  return (await parse<{ events: SecurityEvent[] }>(await authenticatedFetch("/security/activity"))).events;
}

export type IncidentKind =
  | "unauthorized_access"
  | "lost_or_stolen_device"
  | "data_sent_to_wrong_person"
  | "system_compromise"
  | "vendor_breach"
  | "other";
export type DataKind = "contact_details" | "identity_numbers" | "financial_records" | "employee_records" | "credentials";
export type IncidentStep = "contained" | "assessed" | "commissioner_notified" | "individuals_notified" | "closed";

export interface IncidentRequest {
  kind: IncidentKind;
  data_kinds: DataKind[];
  people_affected: number;
  significant_harm: boolean;
  detected_on: string;
}

export interface Incident extends IncidentRequest {
  id: string;
  opened_at: string;
  opened_by_role: string;
  status: "open" | "closed";
  checklist: { step: IncidentStep; required: boolean; done: boolean; done_at: string | null; done_by_role: string | null }[];
}

export async function fetchIncidents(): Promise<Incident[]> {
  return (await parse<{ incidents: Incident[] }>(await authenticatedFetch("/security/incidents"))).incidents;
}

export function openIncident(request: IncidentRequest): Promise<Incident> {
  return send("/security/incidents", "POST", request);
}

export function completeIncidentStep(id: string, step: IncidentStep): Promise<Incident> {
  return send(`/security/incidents/${encodeURIComponent(id)}/steps`, "POST", { step });
}

export async function draftIncidentNotice(id: string, audience: "commissioner" | "individuals"): Promise<string> {
  return (await send<{ action_id: string }>(`/security/incidents/${encodeURIComponent(id)}/notices`, "POST", { audience })).action_id;
}

export interface Officer {
  user_id: string;
  display_name: string;
  email_masked: string;
  role: string;
}

export async function fetchOfficer(): Promise<Officer | null> {
  return (await parse<{ officer: Officer | null }>(await authenticatedFetch("/security/dpo"))).officer;
}

export async function nameOfficer(userId: string): Promise<Officer | null> {
  return (await send<{ officer: Officer | null }>("/security/dpo", "PUT", { user_id: userId })).officer;
}

/** PDPA portability: one customer's records as a JSON document (Compliance, step-up). */
export async function exportCustomerData(customerId: number): Promise<Blob> {
  const response = await authenticatedFetch(`/privacy/customers/${customerId}/export`, { method: "POST" });
  const body = await parse<unknown>(response);
  return new Blob([JSON.stringify(body, null, 2)], { type: "application/json" });
}
