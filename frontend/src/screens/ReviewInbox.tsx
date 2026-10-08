import { useEffect, useMemo, useState } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { SectionTabs } from "../components/SectionTabs";
import { EmptyState } from "../components/EmptyState";
import { useAuth } from "../auth/AuthProvider";
import { canOpen } from "../lib/access";
import { useAppState } from "../lib/appState";
import type { Screen } from "../lib/screens";
import { useI18n } from "../lib/i18n";
import { JOB_LABELS } from "../lib/jobFunctions";
import { ApiError, friendlyLoadError } from "../api/client";
import {
  decidableCount,
  decideReviewAction,
  fetchReviewInbox,
  ringgit,
  type DataMode,
  type JobFunction,
  type ReviewAction,
  type ReviewDecisionRequest,
} from "../api/topicE";

const LEVEL_HINT: Record<ReviewAction["autonomy_level"], string> = {
  L0: "Read only",
  L1: "Draft",
  L2: "External action",
  L3: "Money movement",
};

// Backend refusal codes from the review inbox, in words a reviewer can act on.
const DECISION_ERRORS: Record<string, string> = {
  owner_approval_required: "Only the owner can approve this step.",
  maker_approval_required: "Someone who holds this position must approve first, then the owner checks.",
  same_person_cannot_approve_twice: "You already approved this. A different person must check it.",
  edit_not_allowed_at_l3: "Money movement can't be edited, only approved or rejected.",
  not_your_job_function: "This item belongs to a position you don't hold.",
  action_not_found: "This item no longer exists. Refresh the inbox.",
};

function isOpen(action: ReviewAction): boolean {
  return action.status === "pending" || action.status === "awaiting_second_approval";
}

function StatusPill({ action }: { action: ReviewAction }) {
  const { t } = useI18n();
  if (!isOpen(action)) {
    const label = { approved: "Approved", edited: "Edited and approved", rejected: "Rejected" }[action.status as "approved" | "edited" | "rejected"];
    return <span className={"fb-inbox-pill is-" + action.status}>{label}</span>;
  }
  if (action.can_decide) return <span className="fb-inbox-pill is-can">{t("inbox.canApprove")}</span>;
  if (action.status === "awaiting_second_approval") return <span className="fb-inbox-pill is-muted">{t("inbox.waitingOwner")}</span>;
  return <span className="fb-inbox-pill is-muted">{t("inbox.readOnly")}</span>;
}

function LevelPill({ level }: { level: ReviewAction["autonomy_level"] }) {
  return <span className={"fb-inbox-level is-" + level.toLowerCase()}>{level}</span>;
}

function ApprovalSteps({ action }: { action: ReviewAction }) {
  const makerDone = action.approvals.length >= 1;
  const checkerDone = action.approvals.length >= 2;
  const step = (n: number, label: string, detail: string, state: "done" | "current" | "todo") => (
    <li className={"fb-inbox-step is-" + state}>
      <span className="fb-inbox-step-label">{n} · {label}</span>
      <span>{detail}</span>
    </li>
  );
  return (
    <ol className="fb-inbox-steps" aria-label="Approvals">
      {step(1, "Agent", "Flagged and drafted", "done")}
      {step(2, "Maker", makerDone ? "Approved" : "Position holder approves", makerDone ? "done" : "current")}
      {step(3, "Checker", checkerDone ? "Approved" : "Owner, a different person", checkerDone ? "done" : makerDone ? "current" : "todo")}
    </ol>
  );
}

// Where a piece of evidence lives, from the prefix of its source reference.
function evidenceScreen(source: string): Screen | null {
  const prefix = source.split(":")[0];
  const map: Record<string, Screen> = {
    einvoice: "einvoice",
    cashflow: "cashflow",
    finance: "finance",
    financing: "financing",
    payables: "cashflow",
    payroll: "positions",
    pipeline: "customers",
    email: "ingestion",
    stock: "positions",
    team: "team",
    review: "inbox",
  };
  return map[prefix] ?? null;
}

