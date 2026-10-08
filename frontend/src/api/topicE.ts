// Topic E endpoints. Shapes mirror docs/api/topic-e-contract.json; every
// response says whether its data is a canned stub or computed live.
import { ApiError, authenticatedFetch, parse, publicFetch, type Role } from "./client";

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

// ── Cash flow ───────────────────────────────────────────────────────────────

export type ForecastHorizon = 30 | 60 | 90;

export interface ForecastPoint {
  day: number;
  date: string;
  best: string;
  likely: string;
  worst: string;
}

export interface Shortfall {
  day: number;
  date: string;
  likely_balance: string;
  minimum_balance: string;
  gap: string;
}

export interface ForecastAlert {
  id: string;
  severity: "info" | "warning" | "critical";
  title: string;
  detail: string;
  day: number;
  date: string;
}

export interface CashSignal {
  id: string;
  source_agent: string;
  job_function: JobFunction;
  /** "risk" signals annotate the forecast; they never move the balance. */
  kind: "inflow" | "outflow" | "risk";
  label: string;
  amount_myr: string;
  source_currency: string;
  source_amount: string | null;
  fx_rate: string | null;
  best_day: number;
  likely_day: number | null;
  worst_day: number | null;
  probability: number;
  affects: string | null;
}

export interface ForecastResponse {
  data_mode: DataMode;
  as_of: string;
  currency: "MYR";
  horizon_days: number;
  opening_balance: string;
  minimum_balance: string;
  points: ForecastPoint[];
  shortfall: Shortfall | null;
  alerts: ForecastAlert[];
  drivers: CashSignal[];
}

export interface AgentCashTotal {
  agent_id: string;
  job_function: JobFunction;
  inflow_total: string;
  outflow_total: string;
  at_risk_total: string;
  signal_count: number;
}

export interface CashSignalsResponse {
  data_mode: DataMode;
  horizon_days: number;
  signals: CashSignal[];
  by_agent: AgentCashTotal[];
}

export interface EventShift {
  event_id: string;
  shift_days: number;
}

export async function fetchForecast(horizonDays: ForecastHorizon = 90): Promise<ForecastResponse> {
  return parse<ForecastResponse>(await authenticatedFetch(`/cashflow/forecast?horizon_days=${horizonDays}`));
}

export async function runScenario(horizonDays: ForecastHorizon, shifts: EventShift[]): Promise<ForecastResponse> {
  return parse<ForecastResponse>(
    await authenticatedFetch("/cashflow/scenarios", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ horizon_days: horizonDays, shifts }),
    }),
  );
}

export async function fetchCashSignals(horizonDays: ForecastHorizon = 90): Promise<CashSignalsResponse> {
  return parse<CashSignalsResponse>(await authenticatedFetch(`/cashflow/signals?horizon_days=${horizonDays}`));
}

/** Ringgit with two decimals, e.g. "RM20,560.00". */
export function ringgit(amount: string | number | null): string {
  if (amount === null) return "—";
  const value = typeof amount === "number" ? amount : Number(amount);
  if (!Number.isFinite(value)) return `RM${amount}`;
  const sign = value < 0 ? "−" : "";
  return sign + "RM" + Math.abs(value).toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Financing ───────────────────────────────────────────────────────────────

export type Jurisdiction = "MY" | "CN";

export interface RuleResult {
  rule: string;
  passed: boolean;
  detail: string;
  evidence: EvidenceRef[];
}

export interface FinancingProduct {
  id: string;
  jurisdiction: Jurisdiction;
  category: string;
  name: string;
  illustrative_terms: string;
  last_verified: string | null;
  source_url: string | null;
}

export interface FinancingMatch {
  product: FinancingProduct;
  eligible: boolean;
  fit_score: number;
  rules: RuleResult[];
  explanation: string;
}

export interface FinancingMatchesResponse {
  data_mode: DataMode;
  jurisdiction: Jurisdiction;
  disclaimer: string;
  shortfall_gap: string | null;
  matches: FinancingMatch[];
}

export async function fetchFinancingMatches(jurisdiction: Jurisdiction = "MY"): Promise<FinancingMatchesResponse> {
  return parse<FinancingMatchesResponse>(await authenticatedFetch(`/financing/matches?jurisdiction=${jurisdiction}`));
}

/** Drafts an application pack; it lands in the review inbox for the owner. */
export async function prepareApplicationPack(productId: string): Promise<ReviewDecisionResponse> {
  return parse<ReviewDecisionResponse>(
    await authenticatedFetch("/financing/application-packs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: productId }),
    }),
  );
}

