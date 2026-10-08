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
