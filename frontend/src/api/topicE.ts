// Topic E endpoints. Shapes mirror docs/api/topic-e-contract.json; every
// response says whether its data is a canned stub or computed live.
import { authenticatedFetch, parse } from "./client";

export type DataMode = "stub" | "live";

export type JobFunction =
  | "owner"
  | "operations"
  | "finance"
  | "sales"
  | "customer_service"
  | "marketing"
  | "procurement"
  | "logistics"
  | "production"
  | "hr"
  | "compliance";

export type AutonomyLevel = "L0" | "L1" | "L2" | "L3";

export type ReviewStatus = "pending" | "awaiting_second_approval" | "approved" | "edited" | "rejected";

export interface EvidenceRef {
  label: string;
  source: string;
}

export interface ReviewApproval {
  approver_id: string;
  approved_at: string;
}

export interface ReviewAction {
  id: string;
  agent_id: string;
  title: string;
  summary: string;
  autonomy_level: AutonomyLevel;
  reviewer_job_function: JobFunction;
  status: ReviewStatus;
  amount: string | null;
  draft: string | null;
  evidence: EvidenceRef[];
  created_at: string;
  approvals: ReviewApproval[];
  can_decide: boolean;
}

export interface ReviewInboxResponse {
  data_mode: DataMode;
  job_functions: JobFunction[];
  actions: ReviewAction[];
}

export interface ReviewDecisionRequest {
  decision: "approve" | "edit" | "reject";
  edited_draft?: string;
  reason?: string;
}

export interface ReviewDecisionResponse {
  data_mode: DataMode;
  action: ReviewAction;
}

export async function fetchReviewInbox(jobFunction?: JobFunction): Promise<ReviewInboxResponse> {
  const query = jobFunction ? `?job_function=${encodeURIComponent(jobFunction)}` : "";
  return parse<ReviewInboxResponse>(await authenticatedFetch(`/review-inbox${query}`));
}

export async function decideReviewAction(
  actionId: string,
  request: ReviewDecisionRequest,
): Promise<ReviewDecisionResponse> {
  return parse<ReviewDecisionResponse>(
    await authenticatedFetch(`/review-inbox/${encodeURIComponent(actionId)}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }),
  );
}

/** Items the signed-in person can act on now: the sidebar badge count. */
export function decidableCount(actions: ReviewAction[]): number {
  return actions.filter(
    (a) => a.can_decide && (a.status === "pending" || a.status === "awaiting_second_approval"),
  ).length;
}

// ── Cash flow ───────────────────────────────────────────────────────────────

export type ForecastHorizon = 30 | 60 | 90;

export interface ForecastPoint {
  day: number;
  date: string;
  best: string;
  likely: string;
  worst: string;
}

export interface Shortfall {
  day: number;
  date: string;
  likely_balance: string;
  minimum_balance: string;
  gap: string;
}

export interface ForecastAlert {
  id: string;
  severity: "info" | "warning" | "critical";
  title: string;
  detail: string;
  day: number;
  date: string;
}

export interface CashSignal {
  id: string;
  source_agent: string;
  job_function: JobFunction;
  /** "risk" signals annotate the forecast; they never move the balance. */
  kind: "inflow" | "outflow" | "risk";
  label: string;
  amount_myr: string;
  source_currency: string;
  source_amount: string | null;
  fx_rate: string | null;
  best_day: number;
  likely_day: number | null;
  worst_day: number | null;
  probability: number;
  affects: string | null;
}

export interface ForecastResponse {
  data_mode: DataMode;
  as_of: string;
  currency: "MYR";
  horizon_days: number;
  opening_balance: string;
  minimum_balance: string;
  points: ForecastPoint[];
  shortfall: Shortfall | null;
  alerts: ForecastAlert[];
  drivers: CashSignal[];
}

export interface AgentCashTotal {
  agent_id: string;
  job_function: JobFunction;
  inflow_total: string;
  outflow_total: string;
  at_risk_total: string;
  signal_count: number;
}

export interface CashSignalsResponse {
  data_mode: DataMode;
  horizon_days: number;
  signals: CashSignal[];
  by_agent: AgentCashTotal[];
}

export interface EventShift {
  event_id: string;
  shift_days: number;
}

export async function fetchForecast(horizonDays: ForecastHorizon = 90): Promise<ForecastResponse> {
  return parse<ForecastResponse>(await authenticatedFetch(`/cashflow/forecast?horizon_days=${horizonDays}`));
}

export async function runScenario(horizonDays: ForecastHorizon, shifts: EventShift[]): Promise<ForecastResponse> {
  return parse<ForecastResponse>(
    await authenticatedFetch("/cashflow/scenarios", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ horizon_days: horizonDays, shifts }),
    }),
  );
}

export async function fetchCashSignals(horizonDays: ForecastHorizon = 90): Promise<CashSignalsResponse> {
  return parse<CashSignalsResponse>(await authenticatedFetch(`/cashflow/signals?horizon_days=${horizonDays}`));
}

/** Ringgit with two decimals, e.g. "RM20,560.00". */
export function ringgit(amount: string | number | null): string {
  if (amount === null) return "—";
  const value = typeof amount === "number" ? amount : Number(amount);
  if (!Number.isFinite(value)) return `RM${amount}`;
  const sign = value < 0 ? "−" : "";
  return sign + "RM" + Math.abs(value).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
