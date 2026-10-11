import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "./cashSeries";

/**
 * How the audit chain catches a change, as an illustration (the hashes are made up).
 * Each event holds the hash of the one before it, so editing any record breaks every
 * link after it. The app's Trust & audit page runs the real check.
 */

const EVENTS = [
  { label: "Reminder drafted", by: "Finance agent", hash: "3f9a…c21e" },
  { label: "Reminder approved", by: "Owner", hash: "b70d…4a88" },
  { label: "Passport shared for 7 days", by: "Owner, with a code", hash: "e1c4…09f3" },
  { label: "Passport verified", by: "Lender", hash: "52aa…d7b0" },
];

type Mode = "idle" | "checking" | "intact" | "tampered";

export function ChainProof() {
  const [mode, setMode] = useState<Mode>("idle");
  const [lit, setLit] = useState(0);
  const timers = useRef<number[]>([]);

  useEffect(() => () => timers.current.forEach((t) => window.clearTimeout(t)), []);

  const run = (tamper: boolean) => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
    const stop = tamper ? 1 : EVENTS.length;
    if (prefersReducedMotion()) {
      setLit(stop);
      setMode(tamper ? "tampered" : "intact");
      return;
    }
    setMode("checking");
    setLit(0);
    for (let i = 1; i <= stop; i += 1) timers.current.push(window.setTimeout(() => setLit(i), i * 420));
    timers.current.push(window.setTimeout(() => setMode(tamper ? "tampered" : "intact"), stop * 420 + 260));
  };

  return (
    <div className={"lv-chain is-" + mode}>
      <ol>
        {EVENTS.map((e, i) => {
          const broken = mode === "tampered" && i >= 1;
          return (
            <li key={e.label} className={(i < lit ? "is-lit" : "") + (broken ? " is-broken" : "")}>
              <strong>{e.label}</strong>
              <span>{e.by}</span>
              <code>{broken && i === 1 ? "edited record" : e.hash}</code>
            </li>
          );
        })}
      </ol>
      <div className="lv-chain-actions">
        <button type="button" className="lx-btn is-ghost" onClick={() => run(false)}>Verify the chain</button>
        <button type="button" className="lv-chain-tamper" onClick={() => run(true)}>Edit one record, then verify</button>
        <p role="status" className="lv-chain-result">
          {mode === "intact" && "Chain intact: every event links to the one before it."}
          {mode === "tampered" && "Change detected at the approval: it no longer matches the hash the next event holds."}
          {mode === "checking" && "Checking each link…"}
          {mode === "idle" && "Illustration. In the app, Trust & audit re-verifies the real chain."}
        </p>
      </div>
    </div>
  );
}
