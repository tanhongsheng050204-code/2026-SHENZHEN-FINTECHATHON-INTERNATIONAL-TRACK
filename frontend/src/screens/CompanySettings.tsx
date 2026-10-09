import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { useAuth } from "../auth/AuthProvider";
import { useI18n } from "../lib/i18n";
import { JOB_LABELS } from "../lib/jobFunctions";
import { PERSONAS } from "../lib/personas";
import { friendlyLoadError, type Role } from "../api/client";
import {
  TEMPLATE_PLACEHOLDERS,
  applyIndustryTemplate,
  approveMessageTemplate,
  createAlertRule,
  createMessageTemplate,
  decideSettingsChange,
  errorCode,
  fetchAlertRules,
  fetchIndustryTemplates,
  fetchMessageTemplates,
  fetchSettings,
  fetchSettingsChanges,
  previewIndustryTemplate,
  proposeSettingsChange,
  rollbackSettings,
  ringgit,
  type AlertMetric,
  type AlertRule,
  type IndustryTemplate,
  type IndustryTemplateId,
  type JobFunction,
  type MessageTemplate,
  type SettingsArea,
  type SettingsChange,
  type SettingsResponse,
  type TemplatePreview,
  type TenantSettings,
} from "../api/topicE";

// Refusals and safety floors, in words an owner can act on.
const MESSAGES: Record<string, string> = {
  no_changes: "Nothing changed: these values are already in place.",
  owner_must_receive_critical_alerts: "The owner always receives critical cash alerts.",
  mfa_required_for_privileged_roles: "Owner, finance and compliance accounts must keep two-step sign-in.",
  owner_position_required: "The owner position can't be switched off.",
  every_position_listed_once: "Every position must be listed once.",
  change_not_pending: "This change has already been decided.",
  change_not_found: "This change no longer exists.",
  invalid_rollback_version: "Choose an earlier version to roll back to.",
  invalid_placeholder: "Use braces only for the placeholders listed below.",
  personal_data_in_template: "Templates can't contain emails, phone, card or account numbers.",
  no_matching_mapping: "No saved mapping matches these columns yet.",
};

function message(error: unknown): string {
  const code = errorCode(error);
  if (MESSAGES[code]) return MESSAGES[code];
  if (code.startsWith("unknown_placeholder:")) return `Unknown placeholder {${code.split(":")[1]}}.`;
  if (code.startsWith("column_not_in_headers:")) return `"${code.split(":")[1]}" is not one of the file's columns.`;
  if (code.startsWith("missing_required_field:")) return `Map a column to the required field "${code.split(":")[1]}".`;
  if (code.startsWith("duplicate_target_field:")) return `Two columns are mapped to "${code.split(":")[1]}".`;
  return friendlyLoadError(code);
}

const AREAS: { id: SettingsArea; label: string }[] = [
  { id: "profile", label: "Profile" },
  { id: "positions", label: "Positions" },
  { id: "approvals", label: "Approvals" },
  { id: "alerts", label: "Alerts" },
  { id: "financing", label: "Financing" },
  { id: "security", label: "Security" },
  { id: "branding", label: "Branding" },
];
const WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const LANGS: ("en" | "ms" | "zh")[] = ["en", "ms", "zh"];
const PRIVILEGED: Role[] = ["owner_director", "finance_ops", "compliance"];
const ALL_ROLES: Role[] = ["owner_director", "finance_ops", "compliance", "general_employee"];
const JOBS = (Object.keys(JOB_LABELS) as JobFunction[]).filter((j) => j !== "production");

function toggle<T>(list: T[], item: T): T[] {
  return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
}

