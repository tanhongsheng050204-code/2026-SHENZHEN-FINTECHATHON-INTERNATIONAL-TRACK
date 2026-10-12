// Comments and @mentions, the collections board, automations, saved views and chat
// notifications. The backend decides who may do what; these only call it.
import { ApiError, authenticatedFetch, parse } from "./client";
import type { DataMode, JobFunction } from "./topicE";

const JSON_HEADERS = { "Content-Type": "application/json" };

async function send<T>(path: string, method: string, body?: unknown): Promise<T> {
  return parse<T>(
    await authenticatedFetch(path, {
      method,
      headers: body === undefined ? undefined : JSON_HEADERS,
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
}

async function remove(path: string): Promise<void> {
  const response = await authenticatedFetch(path, { method: "DELETE" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(body.detail ?? `request_failed_${response.status}`, response.status, response.headers.get("X-Request-ID"));
  }
}

// ── Comments ────────────────────────────────────────────────────────────────

export interface ReviewComment {
  id: string;
  action_id: string;
  author_role: string;
  by_me: boolean;
  mentions: JobFunction[];
  /** Personal details arrive as placeholders such as ‹name›. */
  text: string;
  created_at: string;
}

export interface Mention {
  comment_id: string;
  action_id: string;
  author_role: string;
  mentions: JobFunction[];
  created_at: string;
}

export async function fetchComments(actionId: string): Promise<ReviewComment[]> {
  const body = await parse<{ comments: ReviewComment[] }>(await authenticatedFetch(`/review-inbox/${encodeURIComponent(actionId)}/comments`));
  return body.comments;
}

export function addComment(actionId: string, text: string, mentions: JobFunction[]): Promise<ReviewComment> {
  return send(`/review-inbox/${encodeURIComponent(actionId)}/comments`, "POST", { text, mentions });
}

export async function fetchMentions(): Promise<Mention[]> {
  const body = await parse<{ mentions: Mention[] }>(await authenticatedFetch("/mentions"));
  return body.mentions;
}

// ── Collections board ───────────────────────────────────────────────────────

export type BoardStage = "later" | "due_soon" | "overdue" | "on_hold" | "reminder" | "paid";
export type HoldKind = "disputed" | "promised" | "paused";

export interface HoldInfo {
  kind: HoldKind;
  until: string | null;
  /** "customer:7" when the customer is paused, else the invoice's own ref. */
  target: string;
}

export interface Hold extends HoldInfo {
  /** The invoice's label, or the customer's masked name for a paused customer. */
  label: string;
  customer_label: string;
  set_at: string;
  set_by_role: string;
}

export interface BoardCard {
  ref: string;
  label: string;
  customer_id: number | null;
  customer_label: string;
  amount: string;
  due_date: string | null;
  days_overdue: number;
  stage: BoardStage;
  reminder_action_id: string | null;
  hold: HoldInfo | null;
  promise_broken_on: string | null;
}

export interface BoardColumn {
  stage: BoardStage;
  total: string;
  cards: BoardCard[];
}

export interface CollectionsBoard {
  data_mode: DataMode;
  as_of: string;
  columns: BoardColumn[];
}

export async function fetchBoard(): Promise<CollectionsBoard> {
  return parse<CollectionsBoard>(await authenticatedFetch("/collections/board"));
}

export async function askForReminder(ref: string): Promise<string> {
  const body = await send<{ action_id: string }>(`/collections/${encodeURIComponent(ref)}/reminder`, "POST");
  return body.action_id;
}

export async function fetchHolds(): Promise<Hold[]> {
  const body = await parse<{ holds: Hold[] }>(await authenticatedFetch("/collections/holds"));
  return body.holds;
}

/** Dispute or promise for one invoice ref, or pause a "customer:<id>". */
export function setHold(target: string, kind: HoldKind, until: string | null = null): Promise<{ target: string }> {
  return send(`/collections/holds/${encodeURIComponent(target)}`, "PUT", { kind, until });
}

export function clearHold(target: string): Promise<void> {
  return remove(`/collections/holds/${encodeURIComponent(target)}`);
}

// ── Automations ─────────────────────────────────────────────────────────────

export type AutomationTrigger = "invoice_overdue_days" | "invoice_due_within_days" | "cash_shortfall_within_days" | "bill_due_within_days";
export type AutomationAction = "draft_reminder" | "reminder_sequence" | "ask_review";

export interface AutomationRequest {
  trigger: AutomationTrigger;
  days: number;
  action: AutomationAction;
  reviewer: JobFunction;
  enabled?: boolean;
}

export interface Automation extends AutomationRequest {
  id: string;
  enabled: boolean;
  created_at: string;
}

export async function fetchAutomations(): Promise<Automation[]> {
  const body = await parse<{ automations: Automation[] }>(await authenticatedFetch("/automations"));
  return body.automations;
}

export function saveAutomation(request: AutomationRequest): Promise<Automation> {
  return send("/automations", "POST", request);
}

export function removeAutomation(id: string): Promise<void> {
  return remove(`/automations/${encodeURIComponent(id)}`);
}

export async function runAutomations(): Promise<string[]> {
  const body = await send<{ proposals: string[] }>("/automations/run", "POST");
  return body.proposals;
}

export type SkipReason = "on_hold" | "waiting_for_decision" | "stopped_after_rejection";

export interface AutomationRun {
  at: string;
  proposed: string[];
  skipped: Partial<Record<SkipReason, number>>;
}

export async function fetchAutomationRuns(id: string): Promise<AutomationRun[]> {
  const body = await parse<{ runs: AutomationRun[] }>(await authenticatedFetch(`/automations/${encodeURIComponent(id)}/runs`));
  return body.runs;
}

// ── Saved views ─────────────────────────────────────────────────────────────

export type SavedViewScreen = "customers" | "collections";
export type Priority = "urgent" | "high" | "monitoring" | "healthy";

export interface SavedViewFilters {
  priorities: Priority[];
  min_overdue: string | null;
  min_outstanding: string | null;
  unconfirmed_only: boolean;
  stages: BoardStage[];
}

export interface SavedView {
  id: string;
  screen: SavedViewScreen;
  filters: SavedViewFilters;
  shared: boolean;
  mine: boolean;
  created_at: string;
}

export const NO_FILTERS: SavedViewFilters = { priorities: [], min_overdue: null, min_outstanding: null, unconfirmed_only: false, stages: [] };

export async function fetchSavedViews(screen: SavedViewScreen): Promise<SavedView[]> {
  const body = await parse<{ views: SavedView[] }>(await authenticatedFetch(`/saved-views?screen=${screen}`));
  return body.views;
}

export function saveView(screen: SavedViewScreen, filters: SavedViewFilters, shared: boolean): Promise<SavedView> {
  return send("/saved-views", "POST", { screen, filters, shared });
}

export function removeView(id: string): Promise<void> {
  return remove(`/saved-views/${encodeURIComponent(id)}`);
}

// ── Chat notifications ──────────────────────────────────────────────────────

export type ChatChannel = "slack" | "whatsapp";

export interface ChatChannelStatus {
  channel: ChatChannel;
  configured: boolean;
  enabled: boolean;
}

export async function fetchChatChannels(): Promise<ChatChannelStatus[]> {
  const body = await parse<{ channels: ChatChannelStatus[] }>(await authenticatedFetch("/notifications/channels"));
  return body.channels;
}

export async function testChatChannel(channel: ChatChannel): Promise<"sent" | "simulated" | "not_configured" | "failed"> {
  const body = await send<{ status: "sent" | "simulated" | "not_configured" | "failed" }>("/notifications/test", "POST", { channel });
  return body.status;
}

// ── API keys for AI tools (MCP) ─────────────────────────────────────────────

export const MCP_TOOLS = [
  "get_cash_forecast",
  "get_forecast_check",
  "get_review_inbox",
  "get_collections_board",
  "get_financing_matches",
] as const;
export type McpTool = (typeof MCP_TOOLS)[number];
export type KeyLifetime = 30 | 90 | 180 | 365;

export interface ApiKeyView {
  id: string;
  created_at: string;
  revoked: boolean;
  tools: McpTool[];
  expires_at: string;
  expired: boolean;
  last_used_at: string | null;
  recent_calls: { tool: McpTool; at: string }[];
}

export async function fetchApiKeys(): Promise<ApiKeyView[]> {
  const body = await parse<{ keys: ApiKeyView[] }>(await authenticatedFetch("/api-keys"));
  return body.keys;
}

export function createApiKey(tools: McpTool[], expiresInDays: KeyLifetime): Promise<{ key: ApiKeyView; secret: string }> {
  return send("/api-keys", "POST", { tools, expires_in_days: expiresInDays });
}

export function revokeApiKey(id: string): Promise<void> {
  return remove(`/api-keys/${encodeURIComponent(id)}`);
}
