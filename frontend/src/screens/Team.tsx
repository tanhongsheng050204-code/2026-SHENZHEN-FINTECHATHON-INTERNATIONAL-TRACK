import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { useAuth } from "../auth/AuthProvider";
import { useI18n } from "../lib/i18n";
import { JOB_LABELS } from "../lib/jobFunctions";
import { PERSONAS } from "../lib/personas";
import { ApiError, friendlyLoadError, type Role } from "../api/client";
import {
  fetchTeam,
  inviteMember,
  signOutMember,
  updateMember,
  type JobFunction,
  type TeamMember,
} from "../api/topicE";

const ROLES: Role[] = ["owner_director", "finance_ops", "compliance", "general_employee"];
const PRIVILEGED: Role[] = ["owner_director", "finance_ops", "compliance"];
const JOBS = Object.keys(JOB_LABELS) as JobFunction[];
const INACTIVE_DAYS = 30;
const DAY_MS = 86_400_000;

const TEAM_ERRORS: Record<string, string> = {
  cannot_deactivate_self: "You can't deactivate your own account.",
  last_owner_required: "The company must keep at least one active owner.",
  member_not_found: "That person is no longer on the team.",
};

function errorText(error: unknown): string {
  const code = error instanceof ApiError ? error.code : error instanceof Error ? error.message : "";
  return TEAM_ERRORS[code] ?? friendlyLoadError(code);
}

function ago(iso: string | null, now: number): string {
  if (!iso) return "Never";
  const days = Math.floor((now - new Date(iso).getTime()) / DAY_MS);
  if (days <= 0) {
    const hours = Math.max(0, Math.round((now - new Date(iso).getTime()) / 3_600_000));
    return hours <= 1 ? "Just now" : `${hours} hours ago`;
  }
  return days === 1 ? "1 day ago" : `${days} days ago`;
}

function JobPicker({ value, onChange, legend }: { value: JobFunction[]; onChange: (v: JobFunction[]) => void; legend: string }) {
  const toggle = (job: JobFunction) =>
    onChange(value.includes(job) ? value.filter((j) => j !== job) : [...value, job]);
  return (
    <fieldset className="fb-team-jobs">
      <legend>{legend}</legend>
      {JOBS.filter((j) => j !== "production").map((job) => (
        <label key={job}>
          <input type="checkbox" checked={value.includes(job)} onChange={() => toggle(job)} />
          {JOB_LABELS[job]}
        </label>
      ))}
    </fieldset>
  );
}

function Invite({ onInvited }: { onInvited: (m: TeamMember) => void }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("general_employee");
  const [jobs, setJobs] = useState<JobFunction[]>(["sales"]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (jobs.length === 0) {
      setError("Choose at least one position.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onInvited(await inviteMember(email, role, jobs));
      setEmail("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="fb-cash-card" onSubmit={(e) => void submit(e)}>
      <h2>Invite someone</h2>
      <div className="fb-cash-whatif">
        <label className="fb-cash-field">
          <span>Email</span>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.example" />
        </label>
        <label className="fb-cash-field">
          <span>Access role</span>
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => <option key={r} value={r}>{PERSONAS[r].label}</option>)}
          </select>
        </label>
      </div>
      <JobPicker value={jobs} onChange={setJobs} legend="Positions they cover" />
      {PRIVILEGED.includes(role) && <p className="fb-inbox-muted">This role must sign in with an authenticator app.</p>}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
      <button className="fb-btn fb-btn-solid fb-team-submit" type="submit" disabled={busy}>{busy ? "Inviting…" : "Send invitation"}</button>
    </form>
  );
}

function MemberRow({ member, now, isOwner, onChange }: { member: TeamMember; now: number; isOwner: boolean; onChange: (m: TeamMember) => void }) {
  const [editing, setEditing] = useState(false);
  const [role, setRole] = useState<Role>(member.role);
  const [jobs, setJobs] = useState<JobFunction[]>(member.job_functions);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inactiveDays = member.last_active_at ? Math.floor((now - new Date(member.last_active_at).getTime()) / DAY_MS) : null;
  const stale = member.active && inactiveDays !== null && inactiveDays >= INACTIVE_DAYS;

  const act = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      await work();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <tr className={member.active ? undefined : "is-inactive"}>
        <td>
          <strong>{member.display_name}</strong>
          <br />
          <span className="fb-inbox-muted">{member.email_masked}</span>
        </td>
        <td>{PERSONAS[member.role].label}</td>
        <td>{member.job_functions.map((j) => JOB_LABELS[j]).join(" · ")}</td>
        <td>
          <span className={"fb-inbox-pill " + (member.mfa_enrolled ? "is-approved" : PRIVILEGED.includes(member.role) ? "is-rejected" : "is-muted")}>
            {member.mfa_enrolled ? "Enrolled" : PRIVILEGED.includes(member.role) ? "Required" : "Optional"}
          </span>
        </td>
        <td>
          {member.active ? ago(member.last_active_at, now) : "Deactivated"}
          {stale && <><br /><span className="fb-inbox-pill is-rejected">Review access</span></>}
        </td>
        {isOwner && (
          <td className="fb-team-actions">
            <button className="fb-cash-more" type="button" aria-expanded={editing} onClick={() => setEditing((v) => !v)}>Manage</button>
          </td>
        )}
      </tr>
      {editing && isOwner && (
        <tr className="fb-team-edit">
          <td colSpan={6}>
            <div className="fb-cash-whatif">
              <label className="fb-cash-field">
                <span>Access role</span>
                <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                  {ROLES.map((r) => <option key={r} value={r}>{PERSONAS[r].label}</option>)}
                </select>
              </label>
            </div>
            <JobPicker value={jobs} onChange={setJobs} legend="Positions" />
            <div className="fb-inbox-actions">
              <button className="fb-btn fb-btn-solid" type="button" disabled={busy || jobs.length === 0} onClick={() => void act(async () => { onChange(await updateMember(member.user_id, { role, job_functions: jobs })); setNote("Saved."); })}>
                Save changes
              </button>
              <button className="fb-btn fb-btn-outline" type="button" disabled={busy} onClick={() => void act(async () => { const n = await signOutMember(member.user_id); setNote(`Signed out of ${n} session${n === 1 ? "" : "s"}.`); })}>
                Sign out everywhere
              </button>
              <button className="fb-btn fb-btn-outline fb-fin-revoke" type="button" disabled={busy} onClick={() => void act(async () => onChange(await updateMember(member.user_id, { active: !member.active })))}>
                {member.active ? "Deactivate" : "Reactivate"}
              </button>
            </div>
            {note && <p className="fb-inbox-muted" role="status">{note}</p>}
            {error && <div className="fb-inbox-error" role="alert">{error}</div>}
          </td>
        </tr>
      )}
    </>
  );
}

