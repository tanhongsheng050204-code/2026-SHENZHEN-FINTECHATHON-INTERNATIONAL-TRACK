import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { friendlyLoadError } from "../api/client";
import {
  IMPORT_FIELDS,
  createImportMapping,
  errorCode,
  fetchImportMappings,
  matchImportMapping,
  type ImportMapping,
  type ImportSchema,
} from "../api/topicE";

function message(error: unknown): string {
  const code = errorCode(error);
  if (code === "no_matching_mapping") return "No saved mapping matches these columns yet.";
  if (code.startsWith("column_not_in_headers:")) return `"${code.split(":")[1]}" is not one of the file's columns.`;
  if (code.startsWith("missing_required_field:")) return `Map a column to the required field "${code.split(":")[1]}".`;
  if (code.startsWith("duplicate_target_field:")) return `Two columns are mapped to "${code.split(":")[1]}".`;
  if (code.startsWith("unknown_target_field:")) return `"${code.split(":")[1]}" is not a field of this file type.`;
  return friendlyLoadError(code);
}

function Field({ label, children, wide }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <label className={"fb-cash-field" + (wide ? " fb-cs-wide" : "")}>
      <span>{label}</span>
      {children}
    </label>
  );
}


function splitHeaders(text: string): string[] {
  return text.split(/[,\t]/).map((h) => h.trim()).filter(Boolean);
}

/** Teach FinBrain a bank or spreadsheet layout once; matching files then import automatically. */
export function ImportMappingsCard() {
  const [mappings, setMappings] = useState<ImportMapping[]>([]);
  const [schema, setSchema] = useState<ImportSchema>("payables_register_v1");
  const [name, setName] = useState("Supplier sheet");
  const [headerText, setHeaderText] = useState("Bill, Vendor, Total, Ccy, Due, Notes");
  const [map, setMap] = useState<Record<string, string>>({});
  const [matchText, setMatchText] = useState("Baki, TARIKH, Kredit, Tarikh Nilai, Debit, Keterangan");
  const [matchResult, setMatchResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const headers = splitHeaders(headerText);

  useEffect(() => {
    let active = true;
    fetchImportMappings().then((m) => active && setMappings(m)).catch((e) => active && setError(message(e)));
    return () => { active = false; };
  }, []);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    const columnMap = Object.fromEntries(Object.entries(map).filter(([h, f]) => f && headers.includes(h)));
    try {
      const created = await createImportMapping(schema, name, headers, columnMap);
      setMappings((list) => [...list, created]);
    } catch (e) {
      setError(message(e));
    }
  };

  const match = async () => {
    setError(null);
    setMatchResult(null);
    try {
      const found = await matchImportMapping("bank_statement_v1", splitHeaders(matchText));
      setMatchResult(`Matches "${found.name}". Columns can be in any order or case.`);
    } catch (e) {
      setMatchResult(message(e));
    }
  };

  return (
    <section className="fb-cash-card">
      <h2>Import column mappings</h2>
      <p className="fb-inbox-muted">Teach FinBrain your bank and spreadsheet columns once; the next file with the same columns imports automatically.</p>
      <ul className="fb-fin-items">
        {mappings.map((m) => (
          <li key={m.id}>
            <span><strong>{m.name}</strong> · {m.schema_name === "bank_statement_v1" ? "Bank statement" : "Payables register"}<br />
              <span className="fb-inbox-muted">{Object.entries(m.column_map).map(([h, f]) => `${h} → ${f}`).join(" · ")}</span></span>
          </li>
        ))}
      </ul>
      <div className="fb-cs-subform">
        <div className="fb-inbox-label">Does a file match a saved mapping?</div>
        <div className="fb-cash-whatif">
          <Field label="Bank statement column headers, comma-separated" wide><input value={matchText} onChange={(e) => setMatchText(e.target.value)} /></Field>
          <button className="fb-btn fb-btn-outline" type="button" onClick={() => void match()}>Check</button>
        </div>
        {matchResult && <p className="fb-fin-done" role="status">{matchResult}</p>}
      </div>
      <form className="fb-cs-subform" onSubmit={(e) => void save(e)}>
        <div className="fb-inbox-label">New mapping</div>
        <div className="fb-cash-whatif">
          <Field label="Name"><input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="File type">
            <select value={schema} onChange={(e) => { setSchema(e.target.value as ImportSchema); setMap({}); }}>
              <option value="payables_register_v1">Payables register</option><option value="bank_statement_v1">Bank statement</option>
            </select>
          </Field>
          <Field label="Every column header in the file" wide><input value={headerText} onChange={(e) => setHeaderText(e.target.value)} /></Field>
        </div>
        <ul className="fb-cs-positions">
          {headers.map((h) => (
            <li key={h}>
              <span>{h}</span>
              <select aria-label={`Field for column ${h}`} value={map[h] ?? ""} onChange={(e) => setMap({ ...map, [h]: e.target.value })}>
                <option value="">Not imported</option>
                {IMPORT_FIELDS[schema].all.map((f) => <option key={f} value={f}>{f}{IMPORT_FIELDS[schema].required.includes(f) ? " (required)" : ""}</option>)}
              </select>
            </li>
          ))}
        </ul>
        <button className="fb-btn fb-btn-solid fb-team-submit" type="submit">Save mapping</button>
      </form>
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
    </section>
  );
}

