import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { ApiError, friendlyLoadError } from "../api/client";
import {
  IMPORT_LABELS, ImportValidationError, commitBusinessCsv, fetchImportBatches,
  previewBusinessCsv, type CsvImportPreview, type ImportBatch, type ImportIssue,
} from "../api/businessImports";
import { IMPORT_FIELDS, type ImportSchema } from "../api/importSchemas";
import { fetchImportMappings, type ImportMapping } from "../api/topicE";

const MAX_BYTES = 2_000_000;
const ISSUE_MESSAGES: Record<string, string> = {
  mapping_required: "Map your column headers below, then preview again.",
  mapping_not_found_or_headers_changed: "The selected mapping does not match this file's columns.",
  immutable_record_conflict: "This reference already exists with different facts. Check the source record.",
  conflicting_duplicate: "This file repeats a reference with different facts.",
  payroll_period_sealed: "Payroll for this period is already imported. Check the existing run.",
  prompt_injection: "Instructions inside the file were blocked. Remove them and check the source.",
  supplier_bank_change: "A supplier account change needs a separate verified review.",
};

function message(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "import_job_function_required") return "This file type needs a position assigned to you. Ask your company owner to review your access.";
    if (error.code === "invalid_request") return "The file does not meet the import requirements. Check its size and format.";
    return friendlyLoadError(error.code);
  }
  return "Could not complete the import. Please try again.";
}

