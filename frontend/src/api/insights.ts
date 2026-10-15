// Unusual bills and payments, the checker agent's findings, privacy-protected
// benchmarks and the payment-delay model. The backend decides who may see what.
import { authenticatedFetch, parse } from "./client";
import type { DataMode } from "./topicE";

export type AnomalyKind = "unusual_amount" | "possible_duplicate" | "new_supplier_large" | "possible_duplicate_payment";

export interface AnomalyFinding {
  ref: string;
  kind: AnomalyKind;
  severity: "high" | "medium";
  label: string;
  amount_myr: string;
  score: number | null;
  reason: string;
}

export interface AnomaliesResponse {
  data_mode: DataMode;
  findings: AnomalyFinding[];
  bills_checked: number;
  payments_checked: number;
}

export async function fetchAnomalies(): Promise<AnomaliesResponse> {
  return parse<AnomaliesResponse>(await authenticatedFetch("/insights/anomalies"));
}

export async function sendAnomalyForReview(ref: string): Promise<string> {
  const body = await parse<{ action_id: string }>(
    await authenticatedFetch(`/insights/anomalies/${encodeURIComponent(ref)}/review`, { method: "POST" }),
  );
  return body.action_id;
}

export interface PolicyCheck {
  name: "evidence" | "owner_escalation" | "two_person_rule" | "holds" | "anomalies";
  status: "pass" | "warn" | "fail";
  detail: string;
}

export async function fetchPolicyChecks(actionId: string): Promise<PolicyCheck[]> {
  return (await parse<{ checks: PolicyCheck[] }>(await authenticatedFetch(`/insights/checks/${encodeURIComponent(actionId)}`))).checks;
}

export interface BenchmarksResponse {
  status: "measured" | "not_enough_companies";
  epsilon: number;
  min_companies: number;
  metrics: { name: "median_days_late"; your_value: number | null; peer_value: number | null; noise_scale: number | null }[];
}

export async function fetchBenchmarks(): Promise<BenchmarksResponse> {
  return parse<BenchmarksResponse>(await authenticatedFetch("/insights/benchmarks"));
}

export interface PaymentModelResponse {
  data_mode: DataMode;
  learned_from: number;
  default_extra_days: number;
  company_extra_days: number;
  company_learned: boolean;
  customers: { customer_id: number; label: string; paid_invoices: number; median_days_late: number; worst_extra_days: number }[];
  backtest: { checked: number; within: number; coverage_pct: number } | null;
}

export async function fetchPaymentModel(): Promise<PaymentModelResponse> {
  return parse<PaymentModelResponse>(await authenticatedFetch("/cashflow/payment-model"));
}

export interface ReconciliationLine {
  ref: string;
  posted_on: string;
  direction: "credit" | "debit";
  amount: string;
  description: string;
  status: "matched" | "unmatched";
  matched_to: string | null;
  review_action_id: string | null;
}

export interface ReconciliationResponse {
  data_mode: DataMode;
  period: string;
  label: string;
  lines: number;
  matched: number;
  window_days: number;
  items: ReconciliationLine[];
}

export async function fetchReconciliation(period?: string): Promise<ReconciliationResponse> {
  const query = period ? `?period=${encodeURIComponent(period)}` : "";
  return parse<ReconciliationResponse>(await authenticatedFetch(`/reconciliation${query}`));
}

export async function explainBankLine(ref: string): Promise<string> {
  const body = await parse<{ action_id: string }>(
    await authenticatedFetch(`/reconciliation/${encodeURIComponent(ref)}/explain`, { method: "POST" }),
  );
  return body.action_id;
}
