import { useEffect, useState } from "react";
import { friendlyLoadError } from "../api/client";
import {
  errorCode,
  fetchBriefingPreference,
  saveBriefingPreference,
  sendBriefingNow,
  type BriefingPreference,
} from "../api/topicE";

/**
 * Opt in to DuitDuit's morning briefing by email and/or Telegram. Off until the
 * person turns it on; pushed briefings carry ranges and counts, never exact
 * amounts or names, because a message can be forwarded.
 */
export function BriefingPushCard({ email }: { email: string }) {
  const [saved, setSaved] = useState<BriefingPreference | null>(null);
  const [wantEmail, setWantEmail] = useState(false);
  const [wantTelegram, setWantTelegram] = useState(false);
  const [chatId, setChatId] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchBriefingPreference()
      .then((p) => {
        if (!active) return;
        setSaved(p);
        setWantEmail(p.email);
        setWantTelegram(p.telegram);
      })
      .catch((e) => active && setNote(friendlyLoadError(errorCode(e))));
    return () => { active = false; };
  }, []);

  const telegramValid = !wantTelegram || /^\d{5,15}$/.test(chatId) || (saved?.telegram && chatId === "");

  const save = async () => {
    setBusy(true);
    setNote(null);
    try {
      const keepExisting = wantTelegram && chatId === "" && saved?.telegram;
      if (keepExisting) {
        setNote("To change Telegram, enter your Telegram ID again.");
        return;
      }
      const result = await saveBriefingPreference(wantEmail, wantTelegram ? chatId : null);
      setSaved(result);
      setChatId("");
      setNote(result.email || result.telegram ? "Saved. Your briefing arrives each morning at 8am." : "Saved. Pushed briefings are off.");
    } catch (e) {
      setNote(friendlyLoadError(errorCode(e)));
    } finally {
      setBusy(false);
    }
  };

  const testNow = async () => {
    setBusy(true);
    setNote(null);
    try {
      const { sent } = await sendBriefingNow();
      setNote(sent.length ? `Sent by ${sent.join(" and ")}.` : "Nothing sent: turn on a channel and save first, or check that email/Telegram is set up.");
    } catch (e) {
      setNote(friendlyLoadError(errorCode(e)));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="fb-settings-section">
      <h2>Morning briefing</h2>
      <div className="fb-settings-card fb-briefing-push">
        <p className="fb-inbox-muted">DuitDuit can send you what needs you each morning. It only says ranges and counts, never exact amounts or names; sign in for the details.</p>
        <label className="fb-briefing-push-row">
          <input type="checkbox" checked={wantEmail} onChange={(e) => setWantEmail(e.target.checked)} />
          <span>Email to <strong>{email}</strong></span>
        </label>
        <label className="fb-briefing-push-row">
          <input type="checkbox" checked={wantTelegram} onChange={(e) => setWantTelegram(e.target.checked)} />
          <span>Telegram{saved?.telegram ? " (connected)" : ""}</span>
        </label>
        {wantTelegram && (
          <label className="fb-cash-field">
            <span>Your Telegram ID (send /start to the DuitDuit bot to see it)</span>
            <input inputMode="numeric" value={chatId} placeholder={saved?.telegram ? "Leave empty to keep the current one" : "e.g. 123456789"} onChange={(e) => setChatId(e.target.value.replace(/\D/g, ""))} />
          </label>
        )}
        <div className="fb-assistant-actions">
          <button type="button" className="fb-btn fb-btn-solid" disabled={busy || !telegramValid} onClick={() => void save()}>Save</button>
          <button type="button" className="fb-btn fb-btn-outline" disabled={busy || !(saved?.email || saved?.telegram)} onClick={() => void testNow()}>Send me one now</button>
        </div>
        {note && <p className="fb-inbox-muted" role="status">{note}</p>}
      </div>
    </section>
  );
}