function Field({ label, children, wide }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <label className={"fb-cash-field" + (wide ? " fb-cs-wide" : "")}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function Checks<T extends string>({ legend, options, value, onChange, locked = [], label }: {
  legend: string; options: T[]; value: T[]; onChange: (v: T[]) => void; locked?: T[]; label: (o: T) => string;
}) {
  return (
    <fieldset className="fb-team-jobs">
      <legend>{legend}</legend>
      {options.map((o) => (
        <label key={o}>
          <input type="checkbox" checked={value.includes(o)} disabled={locked.includes(o)} onChange={() => onChange(toggle(value, o))} />
          {label(o)}{locked.includes(o) && " (required)"}
        </label>
      ))}
    </fieldset>
  );
}

// ── Settings areas ──────────────────────────────────────────────────────────

function AreaForm({ area, draft, setDraft, readOnly }: {
  area: SettingsArea; draft: TenantSettings; setDraft: (s: TenantSettings) => void; readOnly: boolean;
}) {
  const set = <K extends keyof TenantSettings>(key: K, value: TenantSettings[K]) => setDraft({ ...draft, [key]: value });
  const p = draft.profile, a = draft.approvals, al = draft.alerts, f = draft.financing, s = draft.security, b = draft.branding;

  const body = (() => {
    switch (area) {
      case "profile":
        return (
          <>
            <div className="fb-cash-whatif">
              <Field label="Company name"><input value={p.company_name} maxLength={120} onChange={(e) => set("profile", { ...p, company_name: e.target.value })} /></Field>
              <Field label="State"><input value={p.state} maxLength={40} onChange={(e) => set("profile", { ...p, state: e.target.value })} /></Field>
              <Field label="Size">
                <select value={p.size} onChange={(e) => set("profile", { ...p, size: e.target.value as typeof p.size })}>
                  <option value="micro">Micro</option><option value="small">Small</option><option value="medium">Medium</option>
                </select>
              </Field>
              <Field label="Financial year starts">
                <select value={p.fiscal_year_start_month} onChange={(e) => set("profile", { ...p, fiscal_year_start_month: Number(e.target.value) })}>
                  {Array.from({ length: 12 }, (_, i) => <option key={i + 1} value={i + 1}>{new Date(2026, i, 1).toLocaleString("en-MY", { month: "long" })}</option>)}
                </select>
              </Field>
              <Field label="Registered on (sets months trading)"><input type="date" value={p.registered_on ?? ""} max={new Date().toISOString().slice(0, 10)} onChange={(e) => set("profile", { ...p, registered_on: e.target.value || null })} /></Field>
            </div>
            <Checks legend="Working days" options={WEEK} value={p.working_days} onChange={(v) => set("profile", { ...p, working_days: v })} label={(d) => d[0].toUpperCase() + d.slice(1)} />
            <Checks legend="Languages" options={LANGS} value={p.languages} onChange={(v) => set("profile", { ...p, languages: v })} label={(l) => ({ en: "English", ms: "Malay", zh: "Chinese" })[l]} />
          </>
        );
      case "positions":
        return (
          <ul className="fb-cs-positions">
            {draft.positions.map((pos, i) => (
              <li key={pos.job_function}>
                <label className="fb-fin-check">
                  <input type="checkbox" checked={pos.enabled} disabled={pos.job_function === "owner"} onChange={() => {
                    const next = [...draft.positions];
                    next[i] = { ...pos, enabled: !pos.enabled };
                    set("positions", next);
                  }} />
                  {JOB_LABELS[pos.job_function]}{pos.job_function === "owner" && " (required)"}
                </label>
                <input aria-label={`Name shown for ${JOB_LABELS[pos.job_function]}`} value={pos.display_name} maxLength={60} onChange={(e) => {
                  const next = [...draft.positions];
                  next[i] = { ...pos, display_name: e.target.value };
                  set("positions", next);
                }} />
              </li>
            ))}
          </ul>
        );
      case "approvals":
        return (
          <div className="fb-cash-whatif">
            <Field label="Owner approves amounts above (RM)"><input inputMode="decimal" value={a.owner_escalation_amount} onChange={(e) => set("approvals", { ...a, owner_escalation_amount: e.target.value })} /></Field>
            <Field label="…or messages to more than (customers)"><input type="number" min={1} value={a.owner_escalation_customer_count} onChange={(e) => set("approvals", { ...a, owner_escalation_customer_count: Number(e.target.value) })} /></Field>
            <Field label="Quiet hours start"><input type="time" value={a.quiet_hours_start.slice(0, 5)} onChange={(e) => set("approvals", { ...a, quiet_hours_start: e.target.value })} /></Field>
            <Field label="Quiet hours end"><input type="time" value={a.quiet_hours_end.slice(0, 5)} onChange={(e) => set("approvals", { ...a, quiet_hours_end: e.target.value })} /></Field>
            <Field label="Agent needs this many reviews before promotion"><input type="number" min={5} value={a.promotion_min_sample} onChange={(e) => set("approvals", { ...a, promotion_min_sample: Number(e.target.value) })} /></Field>
            <Field label="…approved unchanged at least (%)"><input type="number" min={50} max={100} value={Math.round(a.promotion_min_unedited_rate * 100)} onChange={(e) => set("approvals", { ...a, promotion_min_unedited_rate: Number(e.target.value) / 100 })} /></Field>
          </div>
        );
      case "alerts":
        return (
          <>
            <div className="fb-cash-whatif">
              <Field label="Minimum cash balance (RM)"><input inputMode="decimal" value={al.minimum_cash_balance} onChange={(e) => set("alerts", { ...al, minimum_cash_balance: e.target.value })} /></Field>
              <Field label="Warn this many days ahead (7–90)"><input type="number" min={7} max={90} value={al.alert_horizon_days} onChange={(e) => set("alerts", { ...al, alert_horizon_days: Number(e.target.value) })} /></Field>
            </div>
            <Checks legend="Who is warned" options={JOBS} value={al.recipients} onChange={(v) => set("alerts", { ...al, recipients: v })} locked={["owner"]} label={(j) => JOB_LABELS[j]} />
            <Checks legend="Channels" options={["in_app", "email", "telegram"] as ("in_app" | "email" | "telegram")[]} value={al.channels} onChange={(v) => set("alerts", { ...al, channels: v })} label={(c) => ({ in_app: "In the app", email: "Email", telegram: "Telegram" })[c]} />
            <p className="fb-inbox-muted">Critical cash alerts can't be switched off.</p>
          </>
        );
      case "financing":
        return (
          <>
            <label className="fb-fin-check"><input type="checkbox" checked={f.islamic_only} onChange={() => set("financing", { ...f, islamic_only: !f.islamic_only })} />Show Islamic (Shariah-compliant) financing only</label>
            <Checks legend="Look for financing in" options={["MY", "CN"] as ("MY" | "CN")[]} value={f.jurisdictions} onChange={(v) => set("financing", { ...f, jurisdictions: v })} label={(j) => (j === "MY" ? "Malaysia" : "China")} />
          </>
        );
      case "security":
        return (
          <>
            <div className="fb-cash-whatif">
              <Field label="Sign out after idle minutes (5–60)"><input type="number" min={5} max={60} value={s.session_idle_minutes} onChange={(e) => set("security", { ...s, session_idle_minutes: Number(e.target.value) })} /></Field>
            </div>
            <Checks legend="Roles that must use two-step sign-in" options={ALL_ROLES} value={s.mfa_required_roles} onChange={(v) => set("security", { ...s, mfa_required_roles: v })} locked={PRIVILEGED} label={(r) => PERSONAS[r].label} />
            <p className="fb-inbox-muted">Security changes wait for Compliance before they apply.</p>
          </>
        );
      case "branding":
        return (
          <div className="fb-cash-whatif">
            <Field label="Name on documents"><input value={b.display_name} maxLength={120} onChange={(e) => set("branding", { ...b, display_name: e.target.value })} /></Field>
            <Field label="Document footer" wide><input value={b.document_footer ?? ""} maxLength={200} onChange={(e) => set("branding", { ...b, document_footer: e.target.value || null })} /></Field>
          </div>
        );
    }
  })();

  return <fieldset className="fb-cs-area" disabled={readOnly}>{body}</fieldset>;
}

function ChangeResult({ change }: { change: SettingsChange }) {
  return (
    <div className={"fb-fin-verify " + (change.status === "applied" ? "is-verified" : "")} role="status">
      <strong>{change.status === "applied" ? `Applied as version ${change.version}.` : change.status === "pending_approval" ? "Waiting for Compliance." : "Rejected."}</strong>
      <ul className="fb-cs-preview">{change.preview.map((line) => <li key={line}><code>{line}</code></li>)}</ul>
    </div>
  );
}

function SettingsTab({ data, setData, isOwner }: { data: SettingsResponse; setData: (d: SettingsResponse) => void; isOwner: boolean }) {
  const [area, setArea] = useState<SettingsArea>("alerts");
  const [draft, setDraft] = useState<TenantSettings>(data.settings);
  const [result, setResult] = useState<SettingsChange | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const choose = (next: SettingsArea) => {
    setArea(next);
    setDraft(data.settings);
    setResult(null);
    setError(null);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await proposeSettingsChange(area, draft[area]);
      setResult(res.change);
      if (res.change.status === "applied") {
        setData({ ...data, version: res.change.version, settings: res.settings });
        setDraft(res.settings);
      }
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="fb-cash-card" onSubmit={(e) => void submit(e)}>
      <div className="fb-inbox-tabs" role="tablist" aria-label="Settings area">
        {AREAS.map((a) => (
          <button key={a.id} type="button" role="tab" aria-selected={area === a.id} className={area === a.id ? "is-current" : undefined} onClick={() => choose(a.id)}>{a.label}</button>
        ))}
      </div>
      <AreaForm area={area} draft={draft} setDraft={setDraft} readOnly={!isOwner} />
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
      {result && <ChangeResult change={result} />}
      {isOwner ? (
        <div className="fb-inbox-actions">
          <button className="fb-btn fb-btn-solid" type="submit" disabled={busy}>{busy ? "Saving…" : area === "security" ? "Send to Compliance" : "Save changes"}</button>
          <button className="fb-btn fb-btn-outline" type="button" onClick={() => choose(area)}>Discard</button>
        </div>
      ) : (
        <p className="fb-inbox-muted">Only the owner can change company settings.</p>
      )}
    </form>
  );
}

// ── Change history ──────────────────────────────────────────────────────────

function HistoryTab({ role, currentVersion, onApplied }: { role: string; currentVersion: number; onApplied: (s: TenantSettings, v: number) => void }) {
  const [changes, setChanges] = useState<SettingsChange[]>([]);
  const [note, setNote] = useState<ReactNode>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchSettingsChanges().then((c) => active && setChanges(c)).catch((e) => active && setError(message(e)));
    return () => { active = false; };
  }, []);

  const decide = async (change: SettingsChange, decision: "approve" | "reject") => {
    setError(null);
    try {
      const res = await decideSettingsChange(change.id, decision);
      setChanges((list) => list.map((c) => (c.id === change.id ? res.change : c)));
      if (res.change.status === "applied") onApplied(res.settings, res.change.version);
    } catch (e) {
      setError(message(e));
    }
  };

  const rollback = async (version: number) => {
    setError(null);
    try {
      const res = await rollbackSettings(version);
      setChanges((list) => [...list, res.change]);
      setNote(<ChangeResult change={res.change} />);
      if (res.change.status === "applied") onApplied(res.settings, res.change.version);
    } catch (e) {
      setError(message(e));
    }
  };

  const versions = [...new Set(changes.filter((c) => c.status === "applied").map((c) => c.version))].filter((v) => v < currentVersion);

  return (
    <section className="fb-cash-card">
      <h2>Change history</h2>
      <p className="fb-inbox-muted">Every change becomes a new version. Security changes, and rollbacks that touch security, wait for Compliance.</p>
      <ol className="fb-trust-events">
        {[...changes].reverse().map((c) => (
          <li key={c.id}>
            <div className="fb-trust-event-head">
              <span className="fb-trust-code">v{c.version}</span>
              <strong style={{ textTransform: "capitalize" }}>{c.area}</strong>
              <span className={"fb-inbox-pill " + (c.status === "applied" ? "is-approved" : c.status === "pending_approval" ? "is-can" : "is-rejected")}>
                {c.status === "pending_approval" ? "Waiting for Compliance" : c.status}
              </span>
            </div>
            {c.preview.map((line) => <code key={line} className="fb-cs-line">{line}</code>)}
            {c.status === "pending_approval" && role === "compliance" && (
              <div className="fb-inbox-actions">
                <button className="fb-btn fb-btn-solid" type="button" onClick={() => void decide(c, "approve")}>Approve</button>
                <button className="fb-btn fb-btn-outline fb-fin-revoke" type="button" onClick={() => void decide(c, "reject")}>Reject</button>
              </div>
            )}
          </li>
        ))}
      </ol>
      {role === "owner_director" && versions.length > 0 && (
        <div className="fb-inbox-actions">
          {versions.map((v) => <button key={v} className="fb-btn fb-btn-outline" type="button" onClick={() => void rollback(v)}>Roll back to v{v}</button>)}
        </div>
      )}
      {note}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
    </section>
  );
}

