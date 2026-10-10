// Whether the API answered the last request. The banner in components/ServerStatusBanner
// listens, so a judge or owner sees one clear sentence instead of a blank page when the
// server (or the tunnel or proxy in front of it) is down.

type Listener = (reachable: boolean) => void;

let reachable = true;
const listeners = new Set<Listener>();

function set(next: boolean) {
  if (next === reachable) return;
  reachable = next;
  for (const listener of listeners) listener(reachable);
}

export function serverReachable(): boolean {
  return reachable;
}

export function onServerReachability(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** A gateway status means the proxy answered but the API behind it did not. */
const GATEWAY = new Set([502, 503, 504]);

/** fetch, recording whether the API was reachable. Errors are passed on unchanged. */
export async function trackedFetch(input: string, init?: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(input, init);
  } catch (error) {
    set(false);
    throw error;
  }
  set(!GATEWAY.has(response.status));
  return response;
}

/** True for the browser's own "could not connect" errors. */
export function isNetworkError(message: string): boolean {
  return /failed to fetch|networkerror|load failed|network request failed|request_failed_50[234]/i.test(message);
}