function Issues({ issues }: { issues: ImportIssue[] }) {
  if (!issues.length) return null;
  return (
    <div className="fb-inbox-error" role="alert">
      <strong>Fix these issues before importing</strong>
      <ul>
        {issues.map((issue, index) => (
          <li key={`${issue.row}-${issue.field}-${index}`}>
            {issue.row ? `Row ${issue.row}` : "File"} · {issue.field}: {ISSUE_MESSAGES[issue.code] ?? issue.code.replaceAll("_", " ")}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Raw file bytes stay in memory and are sent only to DuitDuit's backend. */
export function BusinessCsvImportCard() {
  const { identity } = useAuth();
  const canConfigure = identity?.role === "owner_director" || identity?.role === "finance_ops";
  const readOnly = identity?.role === "compliance";
  const input = useRef<HTMLInputElement>(null);
  const generation = useRef(0);
  const [schema, setSchema] = useState<ImportSchema>("bank_statement_v1");
  const [csvText, setCsvText] = useState("");
  const [filename, setFilename] = useState("");
  const [mappingId, setMappingId] = useState("");
  const [mappings, setMappings] = useState<ImportMapping[]>([]);
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [preview, setPreview] = useState<CsvImportPreview | null>(null);
  const [issues, setIssues] = useState<ImportIssue[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchImportBatches().then((rows) => active && setBatches(rows))
      .catch((e) => active && setHistoryError(message(e)));
    if (canConfigure) {
      fetchImportMappings().then((rows) => active && setMappings(rows)).catch(() => {});
    }
    return () => { active = false; generation.current += 1; };
  }, [canConfigure]);

  const invalidate = () => {
    generation.current += 1;
    setPreview(null);
    setIssues([]);
    setError(null);
    setNotice(null);
  };

  const selectFile = async (file: File | undefined) => {
    invalidate();
    setCsvText("");
    setFilename(file?.name ?? "");
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Choose a CSV file.");
      return;
    }
    if (file.size > MAX_BYTES) {
      setError("Choose a CSV file of 2 MB or less.");
      return;
    }
    const current = generation.current;
    setBusy(true);
    try {
      const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      if (current !== generation.current) return;
      if (!text.trim()) setError("This file is empty.");
      else setCsvText(text);
    } catch {
      if (current === generation.current) setError("Save this file as UTF-8 CSV and try again.");
    } finally {
      if (current === generation.current) setBusy(false);
    }
  };

  const check = async () => {
    invalidate();
    const current = generation.current;
    setBusy(true);
    try {
      const result = await previewBusinessCsv(schema, csvText, mappingId);
      if (current !== generation.current) return;
      setPreview(result);
      setIssues(result.issues);
      // Refresh mappings after someone saves a layout in the card below.
      if (canConfigure) {
        const saved = await fetchImportMappings().catch(() => mappings);
        if (current === generation.current) setMappings(saved);
      }
    } catch (e) {
      if (current === generation.current) setError(message(e));
    } finally {
      if (current === generation.current) setBusy(false);
    }
  };

  const commit = async () => {
    if (!preview?.can_commit) return;
    const current = generation.current;
    setBusy(true);
    setError(null);
    try {
      const result = await commitBusinessCsv(schema, csvText, mappingId);
      if (current !== generation.current) return;
      setNotice(result.replayed
        ? "This file was already imported. No new records were added."
        : `${result.imported_rows} records imported. ${result.duplicate_rows} existing records skipped.${result.synthetic ? " Synthetic data." : ""}`);
      setCsvText("");
      setFilename("");
      setPreview(null);
      setIssues([]);
      if (input.current) input.current.value = "";
      try {
        const rows = await fetchImportBatches();
        if (current === generation.current) { setBatches(rows); setHistoryError(null); }
      } catch (e) {
        if (current === generation.current) setHistoryError(message(e));
      }
    } catch (e) {
      if (current !== generation.current) return;
      setPreview(null);
      if (e instanceof ImportValidationError) setIssues(e.issues);
      else setError(message(e));
    } finally {
      if (current === generation.current) setBusy(false);
    }
  };

  return (
    <section className="fb-cash-card" aria-busy={busy} style={{ marginBottom: "1.4rem" }}>
      <h2>Business CSV import</h2>
      <p className="fb-inbox-muted">Bring your company's spreadsheets into cash flow, stock and position workspaces. Preview first; no records are added until you confirm.</p>
      {readOnly ? <p>You can review import history. Imports need the owner or the assigned position holder.</p> : (
        <>
          <div className="fb-cash-whatif">
            <label className="fb-cash-field"><span>File type</span>
              <select value={schema} disabled={busy} onChange={(e) => {
                invalidate(); setSchema(e.target.value as ImportSchema); setMappingId("");
              }}>
                {Object.entries(IMPORT_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
              </select>
            </label>
            <label className="fb-cash-field"><span>Column mapping</span>
              <select value={mappingId} disabled={busy} onChange={(e) => { invalidate(); setMappingId(e.target.value); }}>
                <option value="">Match automatically / standard headers</option>
                {mappings.filter((m) => m.schema_name === schema).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
              </select>
            </label>
            <label className="fb-cash-field fb-cs-wide"><span>CSV file · UTF-8 · up to 2 MB and 5,000 rows</span>
              <input ref={input} type="file" accept=".csv,text/csv" disabled={busy} onChange={(e) => void selectFile(e.target.files?.[0])} />
            </label>
          </div>
          <p className="fb-fine">Required fields: {IMPORT_FIELDS[schema].required.join(", ")}. Use a saved mapping if your column names differ.</p>
          {schema === "payroll_v1" && <p className="fb-fine">Import the complete payroll period at once. Employee names and individual salaries are protected; only run totals feed cash flow.</p>}
          {filename && <p className="fb-fine">Selected: {filename}</p>}
          <div className="fb-upload-actions">
            <button type="button" className="fb-btn fb-btn-outline" disabled={!csvText || busy} onClick={() => void check()}>{busy ? "Working…" : "Preview CSV"}</button>
            <button type="button" className="fb-btn fb-btn-solid" disabled={!preview?.can_commit || busy} onClick={() => void commit()}>Confirm import</button>
            <button type="button" className="fb-btn fb-btn-outline" disabled={busy || !filename} onClick={() => {
              invalidate(); setCsvText(""); setFilename(""); if (input.current) input.current.value = "";
            }}>Clear file</button>
          </div>
          {preview && <p role="status">{preview.total_rows} rows checked · {preview.accepted_rows} new · {preview.duplicate_rows} duplicates. {preview.can_commit ? "Ready to import." : "Changes are needed."}</p>}
        </>
      )}
      <Issues issues={issues} />
      {error && <p className="fb-inbox-error" role="alert">{error}</p>}
      {notice && <p className="fb-fin-done" role="status">{notice}</p>}
      <h3>Recent imports</h3>
      {historyError && <p className="fb-inbox-muted">Import history could not be loaded. {historyError}</p>}
      {!historyError && !batches.length && <p className="fb-inbox-muted">No imports recorded for your accessible positions yet.</p>}
      <ul className="fb-fin-items">
        {batches.map((batch) => <li key={batch.id}><span>
          <strong>{IMPORT_LABELS[batch.schema_name]}</strong> · {batch.imported_rows} imported · {batch.duplicate_rows} duplicates
          <br /><span className="fb-inbox-muted">{new Date(batch.created_at).toLocaleString()}{batch.synthetic ? " · Synthetic" : ""}</span>
        </span></li>)}
      </ul>
    </section>
  );
}
