// Backend cookie sessions (Plan 2). The browser never holds provider tokens:
// the API sets an HttpOnly session cookie, and state-changing requests carry the
// CSRF token it hands back. Set VITE_AUTH_MODE=backend to use this flow; the
// default keeps the older direct Supabase sign-in until the backend is deployed.

import { trackedFetch } from "../lib/connectivity";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const authMode: "backend" | "supabase" =
  import.meta.env.VITE_AUTH_MODE === "backend" ? "backend" : "supabase";

export type SessionState =
  | "email_code_required"
  | "password_required"
  | "mfa_enrollment_required"
  | "mfa_required"
  | "company_setup_required"
  | "authenticated";

export interface SessionResponse {
  state: SessionState;
  csrf_token: string | null;
  user_id: string | null;
  tenant_id: string | null;
  role: "general_employee" | "finance_ops" | "owner_director" | "compliance" | null;
  job_functions: string[];
  aal: "aal1" | "aal2";
}

export interface TotpEnrollment {
  factor_id: string;
  qr_code: string;
  secret: string;
  uri: string;
}

export interface TotpFactor {
  id: string;
  status: string;
  type: string;
}

export class SessionError extends Error {
  constructor(public readonly code: string, public readonly status: number) {
    super(code);
    this.name = "SessionError";
  }
}

const MESSAGES: Record<string, string> = {
  auth_request_failed: "That didn't work. Check what you entered and try again.",
  auth_rate_limited: "Too many attempts. Wait a minute, then try again.",
  auth_provider_unavailable: "The sign-in service is unavailable right now. Please retry shortly.",
  supabase_auth_not_configured: "Sign-in is not configured on this server yet.",
  mfa_verification_failed: "That authenticator code didn't work. Codes change every 30 seconds — try the current one.",
  csrf_origin_denied: "This page's address is not allowed to sign in. Open DuitDuit from its usual address.",
  email_verification_required: "Check your email for the sign-in code.",
  session_expired: "Your session has ended. Please sign in again.",
  session_idle_timeout: "You were signed out after a period of inactivity.",
  session_revoked: "You were signed out. Please sign in again.",
  demo_not_available: "The demo company is not open on this server.",
  demo_not_provisioned: "The demo company is not set up on this server yet.",
  demo_account_locked: "The shared demo account can't change this. Every judge uses the same account.",
  demo_company_read_only: "Team changes are closed in the shared demo company.",
};

/** A sign-in or session error code in words a person can act on. */
export function sessionMessage(code: string, fallback = "Something went wrong. Please try again."): string {
  return MESSAGES[code] ?? fallback;
}

let csrfToken: string | null = null;

export function currentCsrfToken(): string | null {
  return csrfToken;
}

/** Fetch with the session cookie and, for state changes, the CSRF header. */
export async function sessionFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD" && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  return trackedFetch(`${BASE_URL}${path}`, { ...init, headers, credentials: "include" });
}

async function call<T>(path: string, method: "GET" | "POST", body?: unknown): Promise<T> {
  const response = await sessionFetch(path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? (data.detail[0]?.msg ?? "invalid_request") : data.detail;
    throw new SessionError(typeof detail === "string" ? detail : `request_failed_${response.status}`, response.status);
  }
  if (data && typeof data === "object" && "csrf_token" in data && data.csrf_token) csrfToken = data.csrf_token;
  return data as T;
}

/** The current session, or null when nobody is signed in. */
export async function getSession(): Promise<SessionResponse | null> {
  try {
    return await call<SessionResponse>("/auth/session", "GET");
  } catch (error) {
    if (error instanceof SessionError && (error.status === 401 || error.status === 403)) return null;
    throw error;
  }
}

export const signInWithPassword = (email: string, password: string) =>
  call<SessionResponse>("/auth/sign-in", "POST", { email, password });
export const signUpWithPassword = (email: string, password: string) =>
  call<SessionResponse>("/auth/sign-up", "POST", { email, password });
export const startRecovery = (email: string) => call<SessionResponse>("/auth/recovery", "POST", { email });
export const startInvitation = (email: string) => call<SessionResponse>("/auth/invitation", "POST", { email });
export const verifyEmailCode = (code: string) => call<SessionResponse>("/auth/email/verify", "POST", { code });
export const setPassword = (password: string) => call<SessionResponse>("/auth/password", "POST", { password });
export const setupCompany = (companyName: string, slug: string) =>
  call<SessionResponse>("/auth/company", "POST", { company_name: companyName, slug });
export const listFactors = async () => (await call<{ factors: TotpFactor[] }>("/auth/mfa/factors", "GET")).factors;
export const enrollTotp = () => call<TotpEnrollment>("/auth/mfa/enroll", "POST");
export const challengeTotp = async (factorId: string) =>
  (await call<{ challenge_id: string }>(`/auth/mfa/${encodeURIComponent(factorId)}/challenge`, "POST")).challenge_id;
export const verifyTotp = (factorId: string, challengeId: string, code: string) =>
  call<SessionResponse>("/auth/mfa/verify", "POST", { factor_id: factorId, challenge_id: challengeId, code });
// The shared demo company (backend/app/auth/demo.py): the server runs the real
// password and authenticator steps with secrets only it holds.
export async function demoAvailable(): Promise<boolean> {
  try {
    return (await call<{ available: boolean }>("/auth/demo/status", "GET")).available;
  } catch {
    return false;
  }
}
export const demoSignIn = () => call<SessionResponse>("/auth/demo", "POST");
/** The demo account's current authenticator code; null for every other account. */
export async function fetchDemoCode(): Promise<{ code: string; seconds_left: number } | null> {
  try {
    return await call<{ code: string; seconds_left: number }>("/auth/demo/code", "GET");
  } catch {
    return null;
  }
}
export const fetchMe = () => call<{ user_id: string; email: string | null; role: SessionResponse["role"] }>("/auth/me", "GET");

export async function signOutSession(): Promise<void> {
  await sessionFetch("/auth/sign-out", { method: "POST" }).catch(() => undefined);
  csrfToken = null;
}

// ── Step-up ────────────────────────────────────────────────────────────────
// Sensitive operations answer 403 step_up_required when the last authenticator
// check is older than five minutes. The app registers a handler that asks for a
// fresh code; the request is then retried once.

type StepUpHandler = () => Promise<boolean>;
let stepUpHandler: StepUpHandler | null = null;
let pendingStepUp: Promise<boolean> | null = null;

export function registerStepUpHandler(handler: StepUpHandler | null): void {
  stepUpHandler = handler;
}

export async function requestStepUp(): Promise<boolean> {
  if (!stepUpHandler) return false;
  // Several requests failing at once share one prompt.
  pendingStepUp ??= stepUpHandler().finally(() => { pendingStepUp = null; });
  return pendingStepUp;
}

export async function isStepUpRequired(response: Response): Promise<boolean> {
  if (response.status !== 403) return false;
  const body = await response.clone().json().catch(() => ({}));
  return body.detail === "step_up_required";
}
