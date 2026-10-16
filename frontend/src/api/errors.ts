// What to tell a person when a request fails: what happened and what to do next.
// Only short codes are ever shown (never free text), so support can tell which
// check refused the request.

export function isNetworkError(message: string): boolean {
  return /failed to fetch|networkerror|load failed|network request failed|request_failed_50[234]/i.test(message);
}

const SERVER_ERROR = /^(internal server error|request_failed_500|server_error)$/i;

function codeSuffix(message: string): string {
  return /^[a-z0-9_]{1,40}$/.test(message) ? ` (code: ${message})` : "";
}

/** A message we know, or null when the code is unknown. */
function known(message: string): string | null {
  // Internal plumbing codes (thrown by accessToken() when there's no session)
  // leak straight into `Error.message`; translate the ones we know about
  // instead of showing a snake_case string on an initial page load.
  if (message === "authentication_required") return "Your session has expired — please log in again.";
  if (message === "insufficient_role") return "Your role doesn't have access to this data.";
  if (message === "step_up_required") return "This needs a fresh code from your authenticator app. Try again and enter the code.";
  if (message === "csrf_token_invalid" || message === "csrf_origin_denied") return "Your session needs refreshing. Reload the page and try again.";
  if (message === "session_expired" || message === "session_idle_timeout" || message === "session_revoked") return "Your session has ended — please sign in again.";
  if (isNetworkError(message)) return "DuitDuit can't reach its server right now. Your data is safe. Try again in a moment.";
  if (message === "demo_account_locked" || message === "demo_company_read_only") {
    return "The shared demo company can't change its team, password or sign-ins, so other visitors aren't affected. Try this in your own company.";
  }
  if (message === "http_504" || message === "request_failed_504") return "That took too long and the connection closed. Try again: it is usually faster the second time.";
  if (message === "rate_limited" || message === "auth_rate_limited") return "Too many requests in a short time. Wait a minute, then try again.";
  if (message === "request_failed_404" || message === "not_found") return "This item no longer exists, or has moved. Reload the page to see the latest.";
  if (message === "request_failed_409") return "Someone changed this at the same time. Reload the page to see the latest.";
  return null;
}

/** For a screen or list that failed to load. */
export function friendlyLoadError(message: string): string {
  const text = known(message);
  if (text) return text;
  if (SERVER_ERROR.test(message)) return "Something went wrong on DuitDuit's server. Your data is safe. Try again, or reload the page.";
  return `Couldn't load this page right now. Try again, or reload the page.${codeSuffix(message)}`;
}

/** For a button that failed: approving, rejecting, commenting, saving. */
export function friendlyActionError(message: string): string {
  const text = known(message);
  if (text) return text;
  if (SERVER_ERROR.test(message)) return "That didn't go through, and nothing was changed. Something went wrong on DuitDuit's server; try again in a moment.";
  return `That didn't go through, and nothing was changed. Try again.${codeSuffix(message)}`;
}
