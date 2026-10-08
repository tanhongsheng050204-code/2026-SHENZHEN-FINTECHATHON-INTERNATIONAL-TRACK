// Same-origin API proxy for Vercel (Edge runtime).
//
// The browser calls https://<app>/api/... ; vercel.json rewrites that to
// /api/proxy?__fbpath=..., and this function forwards it to the backend named by
// BACKEND_ORIGIN (e.g. https://finbrain-api-xxxxx.a.run.app). Because the app
// and the API now share one origin, the backend's HttpOnly session cookie is a
// first-party cookie and the browser sends it. Responses are streamed, so
// server-sent agent-run events arrive as they happen.

export const config = { runtime: "edge" };

// Headers that describe this hop, not the request itself.
const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "proxy-authorization",
  "proxy-authenticate",
  "te",
  "trailer",
  "host",
  "content-length",
]);
// fetch() decodes compressed bodies, so these would describe the wrong bytes.
const STALE_RESPONSE_HEADERS = new Set(["content-encoding", "content-length", "transfer-encoding", "connection"]);
// Only plain path segments: no scheme, host, "..", percent-escapes or backslashes.
const SAFE_PATH = /^[A-Za-z0-9._~\-/]*$/;

export function backendUrl(requestUrl, backendOrigin) {
  const url = new URL(requestUrl);
  const path = url.searchParams.get("__fbpath") ?? "";
  if (!SAFE_PATH.test(path) || path.split("/").some((segment) => segment === ".." || segment === ".")) {
    return null;
  }
  url.searchParams.delete("__fbpath");
  const target = new URL(backendOrigin);
  target.pathname = `${target.pathname.replace(/\/$/, "")}/${path.replace(/^\/+/, "")}`;
  target.search = url.searchParams.toString();
  return target;
}

export default async function handler(request) {
  const origin = globalThis.process?.env?.BACKEND_ORIGIN;
  if (!origin) {
    return Response.json({ detail: "backend_not_configured" }, { status: 503 });
  }
  const target = backendUrl(request.url, origin);
  if (!target) {
    return Response.json({ detail: "invalid_path" }, { status: 400 });
  }

  const headers = new Headers();
  for (const [name, value] of request.headers) {
    if (!HOP_BY_HOP.has(name.toLowerCase())) headers.set(name, value);
  }
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) headers.set("x-forwarded-for", forwardedFor);
  headers.set("x-forwarded-host", new URL(request.url).host);
  headers.set("x-forwarded-proto", "https");

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  let upstream;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      // Required by fetch when streaming a request body.
      duplex: hasBody ? "half" : undefined,
      redirect: "manual",
    });
  } catch {
    return Response.json({ detail: "backend_unreachable" }, { status: 502 });
  }

  const responseHeaders = new Headers();
  for (const [name, value] of upstream.headers) {
    const lower = name.toLowerCase();
    if (STALE_RESPONSE_HEADERS.has(lower) || lower === "set-cookie") continue;
    responseHeaders.set(name, value);
  }
  // Each session cookie must stay a separate header.
  for (const cookie of upstream.headers.getSetCookie?.() ?? []) {
    responseHeaders.append("set-cookie", cookie);
  }
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
