// Serve a built dist/ with the response headers from vercel.json, the way Vercel does,
// so security scanners (OWASP ZAP in CI) test the headers that production sends.
// Usage: node scripts/serve-dist.mjs [dist] [port]
import { createServer } from "node:http";
import { existsSync, readFileSync, statSync } from "node:fs";
import { extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL("..", import.meta.url));
const dist = resolve(process.argv[2] ?? resolve(here, "dist"));
const port = Number(process.argv[3] ?? 4173);
const config = JSON.parse(readFileSync(resolve(here, "vercel.json"), "utf8"));
const rules = (config.headers ?? []).map((rule) => ({ pattern: new RegExp(`^${rule.source}$`), headers: rule.headers }));
const types = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
  ".png": "image/png", ".jpg": "image/jpeg", ".json": "application/json", ".woff2": "font/woff2",
  ".txt": "text/plain; charset=utf-8", ".xml": "application/xml",
};

createServer((request, response) => {
  const path = decodeURIComponent(new URL(request.url ?? "/", "http://localhost").pathname);
  for (const rule of rules) {
    if (rule.pattern.test(path)) for (const header of rule.headers) response.setHeader(header.key, header.value);
  }
  let file = resolve(dist, `.${path}`);
  if (!file.startsWith(dist + sep) || !existsSync(file) || statSync(file).isDirectory()) {
    file = resolve(dist, "index.html");
  }
  response.setHeader("Content-Type", types[extname(file)] ?? "application/octet-stream");
  response.end(readFileSync(file));
}).listen(port, () => console.log(`Serving ${dist} with production headers on port ${port}`));