// ── Passport, audit packs and external grants ───────────────────────────────

export interface PassportMetric {
  key: string;
  label: string;
  value: string;
  evidence: EvidenceRef[];
}

export interface AnchorRef {
  repository_path: string;
  anchored_at: string | null;
  commit: string | null;
}

export interface Passport {
  id: string;
  version: number;
  company_label: string;
  issued_at: string;
  metrics: PassportMetric[];
  sha256: string;
  audit_entry_id: number | null;
  anchor: AnchorRef | null;
}

export interface VerificationResult {
  data_mode: DataMode;
  passport_id: string;
  status: "verified" | "mismatch" | "unknown_passport";
  expected_sha256: string | null;
  computed_sha256: string;
  chain_intact: boolean;
  anchor: AnchorRef | null;
  mismatched_fields: string[];
}

export interface AuditPackItem {
  key: string;
  label: string;
  description: string;
  sha256: string;
}

export interface AuditPack {
  id: string;
  period: string;
  company_label: string;
  created_at: string;
  items: AuditPackItem[];
  sha256: string;
}

export type GrantKind = "lender" | "auditor";

export interface ExternalGrant {
  id: string;
  kind: GrantKind;
  scope: string;
  grantee_email_token: string;
  expires_at: string;
  allow_exact_values: boolean;
  status: "active" | "revoked" | "expired";
  share_path: string;
}

