import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { SectionTabs } from "../components/SectionTabs";
import { RecordPanel, Who } from "../components/RecordPanel";
import { useAuth } from "../auth/AuthProvider";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import { ApiError, friendlyLoadError } from "../api/client";
import { fetchTeam, type TeamMember } from "../api/topicE";
import {
  completeIncidentStep,
  draftIncidentNotice,
  fetchIncidents,
  fetchOfficer,
  fetchSecurityActivity,
  nameOfficer,
  openIncident,
  type DataKind,
  type Incident,
  type IncidentKind,
  type IncidentStep,
  type Officer,
  type SecurityEvent,
  type Severity,
} from "../api/security";
import "../components/records.css";
import "./SecurityActivity.css";

const SEVERITY: Record<Severity, [string, string]> = {
  critical: ["is-red", "Critical"],
  warning: ["is-amber", "Warning"],
  info: ["", "Info"],
};
const KINDS: Record<IncidentKind, string> = {
  unauthorized_access: "Unauthorised access",
  lost_or_stolen_device: "Lost or stolen device",
  data_sent_to_wrong_person: "Data sent to the wrong person",
  system_compromise: "System compromise",
  vendor_breach: "Breach at a service provider",
  other: "Other personal data breach",
};
const DATA: Record<DataKind, string> = {
  contact_details: "Contact details",
  identity_numbers: "Identity numbers",
  financial_records: "Financial records",
  employee_records: "Employee records",
  credentials: "Sign-in credentials",
};
const STEPS: Record<IncidentStep, [string, string]> = {
  contained: ["Contained", "Stop the leak: revoke access, recall the message, lock the device."],
  assessed: ["Assessed", "What data, how many people, and is significant harm likely?"],
  commissioner_notified: ["Commissioner notified", "Notify the Personal Data Protection Commissioner as the guideline requires."],
  individuals_notified: ["People affected notified", "Required when significant harm is likely."],
  closed: ["Closed", "Every required step is done."],
};
const ROLE_LABEL: Record<string, string> = {
  owner_director: "Owner", finance_ops: "Finance", compliance: "Compliance", general_employee: "Staff",
  automation: "Automation", api_key: "AI key", member: "Member", system: "System",
};

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-MY", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function day(iso: string): string {
  return new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-MY", { day: "numeric", month: "short", year: "numeric" });
}

function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function errorText(error: unknown, tx: (s: string) => string): string {
  const code = error instanceof ApiError ? error.code : "";
  if (code === "required_steps_open") return tx("Complete the required steps before closing the incident.");
  return friendlyLoadError(code);
}

