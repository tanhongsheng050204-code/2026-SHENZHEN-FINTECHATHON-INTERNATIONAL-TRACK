import { useEffect, useState } from "react";
import { fetchDemoCode, STEP_UP_EVENT } from "../api/session";
import "./DemoAuthenticator.css";

/**
 * The shared demo account's authenticator, shown beside the app the way a phone sits
 * beside a laptop. The server returns a code only to the demo session, so for every
 * other account this renders nothing.
 */
const OPEN_KEY = "dd-demo-auth-open";

export function DemoAuthenticator() {
  const [code, setCode] = useState<string | null>(null);
  const [left, setLeft] = useState(0);
  // Open, it covers part of the page, so it starts as a small button and opens when
  // an action asks for a code. The visitor's last choice is remembered.
  const [open, setOpenState] = useState(() => {
    try { return localStorage.getItem(OPEN_KEY) === "1"; } catch { return false; }
  });
  const setOpen = (value: boolean) => {
    setOpenState(value);
    try { localStorage.setItem(OPEN_KEY, value ? "1" : "0"); } catch { /* storage blocked */ }
  };
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const load = async () => {
      const next = await fetchDemoCode();
      if (!active) return;
      if (!next) {
        setCode(null);
        return;
      }
      setCode(next.code);
      setLeft(next.seconds_left);
      timer = window.setTimeout(load, next.seconds_left * 1000 + 300);
    };
    void load();
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    const opened = () => setOpenState(true);
    window.addEventListener(STEP_UP_EVENT, opened);
    return () => window.removeEventListener(STEP_UP_EVENT, opened);
  }, []);

  useEffect(() => {
    if (!code) return;
    const tick = window.setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => window.clearInterval(tick);
  }, [code]);

  if (!code) return null;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked: the code is on screen to type.
    }
  };

  if (!open) {
    return (
      <button className="dd-demo-auth is-closed" type="button" onClick={() => setOpen(true)}>
        Demo authenticator
      </button>
    );
  }

  return (
    <aside className="dd-demo-auth" aria-label="Demo authenticator">
      <div className="dd-demo-auth-head">
        <strong>Demo authenticator</strong>
        <button type="button" className="dd-demo-auth-x" onClick={() => setOpen(false)} aria-label="Hide the demo authenticator">
          ×
        </button>
      </div>
      <button type="button" className="dd-demo-auth-code" onClick={copy} aria-label={`Code ${code.split("").join(" ")}. Copy`}>
        {code.slice(0, 3)} {code.slice(3)}
      </button>
      <div className="dd-demo-auth-bar" aria-hidden="true">
        <span style={{ width: `${(left / 30) * 100}%` }} />
      </div>
      <p>
        {copied ? "Copied." : `Changes in ${left}s.`} Money approvals ask for this code. In a real company it lives
        only on the owner's phone.
      </p>
    </aside>
  );
}
