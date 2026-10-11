import { useEffect, useState } from "react";
import { fetchChatChannels, testChatChannel, type ChatChannel, type ChatChannelStatus } from "../api/collaboration";
import { ApiError, friendlyLoadError } from "../api/client";
import { useI18n } from "../lib/i18n";

const NAMES: Record<ChatChannel, string> = { slack: "Slack", whatsapp: "WhatsApp" };
const OUTCOME: Record<string, string> = {
  sent: "Sent. Check the channel.",
  simulated: "Recorded as simulated: the demo company never sends.",
  not_configured: "Not set up on the server yet.",
  failed: "The channel refused the message. Check the settings on the server.",
};

/**
 * Team chat messages when items wait for review. They say only how many items
 * wait and for which positions, with a link: no titles, amounts or names.
 */
export function ChatNotificationsPanel({ isOwner }: { isOwner: boolean }) {
  const { tx } = useI18n();
  const [channels, setChannels] = useState<ChatChannelStatus[]>([]);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchChatChannels().then((c) => active && setChannels(c)).catch((e) => active && setError(friendlyLoadError(e instanceof ApiError ? e.code : "")));
    return () => { active = false; };
  }, []);

  const test = async (channel: ChatChannel) => {
    setOutcome(null);
    setError(null);
    try {
      setOutcome(`${NAMES[channel]}: ${tx(OUTCOME[await testChatChannel(channel)])}`);
    } catch (e) {
      setError(friendlyLoadError(e instanceof ApiError ? e.code : ""));
    }
  };

  return (
    <section className="fb-cash-card">
      <h2>{tx("Team chat notifications")}</h2>
      <p className="fb-inbox-muted">{tx("When the number of items waiting for review changes, DuitDuit posts one line to your team chat, for example: “3 items wait for review (Finance 2, Owner 1)”, with a link to the review inbox. It never includes titles, amounts or names, and decisions still happen in DuitDuit.")}</p>
      <ul className="fb-fin-items">
        {channels.map((c) => (
          <li key={c.channel}>
            <span>
              <strong>{NAMES[c.channel]}</strong><br />
              <span className="fb-inbox-muted">
                {c.configured ? (c.enabled ? tx("Set up and on") : tx("Set up, switched off")) : tx("Not set up")}
              </span>
            </span>
            {isOwner && c.configured && (
              <button type="button" className="fb-btn fb-btn-outline fb-fin-revoke" onClick={() => void test(c.channel)}>{tx("Send a test")}</button>
            )}
          </li>
        ))}
      </ul>
      <p className="fb-inbox-muted">{tx("The server operator sets these up: a Slack incoming webhook, or a WhatsApp Business account with an approved message template. WhatsApp has not been tested with a live account yet.")}</p>
      {outcome && <p className="fb-inbox-muted" role="status">{outcome}</p>}
      {error && <div className="fb-inbox-error" role="alert">{error}</div>}
    </section>
  );
}