// ── Industry templates ──────────────────────────────────────────────────────

function IndustryTab({ isOwner, onApplied }: { isOwner: boolean; onApplied: (s: TenantSettings, v: number) => void }) {
  const [current, setCurrent] = useState<IndustryTemplateId | null>(null);
  const [templates, setTemplates] = useState<IndustryTemplate[]>([]);
  const [preview, setPreview] = useState<TemplatePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<SettingsChange | null>(null);

  useEffect(() => {
    let active = true;
    fetchIndustryTemplates()
      .then((d) => { if (active) { setCurrent(d.current); setTemplates(d.templates); } })
      .catch((e) => active && setError(message(e)));
    return () => { active = false; };
  }, []);

  const showPreview = async (id: IndustryTemplateId) => {
    setError(null);
    setDone(null);
    try {
      setPreview(await previewIndustryTemplate(id));
    } catch (e) {
      setError(message(e));
    }
  };

  const apply = async (id: IndustryTemplateId) => {
    setError(null);
    try {
      const res = await applyIndustryTemplate(id);
      setDone(res.change);
      setCurrent(id);
      setPreview(null);
      onApplied(res.settings, res.change.version);
    } catch (e) {
      setError(message(e));
    }
  };

  return (
    <section className="fb-cash-card">
      <h2>Industry template</h2>
      <p className="fb-inbox-muted">A template switches positions and agents on or off for your kind of business. Your data is kept.</p>
      <div className="fb-fin-matches">
        {templates.map((t) => (
          <article key={t.id} className={"fb-fin-match" + (t.id === current ? " is-best" : "")}>
            <div className="fb-fin-match-head">
              {t.id === current && <span className="fb-inbox-pill is-can">Current</span>}
              <span className="fb-inbox-pill is-muted">{t.demo_data === "full" ? "Full demo data" : "Settings only"}</span>
            </div>
            <h3>{t.name}</h3>
            <p className="fb-inbox-muted">{t.description}</p>
            {isOwner && t.id !== current && (
              <button className="fb-btn fb-btn-outline" type="button" onClick={() => void showPreview(t.id)}>Preview the switch</button>
            )}
          </article>
        ))}
      </div>
      {preview && (
        <div className="fb-fin-done">
          <strong>Switching to {templates.find((t) => t.id === preview.template_id)?.name}:</strong>{" "}
          {preview.positions_added.length > 0 && <>turns on {preview.positions_added.map((j) => JOB_LABELS[j]).join(", ")}. </>}
          {preview.positions_removed.length > 0 && <>Turns off {preview.positions_removed.map((j) => JOB_LABELS[j]).join(", ")}. </>}
          {preview.designed_positions.length > 0 && <>{preview.designed_positions.map((j) => JOB_LABELS[j]).join(", ")} is designed, not built. </>}
          {preview.data_kept && "All your data is kept."}
          <div className="fb-inbox-actions" style={{ marginTop: ".6rem" }}>
            <button className="fb-btn fb-btn-solid" type="button" onClick={() => void apply(preview.template_id)}>Apply template</button>
            <button className="fb-btn fb-btn-outline" type="button" onClick={() => setPreview(null)}>Cancel</button>
          </div>
        </div>
      )}
      {done && <ChangeResult change={done} />}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
    </section>
  );
}

