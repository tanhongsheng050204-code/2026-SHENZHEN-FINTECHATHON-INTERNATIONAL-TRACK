import { useEffect, useState } from "react";
import { fetchEmailStatus, fetchTelegramStatus } from "../api/client";
import { useAppState } from "../lib/appState";
import "./ConnectionsBoard.css";

// Every way data reaches DuitDuit, as integration tiles with their real state. The
// live connectors report their own health; file imports and e-invoices say plainly
// what they are.

type Tone = "ok" | "warn" | "off" | "neutral";
type Tile = { id: string; name: string; what: string; state: string; tone: Tone; go: () => void; glyph: string };

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function telegramState(status: string | null): [string, Tone] {
  if (status === null) return ["Checking…", "neutral"];
  if (status === "healthy") return ["Connected", "ok"];
  if (status === "not_configured") return ["Not set up", "off"];
  if (status === "starting") return ["Starting", "neutral"];
  if (status === "unreachable") return ["Status unavailable", "neutral"];
  return ["Needs attention", "warn"];
}

function emailState(configured: boolean | null, status: string | null, failure: string | null): [string, Tone] {
  if (configured === null) return ["Checking…", "neutral"];
  if (status === "unreachable") return ["Status unavailable", "neutral"];
  if (!configured) return ["Not set up", "off"];
  if (failure) return ["Needs attention", "warn"];
  return ["Connected", "ok"];
}

export function ConnectionsBoard() {
  const { show } = useAppState();
  const [telegram, setTelegram] = useState<string | null>(null);
  const [email, setEmail] = useState<{ configured: boolean | null; status: string | null; failure: string | null }>({ configured: null, status: null, failure: null });

  useEffect(() => {
    let active = true;
    fetchTelegramStatus()
      .then((s) => active && setTelegram(s.status))
      .catch(() => active && setTelegram("unreachable"));
    fetchEmailStatus()
      .then((s) => active && setEmail({ configured: s.configured, status: s.status, failure: s.failure_code }))
      .catch(() => active && setEmail({ configured: false, status: "unreachable", failure: null }));
    return () => { active = false; };
  }, []);

  const [tgLabel, tgTone] = telegramState(telegram);
  const [mailLabel, mailTone] = emailState(email.configured, email.status, email.failure);

  const tiles: Tile[] = [
    { id: "telegram", name: "Telegram", what: "Send a receipt or note to the bot; it arrives here protected", state: tgLabel, tone: tgTone, go: () => scrollTo("telegram-capture-title"), glyph: "M21 4L3 11l6 2 2 6 3-4 5 4z" },
    { id: "gmail", name: "Gmail", what: "Reads the inbox you connect; sends only what you approve", state: mailLabel, tone: mailTone, go: () => scrollTo("email-capture-title"), glyph: "M3 6h18v12H3zM3 7l9 7 9-7" },
    { id: "files", name: "Business files", what: "Bank, bills, purchase orders, stock, payroll, marketing, payouts and pipeline", state: "File import", tone: "neutral", go: () => scrollTo("dd-business-files"), glyph: "M6 3h9l3 3v15H6zM9 12h6M9 16h6" },
    { id: "myinvois", name: "LHDN e-invoices", what: "MyInvois-ready checks and PDFs; live submission is not connected", state: "Prepares, not connected", tone: "neutral", go: () => show("einvoice"), glyph: "M6 3h9l3 3v15H6zM9 13l2 2 4-4" },
    { id: "lenders", name: "Lenders", what: "Share a Passport link a lender can open and verify", state: "From Financing", tone: "neutral", go: () => show("financing"), glyph: "M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1m-2 4a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1" },
  ];

  return (
    <section className="dd-connections" aria-label="Connections">
      {tiles.map((tile) => (
        <button key={tile.id} type="button" className="dd-connection" onClick={tile.go}>
          <span className="dd-connection-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={tile.glyph} /></svg>
          </span>
          <strong>{tile.name}</strong>
          <span className="dd-connection-what">{tile.what}</span>
          <span className={"dd-connection-state is-" + tile.tone}><i aria-hidden="true" />{tile.state}</span>
        </button>
      ))}
    </section>
  );
}