export interface GrantRequest {
  grantee_email: string;
  expires_in_days: number;
  allow_exact_values: boolean;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export async function fetchPassports(): Promise<Passport[]> {
  return (await parse<{ passports: Passport[] }>(await authenticatedFetch("/passports"))).passports;
}

export async function issuePassport(): Promise<Passport> {
  return (await parse<{ passport: Passport }>(await authenticatedFetch("/passports", { method: "POST" }))).passport;
}

/** Public check a lender can run on a Passport document they were given. */
export async function verifyPassport(document: Passport): Promise<VerificationResult> {
  return parse<VerificationResult>(await authenticatedFetch("/lender/verify", json(document)));
}

export async function fetchAuditPacks(): Promise<AuditPack[]> {
  return (await parse<{ packs: AuditPack[] }>(await authenticatedFetch("/audit-packs"))).packs;
}

function grantsPath(kind: GrantKind, scopeId: string): string {
  return kind === "lender"
    ? `/passports/${encodeURIComponent(scopeId)}/grants`
    : `/audit-packs/${encodeURIComponent(scopeId)}/grants`;
}

export async function fetchGrants(kind: GrantKind, scopeId: string): Promise<ExternalGrant[]> {
  return (await parse<{ grants: ExternalGrant[] }>(await authenticatedFetch(grantsPath(kind, scopeId)))).grants;
}

export async function createGrant(kind: GrantKind, scopeId: string, request: GrantRequest): Promise<ExternalGrant> {
  return (await parse<{ grant: ExternalGrant }>(await authenticatedFetch(grantsPath(kind, scopeId), json(request)))).grant;
}

export async function revokeGrant(kind: GrantKind, scopeId: string, grantId: string): Promise<ExternalGrant> {
  return (
    await parse<{ grant: ExternalGrant }>(
      await authenticatedFetch(`${grantsPath(kind, scopeId)}/${encodeURIComponent(grantId)}`, { method: "DELETE" }),
    )
  ).grant;
}

// ── Agents ──────────────────────────────────────────────────────────────────

export interface AgentSkill {
  id: string;
  name: string;
  wave: "W1" | "W2";
  availability: "available" | "planned";
  side_effect: "read" | "draft" | "external" | "money";
}

export interface ScopedAutonomy {
  action: string;
  level: AutonomyLevel;
  max_amount: string | null;
}

export interface AgentMetrics {
  proposals: number;
  approved_unedited: number;
  approved_edited: number;
  rejected: number;
  unedited_approval_rate: number | null;
  promotion_recommended: boolean;
}

export interface AgentCard {
  id: string;
  name: string;
  purpose: string;
  job_function: JobFunction | null;
  reviewer_job_function: JobFunction | null;
  build_status: "built" | "designed";
  autonomy_level: AutonomyLevel;
  scoped_autonomy: ScopedAutonomy[];
  skills: AgentSkill[];
  kill_switch_engaged: boolean;
  metrics: AgentMetrics | null;
}

export interface AgentListResponse {
  data_mode: DataMode;
  global_kill_switch_engaged: boolean;
  agents: AgentCard[];
}

export interface JourneyAgent {
  agent_id: string;
  name: string;
  autonomy_level: AutonomyLevel;
  build_status: "built" | "designed";
  override_rate: number | null;
  estimated_hours_saved: number;
}

export interface JourneyResponse {
  data_mode: DataMode;
  estimate_note: string;
  functions: { job_function: JobFunction; agents: JourneyAgent[] }[];
}

export interface AgentRunEvent {
  run_id: string;
  sequence: number;
  type: "run_started" | "tool_called" | "proposal_created" | "waiting_for_review" | "run_completed";
  agent_id: string;
  message: string;
  action_id: string | null;
}

export async function fetchAgents(): Promise<AgentListResponse> {
  return parse<AgentListResponse>(await authenticatedFetch("/agents"));
}

export async function fetchJourney(): Promise<JourneyResponse> {
  return parse<JourneyResponse>(await authenticatedFetch("/agents/journey"));
}

export async function setKillSwitch(engaged: boolean, agentId: string | null = null): Promise<AgentListResponse> {
  return parse<AgentListResponse>(await authenticatedFetch("/agents/kill-switch", json({ agent_id: agentId, engaged })));
}

/** Grants (or lowers) autonomy for one action, optionally capped by amount. L3 is never delegable. */
export async function changeAutonomy(
  agentId: string,
  action: string,
  level: AutonomyLevel,
  maxAmount: string | null = null,
): Promise<AgentCard> {
  return (
    await parse<{ agent: AgentCard }>(
      await authenticatedFetch(
        `/agents/${encodeURIComponent(agentId)}/autonomy`,
        json({ action, level, max_amount: maxAmount }),
      ),
    )
  ).agent;
}

/**
 * Starts a supervised run and calls onEvent for each server-sent event.
 * Uses fetch rather than EventSource because EventSource cannot send the
 * Authorization header.
 */
export async function runAgents(goal: string, onEvent: (event: AgentRunEvent) => void): Promise<void> {
  const created = await parse<{ run_id: string; events_url: string }>(
    await authenticatedFetch("/agents/runs", json({ goal })),
  );
  const response = await authenticatedFetch(created.events_url);
  if (!response.ok || !response.body) {
    await parse(response);
    return;
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const data = block
        .split(/\r?\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (data) onEvent(JSON.parse(data) as AgentRunEvent);
    }
  }
}

// ── Positions ───────────────────────────────────────────────────────────────

export interface PositionSummary {
  job_function: JobFunction;
  display_name: string;
  enabled: boolean;
  build_status: "built" | "designed";
  agent_ids: string[];
}

export interface SkillResult {
  skill_id: string;
  title: string;
  value: string | null;
  summary: string;
  status: "ok" | "attention" | "risk" | "planned";
  evidence: EvidenceRef[];
}

export interface PositionWorkspace {
  data_mode: DataMode;
  job_function: JobFunction;
  display_name: string;
  build_status: "built" | "designed";
  agents: AgentCard[];
  skill_results: SkillResult[];
  cash_contribution: { role: string; inflow_total: string; outflow_total: string; at_risk_total: string; signal_ids: string[] };
  inbox_count: number;
}

export async function fetchPositions(): Promise<PositionSummary[]> {
  return (await parse<{ positions: PositionSummary[] }>(await authenticatedFetch("/positions"))).positions;
}

export async function fetchWorkspace(job: JobFunction): Promise<PositionWorkspace> {
  return parse<PositionWorkspace>(await authenticatedFetch(`/positions/${job}/workspace`));
}

// ── Team ────────────────────────────────────────────────────────────────────


export interface TeamMember {
  user_id: string;
  display_name: string;
  email_masked: string;
  role: Role;
  job_functions: JobFunction[];
  active: boolean;
  mfa_enrolled: boolean;
  last_active_at: string | null;
}

export async function fetchTeam(): Promise<TeamMember[]> {
  return (await parse<{ members: TeamMember[] }>(await authenticatedFetch("/team/members"))).members;
}

export async function inviteMember(email: string, role: Role, jobFunctions: JobFunction[]): Promise<TeamMember> {
  return (
    await parse<{ member: TeamMember }>(
      await authenticatedFetch("/team/invitations", json({ email, role, job_functions: jobFunctions })),
    )
  ).member;
}

export async function updateMember(
  userId: string,
  changes: { role?: Role; job_functions?: JobFunction[]; active?: boolean },
): Promise<TeamMember> {
  return (
    await parse<{ member: TeamMember }>(
      await authenticatedFetch(`/team/members/${encodeURIComponent(userId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      }),
    )
  ).member;
}

export async function signOutMember(userId: string): Promise<number> {
  return (
    await parse<{ sessions_revoked: number }>(
      await authenticatedFetch(`/team/members/${encodeURIComponent(userId)}/sign-out`, { method: "POST" }),
    )
  ).sessions_revoked;
}

// ── Trust center ────────────────────────────────────────────────────────────

export interface PostureMetric {
  key: string;
  label: string;
  value: string;
  status: "good" | "attention" | "risk";
  detail: string;
}

export interface GuardrailEvent {
  id: string;
  occurred_at: string;
  agent_id: string | null;
  owasp_code: string;
  title: string;
  detail: string;
  outcome: "blocked" | "quarantined" | "escalated";
}

export interface PostureResponse {
  data_mode: DataMode;
  score: number;
  metrics: PostureMetric[];
  recent_events: GuardrailEvent[];
}

export async function fetchPosture(): Promise<PostureResponse> {
  return parse<PostureResponse>(await authenticatedFetch("/trust/posture"));
}

export async function fetchGuardrailEvents(): Promise<GuardrailEvent[]> {
  return (await parse<{ events: GuardrailEvent[] }>(await authenticatedFetch("/trust/guardrail-events"))).events;
}

// ── Errors ──────────────────────────────────────────────────────────────────

/**
 * The backend answers refusals with a code ("no_changes") and validation
 * failures with a list ({msg: "Value error, owner_must_receive_critical_alerts"}).
 * Returns the first code either way.
 */
export function errorCode(error: unknown): string {
  const raw: unknown = error instanceof ApiError ? error.code : error instanceof Error ? error.message : "";
  if (Array.isArray(raw)) {
    const first = raw[0] as { msg?: string; type?: string } | undefined;
    return (first?.msg ?? first?.type ?? "invalid_request").replace(/^Value error, /, "");
  }
  return typeof raw === "string" ? raw : "";
}

// ── Company settings ────────────────────────────────────────────────────────

export type SettingsArea = "profile" | "positions" | "approvals" | "alerts" | "financing" | "security" | "branding";
export type IndustryTemplateId = "trading" | "services" | "manufacturing";

export interface CompanyProfile {
  company_name: string;
  industry: IndustryTemplateId;
  size: "micro" | "small" | "medium";
  currency: string;
  fiscal_year_start_month: number;
  state: string;
  working_days: string[];
  languages: ("en" | "ms" | "zh")[];
}

export interface PositionSetting {
  job_function: JobFunction;
  enabled: boolean;
  display_name: string;
}

export interface TenantSettings {
  profile: CompanyProfile;
  positions: PositionSetting[];
  approvals: {
    owner_escalation_amount: string;
    owner_escalation_customer_count: number;
    promotion_min_sample: number;
    promotion_min_unedited_rate: number;
    demotion_max_rejection_rate: number;
    quiet_hours_start: string;
    quiet_hours_end: string;
  };
  alerts: {
    minimum_cash_balance: string;
    alert_horizon_days: number;
    recipients: JobFunction[];
    channels: ("in_app" | "email" | "telegram")[];
    critical_alerts_enabled: true;
  };
  financing: { islamic_only: boolean; excluded_categories: string[]; jurisdictions: Jurisdiction[] };
  security: { mfa_required_roles: Role[]; session_idle_minutes: number };
  branding: { display_name: string; document_footer: string | null };
}

export interface SettingsResponse {
  data_mode: DataMode;
  version: number;
  template: IndustryTemplateId;
  settings: TenantSettings;
}

export interface SettingsChange {
  id: string;
  area: SettingsArea | "rollback";
  status: "applied" | "pending_approval" | "rejected";
  requires_approval: boolean;
  version: number;
  preview: string[];
}

export interface SettingsChangeResponse {
  data_mode: DataMode;
  change: SettingsChange;
  settings: TenantSettings;
}

export interface IndustryTemplate {
  id: IndustryTemplateId;
  name: string;
  description: string;
  enabled_positions: JobFunction[];
  designed_positions: JobFunction[];
  demo_data: "full" | "settings_only";
}

export interface TemplatePreview {
  template_id: IndustryTemplateId;
  positions_added: JobFunction[];
  positions_removed: JobFunction[];
  designed_positions: JobFunction[];
  data_kept: boolean;
}

export async function fetchSettings(): Promise<SettingsResponse> {
  return parse<SettingsResponse>(await authenticatedFetch("/settings"));
}

export async function proposeSettingsChange(area: SettingsArea, value: unknown): Promise<SettingsChangeResponse> {
  return parse<SettingsChangeResponse>(await authenticatedFetch("/settings/changes", json({ area, value })));
}

export async function fetchSettingsChanges(): Promise<SettingsChange[]> {
  return (await parse<{ changes: SettingsChange[] }>(await authenticatedFetch("/settings/changes"))).changes;
}

export async function decideSettingsChange(changeId: string, decision: "approve" | "reject"): Promise<SettingsChangeResponse> {
  return parse<SettingsChangeResponse>(
    await authenticatedFetch(`/settings/changes/${encodeURIComponent(changeId)}/${decision}`, { method: "POST" }),
  );
}

export async function rollbackSettings(version: number): Promise<SettingsChangeResponse> {
  return parse<SettingsChangeResponse>(await authenticatedFetch("/settings/rollback", json({ version })));
}

export async function fetchIndustryTemplates(): Promise<{ current: IndustryTemplateId; templates: IndustryTemplate[] }> {
  return parse(await authenticatedFetch("/settings/templates"));
}

export async function previewIndustryTemplate(id: IndustryTemplateId): Promise<TemplatePreview> {
  return parse<TemplatePreview>(await authenticatedFetch(`/settings/templates/${id}/preview`, { method: "POST" }));
}

export async function applyIndustryTemplate(id: IndustryTemplateId): Promise<SettingsChangeResponse> {
  return parse<SettingsChangeResponse>(await authenticatedFetch(`/settings/templates/${id}/apply`, { method: "POST" }));
}

// ── Message templates, import mappings, alert rules ─────────────────────────

export interface MessageTemplate {
  id: string;
  kind: "payment_reminder" | "customer_reply" | "supplier_query";
  language: "en" | "ms" | "zh";
  tone: "formal" | "friendly";
  body: string;
  placeholders: string[];
  status: "draft" | "approved";
}

export const TEMPLATE_PLACEHOLDERS = ["customer_name", "invoice_no", "amount", "due_date", "company_name", "sender_name"];

export async function fetchMessageTemplates(): Promise<MessageTemplate[]> {
  return (await parse<{ templates: MessageTemplate[] }>(await authenticatedFetch("/settings/message-templates"))).templates;
}

export async function createMessageTemplate(
  template: Pick<MessageTemplate, "kind" | "language" | "tone" | "body">,
): Promise<MessageTemplate> {
  return (await parse<{ template: MessageTemplate }>(await authenticatedFetch("/settings/message-templates", json(template)))).template;
}

export async function approveMessageTemplate(id: string): Promise<MessageTemplate> {
  return (
    await parse<{ template: MessageTemplate }>(
      await authenticatedFetch(`/settings/message-templates/${encodeURIComponent(id)}/approve`, { method: "POST" }),
    )
  ).template;
}

export type ImportSchema = "bank_statement_v1" | "payables_register_v1";

export const IMPORT_FIELDS: Record<ImportSchema, { all: string[]; required: string[] }> = {
  bank_statement_v1: {
    all: ["date", "description", "debit", "credit", "balance", "counterparty", "reference"],
    required: ["date", "description", "debit", "credit"],
  },
  payables_register_v1: {
    all: ["bill_id", "supplier", "amount", "currency", "due_date", "status", "bank_account"],
    required: ["bill_id", "supplier", "amount", "currency", "due_date"],
  },
};

export interface ImportMapping {
  id: string;
  schema_name: ImportSchema;
  name: string;
  column_map: Record<string, string>;
  header_fingerprint: string;
}

export async function fetchImportMappings(): Promise<ImportMapping[]> {
  return (await parse<{ mappings: ImportMapping[] }>(await authenticatedFetch("/settings/import-mappings"))).mappings;
}

export async function createImportMapping(
  schemaName: ImportSchema,
  name: string,
  headers: string[],
  columnMap: Record<string, string>,
): Promise<ImportMapping> {
  return (
    await parse<{ mapping: ImportMapping }>(
      await authenticatedFetch(
        "/settings/import-mappings",
        json({ schema_name: schemaName, name, headers, column_map: columnMap }),
      ),
    )
  ).mapping;
}

export async function matchImportMapping(schemaName: ImportSchema, headers: string[]): Promise<ImportMapping> {
  return (
    await parse<{ mapping: ImportMapping }>(
      await authenticatedFetch("/settings/import-mappings/match", json({ schema_name: schemaName, headers })),
    )
  ).mapping;
}

export type AlertMetric =
  | "projected_balance"
  | "overdue_amount_per_customer"
  | "stock_below_reorder"
  | "payroll_coverage_days"
  | "marketing_return_per_ringgit"
  | "open_disputes";

export interface AlertRule {
  id: string;
  metric: AlertMetric;
  operator: "above" | "below";
  threshold: string;
  recipients: JobFunction[];
  channel: "in_app" | "email" | "telegram";
  enabled: boolean;
}

export async function fetchAlertRules(): Promise<AlertRule[]> {
  return (await parse<{ rules: AlertRule[] }>(await authenticatedFetch("/settings/alert-rules"))).rules;
}

export async function createAlertRule(rule: Omit<AlertRule, "id" | "enabled">): Promise<AlertRule> {
  return (await parse<{ rule: AlertRule }>(await authenticatedFetch("/settings/alert-rules", json(rule)))).rule;
}

// ── Public share links (no sign-in) ─────────────────────────────────────────

export async function fetchSharedPassport(token: string): Promise<Passport> {
  return (await parse<{ passport: Passport }>(await publicFetch(`/lender/passports/${encodeURIComponent(token)}`))).passport;
}

export async function fetchSharedAuditPack(token: string): Promise<AuditPack> {
  return (await parse<{ pack: AuditPack }>(await publicFetch(`/auditor/packs/${encodeURIComponent(token)}`))).pack;
}

/** The same check as verifyPassport, for someone who is not signed in. */
export async function verifyPassportPublic(document: unknown): Promise<VerificationResult> {
  return parse<VerificationResult>(await publicFetch("/lender/verify", json(document)));
}

// ── Credit scorecard ────────────────────────────────────────────────────────

export interface ScoreFactor {
  key: string;
  label: string;
  value: string;
  points: number;
  max_points: number;
  reason: string;
  evidence: EvidenceRef[];
}

export interface PublicSignal {
  source: "google_maps" | "shopee" | "grabfood" | "lazada";
  metric: string;
  value: string;
  trend: string;
  status: "ok" | "watch" | "risk";
  synthetic: boolean;
}

export interface ScorecardResponse {
  data_mode: DataMode;
  method: "expert_weights" | "calibrated";
  method_note: string;
  score: number;
  min_score: number;
  max_score: number;
  grade: "A" | "B" | "C" | "D" | "E";
  base_points: number;
  factors: ScoreFactor[];
  public_signals: PublicSignal[];
  public_data_note: string;
  disclaimer: string;
}

export async function fetchScorecard(): Promise<ScorecardResponse> {
  return parse<ScorecardResponse>(await authenticatedFetch("/financing/scorecard"));
}