// ── Message templates ───────────────────────────────────────────────────────

function MessagesTab({ role }: { role: string }) {
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [kind, setKind] = useState<MessageTemplate["kind"]>("payment_reminder");
  const [language, setLanguage] = useState<MessageTemplate["language"]>("en");
  const [tone, setTone] = useState<MessageTemplate["tone"]>("friendly");
  const [body, setBody] = useState("Hi {customer_name}, a quick reminder that invoice {invoice_no} for {amount} was due on {due_date}.");
  const [error, setError] = useState<string | null>(null);
  const canDraft = role === "owner_director" || role === "finance_ops";

  useEffect(() => {
    let active = true;
    fetchMessageTemplates().then((t) => active && setTemplates(t)).catch((e) => active && setError(message(e)));
    return () => { active = false; };
  }, []);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      const created = await createMessageTemplate({ kind, language, tone, body });
      setTemplates((list) => [...list, created]);
    } catch (e) {
      setError(message(e));
    }
  };

  const approve = async (id: string) => {
    setError(null);
    try {
      const approved = await approveMessageTemplate(id);
      setTemplates((list) => list.map((t) => (t.id === id ? approved : t)));
    } catch (e) {
      setError(message(e));
    }
  };

  return (
    <section className="fb-cash-card">
      <h2>Message templates</h2>
      <p className="fb-inbox-muted">Agents draft messages from approved templates. Finance drafts them; the owner approves.</p>
      <ul className="fb-fin-items">
        {templates.map((t) => (
          <li key={t.id}>
            <span>
              <strong>{t.kind.replace(/_/g, " ")}</strong> · {({ en: "English", ms: "Malay", zh: "Chinese" })[t.language]} · {t.tone}
              <br />
              <span className="fb-inbox-muted">{t.body}</span>
            </span>
            {t.status === "approved" ? (
              <span className="fb-inbox-pill is-approved">Approved</span>
            ) : role === "owner_director" ? (
              <button className="fb-btn fb-btn-outline" type="button" onClick={() => void approve(t.id)}>Approve</button>
            ) : (
              <span className="fb-inbox-pill is-muted">Draft</span>
            )}
          </li>
        ))}
      </ul>
      {canDraft && (
        <form className="fb-cs-subform" onSubmit={(e) => void create(e)}>
          <div className="fb-cash-whatif">
            <Field label="Kind">
              <select value={kind} onChange={(e) => setKind(e.target.value as MessageTemplate["kind"])}>
                <option value="payment_reminder">Payment reminder</option><option value="customer_reply">Customer reply</option><option value="supplier_query">Supplier query</option>
              </select>
            </Field>
            <Field label="Language">
              <select value={language} onChange={(e) => setLanguage(e.target.value as MessageTemplate["language"])}>
                <option value="en">English</option><option value="ms">Malay</option><option value="zh">Chinese</option>
              </select>
            </Field>
            <Field label="Tone">
              <select value={tone} onChange={(e) => setTone(e.target.value as MessageTemplate["tone"])}>
                <option value="friendly">Friendly</option><option value="formal">Formal</option>
              </select>
            </Field>
          </div>
          <label className="fb-inbox-edit">
            <span className="fb-inbox-label">Message</span>
            <textarea rows={4} value={body} minLength={10} maxLength={2000} onChange={(e) => setBody(e.target.value)} />
          </label>
          <div className="fb-inbox-chips" aria-label="Insert a placeholder">
            {TEMPLATE_PLACEHOLDERS.map((ph) => (
              <button key={ph} type="button" className="fb-inbox-chip fb-cs-chip" onClick={() => setBody((b) => `${b}{${ph}}`)}>{`{${ph}}`}</button>
            ))}
          </div>
          <button className="fb-btn fb-btn-solid fb-team-submit" type="submit">Save as draft</button>
        </form>
      )}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
    </section>
  );
}

