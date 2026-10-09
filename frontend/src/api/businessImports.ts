import { ApiError, authenticatedFetch, parse } from "./client";
import type { ImportSchema } from "./importSchemas";

export const IMPORT_LABELS: Record<ImportSchema, string> = {
  bank_statement_v1: "Bank statement",
  payables_register_v1: "Payables register",
  purchase_orders_v1: "Purchase orders",
  stock_v1: "Stock snapshot",
  payroll_v1: "Payroll",
  marketing_spend_v1: "Marketing spend",
  marketplace_payouts_v1: "Marketplace payouts",
  sales_pipeline_v1: "Sales pipeline",
};

export interface ImportIssue { row: number; field: string; code: string }
export interface CsvImportPreview {
  data_mode: "live";
  schema_name: ImportSchema;
  mapping_id: string | null;
  fingerprint: string;
  total_rows: number;
  accepted_rows: number;
  duplicate_rows: number;
  issues: ImportIssue[];
  can_commit: boolean;
}
export interface CsvImportResult {
  data_mode: "live";
  schema_name: ImportSchema;
  batch_id: string;
  imported_rows: number;
  duplicate_rows: number;
  replayed: boolean;
  synthetic: boolean;
}
export interface ImportBatch {
  id: string;
  schema_name: ImportSchema;
  imported_rows: number;
  duplicate_rows: number;
  synthetic: boolean;
  created_at: string;
}
export class ImportValidationError extends Error {
  constructor(public readonly issues: ImportIssue[]) {
    super("import_validation_failed");
  }
}

export async function fetchImportBatches(): Promise<ImportBatch[]> {
  return (await parse<{ batches: ImportBatch[] }>(
    await authenticatedFetch("/imports/batches?limit=10"),
  )).batches;
}

async function request<T>(
  schema: ImportSchema, action: "preview" | "commit", csvText: string, mappingId?: string,
): Promise<T> {
  const response = await authenticatedFetch(`/imports/${schema}/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ csv_text: csvText, mapping_id: mappingId || null }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    if (body.detail?.code === "import_validation_failed" && Array.isArray(body.detail.issues)) {
      throw new ImportValidationError(body.detail.issues);
    }
    throw new ApiError(
      typeof body.detail === "string" ? body.detail : "invalid_request",
      response.status, response.headers.get("X-Request-ID"),
    );
  }
  return response.json() as Promise<T>;
}

export const previewBusinessCsv = (schema: ImportSchema, text: string, mapping?: string) =>
  request<CsvImportPreview>(schema, "preview", text, mapping);
export const commitBusinessCsv = (schema: ImportSchema, text: string, mapping?: string) =>
  request<CsvImportResult>(schema, "commit", text, mapping);
