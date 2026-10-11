import { useEffect, useState } from "react";
import { createApiKey, fetchApiKeys, revokeApiKey, type ApiKeyView } from "../api/collaboration";
import { ApiError, friendlyLoadError } from "../api/client";
import { useI18n } from "../lib/i18n";

function when(iso: string): string {
  return new Date(iso).toLocaleDateString("en-MY", { day: "numeric", month: "short", year: "numeric" });
}

/**
 * Connect an AI tool such as Claude to DuitDuit over MCP. A key reads only: the
 * tool can see the forecast, inbox, collections and financing matches, with
 * masked labels, and every change still goes through the review inbox.
 */
export function AiConnectionsPanel({ isOwner }: { isOwner: boolean }) {
  const { tx } = useI18n();
  const [keys, setKeys] = useState<ApiKeyView[]>([]);
  const [secret, setSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const endpoint = `${window.location.origin}/api/mcp`;

  useEffect(() => {
    if (!isOwner) return;
    let active = true;
    fetchApiKeys().then((k) => active && setKeys(k)).catch((e) => active && setError(friendlyLoadError(e instanceof ApiError ? e.code : "")));
    return () => { active = false; };
  }, [isOwner]);

  const create = async () => {
    setError(null);
    try {
      const made = await createApiKey();
      setKeys((list) => [...list, made.key]);
      setSecret(made.secret);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "";
      setError(code === "too_many_api_keys" ? tx("A company can have at most 5 active keys. Revoke one first.") : friendlyLoadError(code));
    }
  };

  const revoke = async (id: string) => {
    setError(null);
    try {
      await revokeApiKey(id);
      setKeys((list) => list.map((k) => (k.id === id ? { ...k, revoked: true } : k)));
    } catch (e) {
      setError(friendlyLoadError(e instanceof ApiError ? e.code : ""));
    }
  };

  const claudeCode = `claude mcp add --transport http duitduit ${endpoint} --header "Authorization: Bearer ${secret ?? "<your key>"}"`;
  const generic = JSON.stringify({ mcpServers: { duitduit: { type: "streamableHttp", url: endpoint, headers: { Authorization: `Bearer ${secret ?? "<your key>"}` } } } }, null, 2);
  const desktop = JSON.stringify({ mcpServers: { duitduit: { command: "npx", args: ["mcp-remote", endpoint, "--header", `Authorization: Bearer ${secret ?? "<your key>"}`] } } }, null, 2);

  return (
    <section className="fb-cash-card">
      <h2>{tx("AI connections")}</h2>
      <p className="fb-inbox-muted">{tx("Let Claude or another AI tool answer from DuitDuit through MCP. A key only reads: the forecast, the forecast check, the review inbox, the collections board and financing matches, with masked labels. It cannot approve, send or change anything, and every call is recorded on the audit trail.")}</p>
      {!isOwner && <p className="fb-inbox-muted">{tx("Only the owner can create or revoke keys.")}</p>}
      {isOwner && (
        <>
          <ul className="fb-fin-items">
            {keys.length === 0 && <li><span className="fb-inbox-muted">{tx("No keys yet.")}</span></li>}
            {keys.map((k) => (
              <li key={k.id}>
                <span><strong><code>ddk_{k.id}_…</code></strong><br /><span className="fb-inbox-muted">{tx("Created {date}", { date: when(k.created_at) })}{k.revoked ? ` · ${tx("Revoked")}` : ""}</span></span>
                {!k.revoked && <button type="button" className="fb-btn fb-btn-outline fb-fin-revoke" onClick={() => void revoke(k.id)}>{tx("Revoke")}</button>}
              </li>
            ))}
          </ul>
          <button type="button" className="fb-btn fb-btn-solid" onClick={() => void create()}>{tx("Create a key")}</button>
          {secret && (
            <div className="fb-fin-done" role="status">
              <strong>{tx("Copy this key now. It is shown only once.")}</strong>
              <pre className="dd-code">{secret}</pre>
              <div className="fb-inbox-label">{tx("Claude Code")}</div>
              <pre className="dd-code">{claudeCode}</pre>
              <div className="fb-inbox-label">{tx("Claude Desktop (claude_desktop_config.json)")}</div>
              <pre className="dd-code">{desktop}</pre>
              <div className="fb-inbox-label">{tx("Chinese AI tools and other MCP clients")}</div>
              <pre className="dd-code">{generic}</pre>
              <button type="button" className="fb-btn fb-btn-outline" onClick={() => setSecret(null)}>{tx("I have saved it")}</button>
            </div>
          )}
          <p className="fb-inbox-muted">{tx("Server address")}: <code>{endpoint}</code></p>
          <div className="dd-ai-clients">
            <div className="fb-inbox-label">{tx("Works with Chinese AI tools")}</div>
            <p className="fb-inbox-muted">{tx("Any client that supports MCP over Streamable HTTP can connect: for example Cherry Studio with DeepSeek, Qwen (通义千问) or Kimi models, ByteDance's Trae, or an agent built on Alibaba Cloud Model Studio (百炼). Add a server with transport Streamable HTTP, the server address above, and the header Authorization: Bearer <your key>. The tools describe themselves in English and Chinese, so the model can answer in Chinese. We have not yet tested each of these clients.")}</p>
            <p className="fb-inbox-muted">{tx("From mainland China, the server address must use a domain reachable there; vercel.app often is not.")}</p>
          </div>
        </>
      )}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
    </section>
  );
}
