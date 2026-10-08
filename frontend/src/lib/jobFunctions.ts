import type { JobFunction } from "../api/topicE";

/** Short position names for tabs, tables and labels. */
export const JOB_LABELS: Record<JobFunction, string> = {
  owner: "Owner",
  operations: "Operations",
  finance: "Finance",
  sales: "Sales",
  customer_service: "Customer service",
  marketing: "Marketing",
  procurement: "Purchasing",
  logistics: "Logistics",
  production: "Production",
  hr: "HR",
  compliance: "Compliance",
};
