import { useCallback, useEffect, useState } from "react";
import { createApiKey, fetchApiKeys, MCP_TOOLS, revokeApiKey, type ApiKeyView, type KeyLifetime, type McpTool } from "../api/collaboration";
import { ApiError, friendlyLoadError } from "../api/client";
import { useI18n } from "../lib/i18n";
import { RecordPanel } from "./RecordPanel";
import "./records.css";

const TOOL_LABEL: Record<McpTool, string> = {
  get_cash_forecast: "Cash forecast",
  get_forecast_check: "Forecast check",
  get_review_inbox: "Review inbox",
  get_collections_board: "Collections board",
  get_financing_matches: "Financing matches",
};
const LIFETIMES: KeyLifetime[] = [30, 90, 180, 365];

function day(iso: string): string {
  return new Date(iso).toLocaleDateString("en-MY", { day: "numeric", month: "short", year: "numeric" });
}

function moment(iso: string): string {
  return new Date(iso).toLocaleString("en-MY", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function status(key: ApiKeyView): [string, string] {
  if (key.revoked) return ["", "Revoked"];
  if (key.expired) return ["is-red", "Expired"];
  return ["is-green", "Active"];
}

/** One key as a record: what it may read, until when, and what it read lately. */
function KeyPanel({ apiKey, onClose, onRevoke }: { apiKey: ApiKeyView; onClose: () => void; onRevoke: (id: string) => void }) {
  const { tx } = useI18n();
  const [tone, label] = status(apiKey);
  return (
    <RecordPanel kicker={tx("AI connection key")} title={`ddk_${apiKey.id}_…`} onClose={onClose}>
      <section className="rc-section">
        <h3>{tx("Details")}</h3>
        <dl className="rc-attrs">
          <dt>{tx("Status")}</dt><dd><span className={"rc-chip " + tone}>{tx(label)}</span></dd>
          <dt>{tx("Created")}</dt><dd>{day(apiKey.created_at)}</dd>
          <dt>{tx("Expires")}</dt><dd>{day(apiKey.expires_at)}</dd>
          <dt>{tx("Last used")}</dt><dd>{apiKey.last_used_at ? moment(apiKey.last_used_at) : tx("Never")}</dd>
          <dt>{tx("Can read")}</dt><dd><div className="rc-chips">{apiKey.tools.map((t) => <span key={t} className="rc-chip is-plain">{tx(TOOL_LABEL[t])}</span>)}</div></dd>
        </dl>
      </section>
      <section className="rc-section">
        <h3>{tx("Recent calls")}</h3>
        <ul className="rc-list">
          {apiKey.recent_calls.length === 0 && <li className="rc-list-empty">{tx("No calls yet.")}</li>}
          {apiKey.recent_calls.map((call) => (
            <li key={call.at + call.tool}>
              <div className="rc-list-main"><strong>{tx(TOOL_LABEL[call.tool] ?? call.tool)}</strong><span>{moment(call.at)}</span></div>
            </li>
          ))}
        </ul>
      </section>
      {!apiKey.revoked && (
        <div className="rc-actions">
          <button type="button" className="rc-action" onClick={() => onRevoke(apiKey.id)}>{tx("Revoke this key")}<small>{tx("The AI tool loses access at once")}</small></button>
        </div>
      )}
      <p className="rc-note">{tx("Every call is recorded on the audit trail by tool name and key id only.")}</p>
    </RecordPanel>
  );
}

/**
 * Connect an AI tool such as Claude to DuitDuit over MCP. A key reads only the
 * tools the owner chose, with masked labels, until it expires; every change still
 * goes through the review inbox.
 */
export function AiConnectionsPanel({ isOwner }: { isOwner: boolean }) {
  const { tx } = useI18n();
  const [keys, setKeys] = useState<ApiKeyView[]>([]);
  const [secret, setSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tools, setTools] = useState<McpTool[]>([...MCP_TOOLS]);
  const [lifetime, setLifetime] = useState<KeyLifetime>(90);
  const [openId, setOpenId] = useState<string | null>(null);
  const closeKey = useCallback(() => setOpenId(null), []);
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
      const made = await createApiKey(tools, lifetime);
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

  const toggle = (tool: McpTool) => setTools((list) => (list.includes(tool) ? list.filter((t) => t !== tool) : [...list, tool]));
  const opened = keys.find((k) => k.id === openId) ?? null;
  const claudeCode = `claude mcp add --transport http duitduit ${endpoint} --header "Authorization: Bearer ${secret ?? "<your key>"}"`;
  const generic = JSON.stringify({ mcpServers: { duitduit: { type: "streamableHttp", url: endpoint, headers: { Authorization: `Bearer ${secret ?? "<your key>"}` } } } }, null, 2);
  const desktop = JSON.stringify({ mcpServers: { duitduit: { command: "npx", args: ["mcp-remote", endpoint, "--header", `Authorization: Bearer ${secret ?? "<your key>"}`] } } }, null, 2);

  return (
    <section className="fb-cash-card">
      <h2>{tx("AI connections")}</h2>
      <p className="fb-inbox-muted">{tx("Let Claude or another AI tool answer from DuitDuit through MCP. A key only reads the tools you choose, with masked labels, until it expires. It cannot approve, send or change anything, and every call is recorded on the audit trail.")}</p>
      {!isOwner && <p className="fb-inbox-muted">{tx("Only the owner can create or revoke keys.")}</p>}
      {isOwner && (
        <>
          <ul className="rc-list">
            {keys.length === 0 && <li className="rc-list-empty">{tx("No keys yet.")}</li>}
            {keys.map((k) => {
              const [tone, label] = status(k);
              return (
                <li key={k.id}>
                  <div className="rc-list-main">
                    <strong><code>ddk_{k.id}_…</code></strong>
                    <span>
                      <span className={"rc-chip " + tone}>{tx(label)}</span>{" "}
                      {tx("{n} of 5 tools", { n: k.tools.length })} · {tx("expires {date}", { date: day(k.expires_at) })} · {k.last_used_at ? tx("last used {when}", { when: moment(k.last_used_at) }) : tx("never used")}
                    </span>
                  </div>
                  <button type="button" className="rc-mini" onClick={() => setOpenId(k.id)}>{tx("Details")}</button>
                </li>
              );
            })}
          </ul>
          <fieldset className="dd-key-form">
            <legend>{tx("New key")}</legend>
            <div className="rc-chips" role="group" aria-label={tx("Tools this key may read")}>
              {MCP_TOOLS.map((tool) => (
                <label key={tool} className={"dd-key-tool" + (tools.includes(tool) ? " is-on" : "")}>
                  <input type="checkbox" checked={tools.includes(tool)} onChange={() => toggle(tool)} />
                  {tx(TOOL_LABEL[tool])}
                </label>
              ))}
            </div>
            <label className="fb-cash-field">
              <span>{tx("Expires after")}</span>
              <select value={lifetime} onChange={(e) => setLifetime(Number(e.target.value) as KeyLifetime)}>
                {LIFETIMES.map((d) => <option key={d} value={d}>{tx("{n} days", { n: d })}</option>)}
              </select>
            </label>
            <button type="button" className="fb-btn fb-btn-solid" disabled={tools.length === 0} onClick={() => void create()}>{tx("Create a key")}</button>
            {tools.length === 0 && <span className="fb-inbox-muted">{tx("Choose at least one tool.")}</span>}
          </fieldset>
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
      {opened && <KeyPanel key={opened.id} apiKey={opened} onClose={closeKey} onRevoke={(id) => void revoke(id)} />}
    </section>
  );
}