export default function Team() {
  const { t } = useI18n();
  const { identity } = useAuth();
  const isOwner = identity?.role === "owner_director";
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now] = useState(() => Date.now());

  useEffect(() => {
    let active = true;
    fetchTeam()
      .then((m) => { if (active) { setMembers(m); setLoaded(true); } })
      .catch((e) => active && setError(errorText(e)));
    return () => { active = false; };
  }, []);

  // Demo data can be dated ahead of the clock; measure from whichever is later.
  const asOf = useMemo(
    () => Math.max(now, ...members.map((m) => (m.last_active_at ? new Date(m.last_active_at).getTime() : 0))),
    [members, now],
  );
  const privileged = members.filter((m) => m.active && PRIVILEGED.includes(m.role));
  const stale = members.filter((m) => m.active && m.last_active_at && asOf - new Date(m.last_active_at).getTime() >= INACTIVE_DAYS * DAY_MS);
  const replace = (member: TeamMember) => setMembers((list) => list.map((m) => (m.user_id === member.user_id ? member : m)));

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="team" />
      <AppTopBar current="team" />
      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.company")}</div>
        <h1>{t("nav.team")}</h1>
        <p>{t("team.desc")}</p>
      </header>
      <div className="fb-page-body">
        <div className="fb-cash">
          {error && <div className="fb-callout" role="alert">{error}</div>}
          {loaded && (
            <>
              <div className="fb-cash-kpis">
                <div className="fb-cash-kpi is-good">
                  <span className="fb-cash-kpi-label">Active members</span>
                  <span className="fb-cash-kpi-value">{members.filter((m) => m.active).length}</span>
                  <span className="fb-cash-kpi-sub">One person can cover several positions</span>
                </div>
                <div className={"fb-cash-kpi " + (privileged.every((m) => m.mfa_enrolled) ? "is-good" : "is-danger")}>
                  <span className="fb-cash-kpi-label">Privileged MFA coverage</span>
                  <span className="fb-cash-kpi-value">{privileged.filter((m) => m.mfa_enrolled).length} / {privileged.length}</span>
                  <span className="fb-cash-kpi-sub">Owner, finance and compliance accounts</span>
                </div>
                <div className={"fb-cash-kpi " + (stale.length ? "is-attn" : "is-good")}>
                  <span className="fb-cash-kpi-label">Needs review</span>
                  <span className="fb-cash-kpi-value">{stale.length}</span>
                  <span className="fb-cash-kpi-sub">Inactive for {INACTIVE_DAYS}+ days</span>
                </div>
              </div>

              <section className="fb-cash-card">
                <h2>People and positions</h2>
                <p className="fb-inbox-muted">Access roles decide what someone may see; positions decide which work they review.</p>
                <div className="fb-cash-scroll">
                  <table className="fb-cash-table fb-team-table">
                    <thead>
                      <tr><th>Member</th><th>Access role</th><th>Positions</th><th>MFA</th><th>Last active</th>{isOwner && <th><span className="fb-sr-only">Actions</span></th>}</tr>
                    </thead>
                    <tbody>
                      {members.map((m) => <MemberRow key={m.user_id} member={m} now={asOf} isOwner={isOwner} onChange={replace} />)}
                    </tbody>
                  </table>
                </div>
                {!isOwner && <p className="fb-inbox-muted">Only the owner can invite people or change access.</p>}
              </section>

              {isOwner && <Invite onInvited={(m) => setMembers((list) => [...list, m])} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