// ── Alert rules ─────────────────────────────────────────────────────────────

const METRICS: Record<AlertMetric, string> = {
  projected_balance: "Projected balance (RM)",
  overdue_amount_per_customer: "Overdue amount per customer (RM)",
  stock_below_reorder: "SKUs below reorder level",
  payroll_coverage_days: "Days of payroll covered",
  marketing_return_per_ringgit: "Marketing return per RM1",
  open_disputes: "Open disputes",
};

function RulesTab({ isOwner }: { isOwner: boolean }) {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [metric, setMetric] = useState<AlertMetric>("open_disputes");
  const [operator, setOperator] = useState<"above" | "below">("above");
  const [threshold, setThreshold] = useState("2");
  const [recipients, setRecipients] = useState<JobFunction[]>(["customer_service"]);
  const [channel, setChannel] = useState<AlertRule["channel"]>("in_app");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchAlertRules().then((r) => active && setRules(r)).catch((e) => active && setError(message(e)));
    return () => { active = false; };
  }, []);

  const create = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      const rule = await createAlertRule({ metric, operator, threshold, recipients, channel });
      setRules((list) => [...list, rule]);
    } catch (e) {
      setError(message(e));
    }
  };

  const describe = (r: AlertRule) => {
    const money = r.metric === "projected_balance" || r.metric === "overdue_amount_per_customer";
    return `${METRICS[r.metric].replace(/ \(RM\)$/, "")} ${r.operator} ${money ? ringgit(r.threshold) : Number(r.threshold)}`;
  };

  return (
    <section className="fb-cash-card">
      <h2>Alert rules</h2>
      <p className="fb-inbox-muted">Extra alerts on fixed measures, sent to the positions you choose.</p>
      <ul className="fb-fin-items">
        {rules.map((r) => (
          <li key={r.id}>
            <span><strong>{describe(r)}</strong><br /><span className="fb-inbox-muted">To {r.recipients.map((j) => JOB_LABELS[j]).join(", ")} · {r.channel.replace("_", " ")}</span></span>
            <span className={"fb-inbox-pill " + (r.enabled ? "is-approved" : "is-muted")}>{r.enabled ? "On" : "Off"}</span>
          </li>
        ))}
      </ul>
      {isOwner && (
        <form className="fb-cs-subform" onSubmit={(e) => void create(e)}>
          <div className="fb-cash-whatif">
            <Field label="Measure"><select value={metric} onChange={(e) => setMetric(e.target.value as AlertMetric)}>{(Object.keys(METRICS) as AlertMetric[]).map((m) => <option key={m} value={m}>{METRICS[m]}</option>)}</select></Field>
            <Field label="When it goes"><select value={operator} onChange={(e) => setOperator(e.target.value as "above" | "below")}><option value="above">Above</option><option value="below">Below</option></select></Field>
            <Field label="Threshold"><input inputMode="decimal" value={threshold} onChange={(e) => setThreshold(e.target.value.replace(/[^0-9.]/g, ""))} /></Field>
            <Field label="Channel"><select value={channel} onChange={(e) => setChannel(e.target.value as AlertRule["channel"])}><option value="in_app">In the app</option><option value="email">Email</option><option value="telegram">Telegram</option></select></Field>
          </div>
          <Checks legend="Send to" options={JOBS} value={recipients} onChange={setRecipients} label={(j) => JOB_LABELS[j]} />
          <button className="fb-btn fb-btn-solid fb-team-submit" type="submit" disabled={recipients.length === 0 || !threshold}>Add rule</button>
        </form>
      )}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
    </section>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

type Tab = "settings" | "history" | "industry" | "messages" | "rules";

export default function CompanySettings() {
  const { t } = useI18n();
  const { identity } = useAuth();
  const role = identity?.role ?? "";
  const isOwner = role === "owner_director";
  const [data, setData] = useState<SettingsResponse | null>(null);
  const [tab, setTab] = useState<Tab>("settings");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchSettings().then((d) => active && setData(d)).catch((e) => active && setError(message(e)));
    return () => { active = false; };
  }, []);

  const applied = (settings: TenantSettings, version: number) => setData((d) => (d ? { ...d, settings, version } : d));
  const tabs: { id: Tab; label: string; show: boolean }[] = [
    { id: "settings", label: "Settings", show: true },
    { id: "history", label: "Change history", show: true },
    { id: "industry", label: "Industry template", show: true },
    { id: "messages", label: "Message templates", show: true },
    { id: "rules", label: "Alert rules", show: true },
  ];

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="company" />
      <AppTopBar current="company" />
      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.company")}</div>
        <h1>{t("nav.company")}</h1>
        <p>{t("company.desc")}</p>
      </header>
      <div className="fb-page-body">
        <div className="fb-cash">
          {error && <div className="fb-callout" role="alert">{error}</div>}
          {data?.data_mode === "stub" && <div className="fb-callout">{t("cash.stub")} Changes are shown but not saved yet.</div>}
          {data && (
            <>
              <div className="fb-cash-kpis">
                <div className="fb-cash-kpi is-good">
                  <span className="fb-cash-kpi-label">Settings version</span>
                  <span className="fb-cash-kpi-value">v{data.version}</span>
                  <span className="fb-cash-kpi-sub">{data.settings.profile.company_name}</span>
                </div>
                <div className="fb-cash-kpi is-attn">
                  <span className="fb-cash-kpi-label">Minimum cash balance</span>
                  <span className="fb-cash-kpi-value">{ringgit(data.settings.alerts.minimum_cash_balance)}</span>
                  <span className="fb-cash-kpi-sub">Warned {data.settings.alerts.alert_horizon_days} days ahead</span>
                </div>
                <div className="fb-cash-kpi is-good">
                  <span className="fb-cash-kpi-label">Positions switched on</span>
                  <span className="fb-cash-kpi-value">{data.settings.positions.filter((p) => p.enabled).length}</span>
                  <span className="fb-cash-kpi-sub">Template: {data.template}</span>
                </div>
              </div>
              <div className="fb-inbox-tabs" role="tablist" aria-label="Company settings">
                {tabs.filter((x) => x.show).map((x) => (
                  <button key={x.id} type="button" role="tab" aria-selected={tab === x.id} className={tab === x.id ? "is-current" : undefined} onClick={() => setTab(x.id)}>{x.label}</button>
                ))}
              </div>
              {tab === "settings" && <SettingsTab data={data} setData={setData} isOwner={isOwner} />}
              {tab === "history" && <HistoryTab role={role} currentVersion={data.version} onApplied={applied} />}
              {tab === "industry" && <IndustryTab isOwner={isOwner} onApplied={applied} />}
              {tab === "messages" && <MessagesTab role={role} />}
              {tab === "rules" && <RulesTab isOwner={isOwner} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
