/** Paths an outsider opens without signing in; they match the backend's share_path. */
export type SharedRoute =
  | { kind: "lender"; token: string }
  | { kind: "auditor"; token: string }
  | { kind: "verify" };

export function sharedRouteFor(pathname: string): SharedRoute | null {
  const lender = pathname.match(/^\/lender\/passports\/([^/]+)\/?$/);
  if (lender) return { kind: "lender", token: decodeURIComponent(lender[1]) };
  const auditor = pathname.match(/^\/auditor\/packs\/([^/]+)\/?$/);
  if (auditor) return { kind: "auditor", token: decodeURIComponent(auditor[1]) };
  if (/^\/verify\/?$/.test(pathname)) return { kind: "verify" };
  return null;
}