/** Record a breach: kinds and numbers only, so no personal data enters the record. */
function NewIncidentPanel({ onClose, onOpened }: { onClose: () => void; onOpened: (incident: Incident) => void }) {
  const { tx } = useI18n();
  const [kind, setKind] = useState<IncidentKind>("data_sent_to_wrong_person");
  const [data, setData] = useState<DataKind[]>(["contact_details"]);
  const [people, setPeople] = useState(1);
  const [harm, setHarm] = useState(false);
  const [detected, setDetected] = useState(today());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onOpened(await openIncident({ kind, data_kinds: data, people_affected: people, significant_harm: harm, detected_on: detected }));
    } catch (e) {
      setError(errorText(e, tx));
    } finally {
      setBusy(false);
    }
  };

  return (
    <RecordPanel kicker={tx("Incident register")} title={tx("Record an incident")} onClose={onClose}>
      <p className="rc-note">{tx("Choose what fits. There is no free text here, so no names or details of the people affected enter the record.")}</p>
      <form className="sa-form" onSubmit={(e) => void submit(e)}>
        <label>{tx("What happened")}
          <select value={kind} onChange={(e) => setKind(e.target.value as IncidentKind)}>
            {(Object.keys(KINDS) as IncidentKind[]).map((k) => <option key={k} value={k}>{tx(KINDS[k])}</option>)}
          </select>
        </label>
        <fieldset>
          <legend>{tx("Personal data involved")}</legend>
          <div className="rc-chips">
            {(Object.keys(DATA) as DataKind[]).map((k) => (
              <label key={k} className={"dd-key-tool" + (data.includes(k) ? " is-on" : "")}>
                <input type="checkbox" checked={data.includes(k)} onChange={() => setData((list) => (list.includes(k) ? list.filter((x) => x !== k) : [...list, k]))} />
                {tx(DATA[k])}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="sa-row">
          <label>{tx("People affected (estimate)")}
            <input type="number" min={0} max={10000000} value={people} onChange={(e) => setPeople(Math.max(0, Number(e.target.value) || 0))} />
          </label>
          <label>{tx("Detected on")}
            <input type="date" value={detected} max={today()} onChange={(e) => setDetected(e.target.value)} required />
          </label>
        </div>
        <label className="sa-check">
          <input type="checkbox" checked={harm} onChange={(e) => setHarm(e.target.checked)} />
          {tx("Significant harm to the people affected is likely")}
        </label>
        <button type="submit" className="rc-action is-primary" disabled={busy || data.length === 0}>{busy ? tx("Recording…") : tx("Record the incident")}<small>{tx("Needs your authenticator code")}</small></button>
        {error && <p className="fb-inbox-error" role="alert">{error}</p>}
      </form>
    </RecordPanel>
  );
}

/** One incident as a record: its facts, then the PDPA checklist step by step. */
function IncidentPanel({ incident, onClose, onChanged }: { incident: Incident; onClose: () => void; onChanged: (incident: Incident) => void }) {
  const { tx } = useI18n();
  const { show } = useAppState();
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const act = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try { await work(); } catch (e) { setError(errorText(e, tx)); } finally { setBusy(false); }
  };

  return (
    <RecordPanel kicker={tx("Incident · {id}", { id: incident.id })} title={tx(KINDS[incident.kind])} onClose={onClose}>
      <section className="rc-section">
        <h3>{tx("Details")}</h3>
        <dl className="rc-attrs">
          <dt>{tx("Status")}</dt><dd><span className={"rc-chip " + (incident.status === "open" ? "is-red" : "is-green")}>{incident.status === "open" ? tx("Still open") : tx("Closed")}</span></dd>
          <dt>{tx("Detected on")}</dt><dd>{day(incident.detected_on)}</dd>
          <dt>{tx("Data involved")}</dt><dd><div className="rc-chips">{incident.data_kinds.map((k) => <span key={k} className="rc-chip is-plain">{tx(DATA[k])}</span>)}</div></dd>
          <dt>{tx("People affected")}</dt><dd>{incident.people_affected.toLocaleString("en-MY")}</dd>
          <dt>{tx("Significant harm")}</dt><dd>{incident.significant_harm ? tx("Likely") : tx("Not likely")}</dd>
          <dt>{tx("Recorded by")}</dt><dd>{tx(ROLE_LABEL[incident.opened_by_role] ?? incident.opened_by_role)} · {when(incident.opened_at)}</dd>
        </dl>
      </section>
      <section className="rc-section">
        <h3>{tx("Checklist")}</h3>
        <ol className="sa-steps">
          {incident.checklist.map((item) => (
            <li key={item.step} className={item.done ? "is-done" : item.required ? "" : "is-optional"}>
              <i aria-hidden="true">{item.done ? "✓" : ""}</i>
              <div>
                <strong>{tx(STEPS[item.step][0])}{!item.required && ` · ${tx("not required")}`}</strong>
                <span>{item.done && item.done_at ? tx("Done by {who}, {when}", { who: tx(ROLE_LABEL[item.done_by_role ?? ""] ?? "someone"), when: when(item.done_at) }) : tx(STEPS[item.step][1])}</span>
              </div>
              {!item.done && incident.status === "open" && (
                <button type="button" className="rc-mini" disabled={busy}
                  onClick={() => void act(async () => onChanged(await completeIncidentStep(incident.id, item.step)))}>
                  {item.step === "closed" ? tx("Close") : tx("Mark done")}
                </button>
              )}
            </li>
          ))}
        </ol>
      </section>
      {incident.status === "open" && (
        <section className="rc-section">
          <h3>{tx("Notices")}</h3>
          <div className="rc-actions">
            <button type="button" className="rc-action" disabled={busy}
              onClick={() => void act(async () => { await draftIncidentNotice(incident.id, "commissioner"); setNotice(tx("A draft notice to the Commissioner is waiting in the review inbox. Nothing has been sent.")); })}>
              {tx("Draft the notice to the Commissioner")}<small>{tx("Review inbox")}</small>
            </button>
            {incident.significant_harm && (
              <button type="button" className="rc-action" disabled={busy}
                onClick={() => void act(async () => { await draftIncidentNotice(incident.id, "individuals"); setNotice(tx("A draft notice to the people affected is waiting in the review inbox. Nothing has been sent.")); })}>
                {tx("Draft the notice to the people affected")}<small>{tx("Review inbox")}</small>
              </button>
            )}
          </div>
          {notice && <p className="rc-note" role="status">{notice} <button type="button" className="sa-link" onClick={() => show("inbox")}>{tx("Open the review inbox")}</button></p>}
        </section>
      )}
      {error && <p className="fb-inbox-error" role="alert">{error}</p>}
      <p className="rc-note">{tx("DuitDuit keeps the record and drafts notices; it does not decide the legal thresholds. Check the Commissioner's guidelines and send notices yourself.")}</p>
    </RecordPanel>
  );
}

export default function SecurityActivity() {
  const { t, tx } = useI18n();
  const { identity } = useAuth();
  const isOwner = identity?.role === "owner_director";
  const [events, setEvents] = useState<SecurityEvent[] | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [officer, setOfficer] = useState<Officer | null>(null);
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [panel, setPanel] = useState<"new" | string | null>(null);
  const [choosing, setChoosing] = useState(false);
  const closePanel = useCallback(() => setPanel(null), []);

  const load = useCallback(() => {
    Promise.all([fetchSecurityActivity(), fetchIncidents(), fetchOfficer()])
      .then(([e, i, o]) => { setEvents(e); setIncidents(i); setOfficer(o); setError(null); })
      .catch((e: Error) => setError(friendlyLoadError(e.message)));
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!isOwner) return;
    let active = true;
    fetchTeam().then((m) => active && setTeam(m.filter((x) => x.active))).catch(() => undefined);
    return () => { active = false; };
  }, [isOwner]);

  const opened = incidents.find((i) => i.id === panel) ?? null;
  const open = incidents.filter((i) => i.status === "open").length;
  const warnings = (events ?? []).filter((e) => e.severity !== "info").length;
  const updated = (incident: Incident) => {
    setIncidents((list) => [incident, ...list.filter((i) => i.id !== incident.id)]);
    load();
  };

  const choose = async (userId: string) => {
    try {
      setOfficer(await nameOfficer(userId));
      setChoosing(false);
      load();
    } catch (e) {
      setError(errorText(e, tx));
    }
  };

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="activity" />
      <AppTopBar current="activity" />
      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.company")}</div>
        <h1>{t("nav.trustAudit")}</h1>
        <p>{tx("What happened that matters for security, incidents and what was done about them, and who your data protection officer is.")}</p>
        <SectionTabs section="trust" current="activity" />
      </header>
      <div className="fb-page-body">
        {error && <div className="fb-callout" role="alert">{error}</div>}
        <div className="dd-board-summary">
          <div><span>{tx("Open incidents")}</span><strong className={open ? "is-late" : undefined}>{open}</strong></div>
          <div><span>{tx("Warnings, last 30 days")}</span><strong>{warnings}</strong></div>
          <div><span>{tx("Data protection officer")}</span><strong className="sa-officer">{officer ? <Who name={officer.display_name} /> : tx("Not named yet")}</strong></div>
        </div>
        <div className="sa-grid">
          <section className="fb-cash-card">
            <div className="sa-head">
              <h2>{tx("Security activity")}</h2>
              <span className="rc-note">{tx("Last 30 days")}</span>
            </div>
            {events === null && !error && <p className="rc-note">{tx("Loading…")}</p>}
            {events?.length === 0 && <p className="rc-note">{tx("Nothing security-relevant happened in the last 30 days.")}</p>}
            {events && events.length > 0 && (
              <ul className="rc-list">
                {events.map((e, n) => {
                  const [tone, label] = SEVERITY[e.severity];
                  return (
                    <li key={`${e.at}-${e.kind}-${n}`}>
                      <div className="rc-list-main">
                        <strong>{tx(e.title)}</strong>
                        <span><span className={"rc-chip " + tone}>{tx(label)}</span> {tx(ROLE_LABEL[e.actor_role] ?? e.actor_role)} · {when(e.at)}</span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
            <p className="rc-note">{tx("Kinds and roles only: no names, contact details or what anyone typed. Ordinary sign-ins are in each person's own preferences.")}</p>
          </section>
          <div className="sa-side">
            <section className="fb-cash-card">
              <div className="sa-head">
                <h2>{tx("Incidents")}</h2>
                <button type="button" className="rc-mini" onClick={() => setPanel("new")}>{tx("Record an incident")}</button>
              </div>
              <ul className="rc-list">
                {incidents.length === 0 && <li className="rc-list-empty">{tx("No incidents recorded.")}</li>}
                {incidents.map((i) => {
                  const done = i.checklist.filter((c) => c.required && c.done).length;
                  const required = i.checklist.filter((c) => c.required).length;
                  return (
                    <li key={i.id}>
                      <div className="rc-list-main">
                        <strong>{tx(KINDS[i.kind])}</strong>
                        <span><span className={"rc-chip " + (i.status === "open" ? "is-red" : "is-green")}>{i.status === "open" ? tx("Still open") : tx("Closed")}</span> {tx("{done} of {n} steps", { done, n: required })} · {day(i.detected_on)}</span>
                      </div>
                      <button type="button" className="rc-mini" onClick={() => setPanel(i.id)}>{tx("Open")}</button>
                    </li>
                  );
                })}
              </ul>
              <p className="rc-note">{tx("Malaysia's amended PDPA (from 1 June 2025) requires breach notification to the Commissioner and, where significant harm is likely, to the people affected.")}</p>
            </section>
            <section className="fb-cash-card">
              <div className="sa-head">
                <h2>{tx("Data protection officer")}</h2>
                {isOwner && <button type="button" className="rc-mini" onClick={() => setChoosing((v) => !v)}>{officer ? tx("Change") : tx("Name one")}</button>}
              </div>
              {officer ? (
                <dl className="rc-attrs">
                  <dt>{tx("Officer")}</dt><dd><Who name={officer.display_name} /></dd>
                  <dt>{tx("Role")}</dt><dd>{tx(ROLE_LABEL[officer.role] ?? officer.role)}</dd>
                  <dt>{tx("Email")}</dt><dd>{officer.email_masked}</dd>
                </dl>
              ) : (
                <p className="rc-note">{tx("Not named yet. The amended PDPA requires a data protection officer; the owner names one from the team.")}</p>
              )}
              {choosing && (
                <ul className="rc-list">
                  {team.length === 0 && <li className="rc-list-empty">{tx("No active team members found. Invite one on the Team page first.")}</li>}
                  {team.map((m) => (
                    <li key={m.user_id}>
                      <div className="rc-list-main"><strong><Who name={m.display_name} /></strong><span>{tx(ROLE_LABEL[m.role] ?? m.role)} · {m.email_masked}</span></div>
                      <button type="button" className="rc-mini" onClick={() => void choose(m.user_id)}>{tx("Choose")}</button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </div>
      </div>
      {panel === "new" && <NewIncidentPanel onClose={closePanel} onOpened={(i) => { updated(i); setPanel(i.id); }} />}
      {opened && <IncidentPanel key={opened.id} incident={opened} onClose={closePanel} onChanged={updated} />}
    </div>
  );
}