export default function ReviewInbox() {
  const { t } = useI18n();
  const { setReviewInboxCount, show, askRole } = useAppState();
  const { identity } = useAuth();
  const role = identity?.role ?? askRole;
  const [actions, setActions] = useState<ReviewAction[]>([]);
  const [jobFunctions, setJobFunctions] = useState<JobFunction[]>([]);
  const [dataMode, setDataMode] = useState<DataMode>("live");
  const [filter, setFilter] = useState<JobFunction | "all">("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    let active = true;
    fetchReviewInbox()
      .then((inbox) => {
        if (!active) return;
        setActions(inbox.actions);
        setJobFunctions(inbox.job_functions);
        setDataMode(inbox.data_mode);
        setSelectedId(inbox.actions.find((a) => a.can_decide)?.id ?? inbox.actions[0]?.id ?? null);
      })
      .catch((error: Error) => active && setLoadError(friendlyLoadError(error.message)))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  // Tabs: every position with items. Compliance oversees all positions, so
  // tabs come from the items, not only from the positions a person decides for.
  const tabs = useMemo(() => {
    const counts = new Map<JobFunction, number>();
    for (const a of actions) counts.set(a.reviewer_job_function, (counts.get(a.reviewer_job_function) ?? 0) + 1);
    return [...counts.entries()];
  }, [actions]);

  const visible = filter === "all" ? actions : actions.filter((a) => a.reviewer_job_function === filter);
  const selected = actions.find((a) => a.id === selectedId) ?? null;
  const overseesOthers = actions.some((a) => !jobFunctions.includes(a.reviewer_job_function));

  const select = (id: string) => {
    setSelectedId(id);
    setEditing(false);
    setDecisionError(null);
  };

  const decide = async (request: ReviewDecisionRequest) => {
    if (!selected) return;
    setBusy(true);
    setDecisionError(null);
    try {
      const { action } = await decideReviewAction(selected.id, request);
      const next = actions.map((a) => (a.id === action.id ? { ...action, can_decide: false } : a));
      setActions(next);
      setReviewInboxCount(decidableCount(next));
      setEditing(false);
    } catch (error) {
      const code = error instanceof ApiError ? error.code : "";
      setDecisionError(DECISION_ERRORS[code] ?? friendlyLoadError(code));
    } finally {
      setBusy(false);
    }
  };

  const approveLabel = selected?.autonomy_level === "L3"
    ? t(selected.status === "awaiting_second_approval" ? "inbox.approveChecker" : "inbox.approveMaker")
    : t("inbox.approve");

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="inbox" />
      <AppTopBar current="inbox" />

      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("inbox.eyebrow")}</div>
        <h1>{t("inbox.title")}</h1>
        <p>{t("inbox.desc")}</p>
        <SectionTabs section="inbox" current="inbox" />
      </header>

      <div className="fb-page-body">
        {dataMode === "stub" && <div className="fb-callout">{t("inbox.stub")}</div>}

        {loading && <div className="fb-callout">Loading your inbox…</div>}
        {loadError && <div className="fb-callout" role="alert">{loadError}</div>}

        {!loading && !loadError && actions.length === 0 && (
          <EmptyState title={t("inbox.empty")} description={t("inbox.emptyDesc")} />
        )}

        {!loading && !loadError && actions.length > 0 && (
          <>
            <div className="fb-inbox-tabs" role="tablist" aria-label="Filter by position">
              <button type="button" role="tab" aria-selected={filter === "all"} className={filter === "all" ? "is-current" : undefined} onClick={() => setFilter("all")}>
                {t("inbox.all")} · {actions.length}
              </button>
              {tabs.map(([job, count]) => (
                <button key={job} type="button" role="tab" aria-selected={filter === job} className={filter === job ? "is-current" : undefined} onClick={() => setFilter(job)}>
                  {JOB_LABELS[job]} · {count}
                </button>
              ))}
            </div>

            <div className="fb-inbox-layout">
              <section className="fb-inbox-list" aria-label="Items">
                {visible.map((action) => (
                  <button
                    key={action.id}
                    type="button"
                    className={"fb-inbox-row" + (action.id === selectedId ? " is-selected" : "") + (!action.can_decide && isOpen(action) ? " is-muted" : "")}
                    aria-pressed={action.id === selectedId}
                    onClick={() => select(action.id)}
                  >
                    <LevelPill level={action.autonomy_level} />
                    <span className="fb-inbox-row-main">
                      <span className="fb-inbox-row-title">{action.title}</span>
                      <span className="fb-inbox-row-sub">
                        {JOB_LABELS[action.reviewer_job_function]}
                        {action.amount !== null && <> · <strong>{ringgit(action.amount)}</strong></>}
                      </span>
                    </span>
                    <StatusPill action={action} />
                  </button>
                ))}
                {overseesOthers && <div className="fb-inbox-note">{t("inbox.compliance")}</div>}
              </section>

              <section className="fb-inbox-detail" aria-label="Item detail" aria-live="polite">
                {!selected && <p className="fb-inbox-muted">{t("inbox.select")}</p>}
                {selected && (
                  <>
                    <div className="fb-inbox-detail-tags">
                      <span className={"fb-inbox-level is-" + selected.autonomy_level.toLowerCase()}>
                        {selected.autonomy_level} · {LEVEL_HINT[selected.autonomy_level]}
                      </span>
                      <StatusPill action={selected} />
                    </div>
                    <h2>{selected.title}</h2>
                    <p className="fb-inbox-summary">{selected.summary}</p>

                    {selected.autonomy_level === "L3" && <ApprovalSteps action={selected} />}

                    {selected.evidence.length > 0 && (
                      <div>
                        <div className="fb-inbox-label">{t("inbox.evidence")}</div>
                        <div className="fb-inbox-chips">
                          {selected.evidence.map((e) => {
                            const target = evidenceScreen(e.source);
                            return target && canOpen(target, role) ? (
                              <button key={e.source} type="button" className="fb-inbox-chip fb-inbox-chip-link" title={e.source} onClick={() => show(target)}>{e.label} →</button>
                            ) : (
                              <span key={e.source} className="fb-inbox-chip" title={e.source}>{e.label}</span>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {selected.draft !== null && !editing && (
                      <div>
                        <div className="fb-inbox-label">{t("inbox.draft")}</div>
                        <blockquote className="fb-inbox-draft">{selected.draft}</blockquote>
                      </div>
                    )}

                    {editing && (
                      <label className="fb-inbox-edit">
                        <span className="fb-inbox-label">{t("inbox.draft")}</span>
                        <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={5} maxLength={5000} />
                      </label>
                    )}

                    {decisionError && <div className="fb-inbox-error" role="alert">{decisionError}</div>}

                    {isOpen(selected) && (
                      <div className="fb-inbox-actions">
                        {editing ? (
                          <>
                            <button className="fb-btn fb-btn-solid" type="button" disabled={busy || draft.trim() === ""} onClick={() => void decide({ decision: "edit", edited_draft: draft })}>
                              {t("inbox.saveEdit")}
                            </button>
                            <button className="fb-btn fb-btn-outline" type="button" disabled={busy} onClick={() => setEditing(false)}>{t("inbox.cancel")}</button>
                          </>
                        ) : (
                          <>
                            <button className="fb-btn fb-btn-solid" type="button" disabled={busy || !selected.can_decide} onClick={() => void decide({ decision: "approve" })}>
                              {approveLabel}
                            </button>
                            <button className="fb-btn fb-btn-outline" type="button" disabled={busy} onClick={() => void decide({ decision: "reject" })}>
                              {t("inbox.reject")}
                            </button>
                            {selected.autonomy_level !== "L3" && selected.draft !== null && (
                              <button className="fb-btn fb-btn-outline" type="button" disabled={busy || !selected.can_decide} onClick={() => { setDraft(selected.draft ?? ""); setEditing(true); }}>
                                {t("inbox.edit")}
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    )}
                    {isOpen(selected) && selected.autonomy_level === "L3" && <p className="fb-inbox-muted">{t("inbox.noEditL3")}</p>}
                  </>
                )}
              </section>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
