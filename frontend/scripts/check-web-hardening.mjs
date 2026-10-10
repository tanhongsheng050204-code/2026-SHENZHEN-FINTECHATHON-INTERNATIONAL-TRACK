// CI guard for Plan 9: the security headers stay in vercel.json, and nothing in the
// app loads from a third-party origin (blocked or unreliable from mainland China).
// Usage, from frontend/: node scripts/check-web-hardening.mjs  (after npm run build)
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { microphoneIsSelfOnly } from "./permissions-policy.mjs";

const failures = [];
const config = JSON.parse(readFileSync("vercel.json", "utf8"));
const all = (config.headers ?? []).find((rule) => rule.source === "/(.*)");
const headers = Object.fromEntries((all?.headers ?? []).map((h) => [h.key.toLowerCase(), h.value]));

const required = {
  "content-security-policy": ["default-src 'self'", "script-src 'self'", "frame-ancestors 'none'", "object-src 'none'"],
  "strict-transport-security": ["max-age="],
  "x-content-type-options": ["nosniff"],
  "referrer-policy": ["strict-origin"],
  "permissions-policy": ["camera=()", "microphone=(self)"],
  // Cross-origin isolation, added after the OWASP ZAP baseline scan flagged it.
  "cross-origin-opener-policy": ["same-origin"],
  "cross-origin-resource-policy": ["same-origin"],
  "cross-origin-embedder-policy": ["require-corp"],
};
for (const [name, parts] of Object.entries(required)) {
  for (const part of parts) {
    if (!headers[name]?.includes(part)) failures.push(`vercel.json: ${name} must include ${part}`);
  }
}
for (const rule of config.headers ?? []) {
  for (const header of rule.headers ?? []) {
    if (header.key.toLowerCase() === "permissions-policy" && !microphoneIsSelfOnly(header.value)) {
      failures.push("vercel.json: microphone must allow self only, with no wildcard or other origin");
    }
  }
}
if (/script-src[^;]*'unsafe-(inline|eval)'/.test(headers["content-security-policy"] ?? "")) {
  failures.push("vercel.json: script-src must not allow unsafe-inline or unsafe-eval");
}
if (!(config.headers ?? []).some((rule) => rule.headers.some((h) => h.key === "X-Robots-Tag"))) {
  failures.push("vercel.json: app routes need X-Robots-Tag: noindex");
}
for (const file of ["public/.well-known/security.txt", "public/robots.txt", "public/sitemap.xml"]) {
  if (!existsSync(file)) failures.push(`missing ${file}`);
}

// Resources the browser would fetch from elsewhere: src/href/url() pointing off-site.
const LOADS = /(?:src|href)\s*=\s*["'`](https?:\/\/[^"'`]+)|url\(\s*["']?(https?:\/\/[^"')]+)|@import\s+["'](https?:\/\/[^"']+)/g;
function scan(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) scan(path);
    else if (/\.(tsx?|css|html)$/.test(entry.name)) {
      for (const match of readFileSync(path, "utf8").matchAll(LOADS)) {
        failures.push(`${path}: loads ${match[1] ?? match[2] ?? match[3]}`);
      }
    }
  }
}
scan("src");
scan("public");
for (const match of readFileSync("index.html", "utf8").matchAll(LOADS)) {
  if (!/^https:\/\/finbrainos\.vercel\.app\//.test(match[1] ?? "")) {
    failures.push(`index.html: loads ${match[1] ?? match[2] ?? match[3]}`);
  }
}

if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log("Web hardening checks passed.");
