// What the privacy layer does to one synthetic supplier email before any AI call:
// the on-server detector finds each personal or financial value and the record keeps
// a token in its place (LABEL_<digest>; amounts become a band, AMOUNT_BAND_<n>_<digest>).
// Band 5 is what tokenize._band_index gives RM18,450.00. The digests are illustrative.
import { Fragment, useEffect, useState } from "react";
import { useInView } from "../../lib/interactivity";

type Part = string | { text: string; kind: string; token: string };

const EMAIL: Part[] = [
  "Hi, this is ",
  { text: "Tan Mei Ling", kind: "Person", token: "PERSON_7c1e9a40b2" },
  " from ",
  { text: "Shenzhen Supplier 1", kind: "Company", token: "ORG_e4a09d31c8" },
  ". Our bank details have changed. Please pay ",
  { text: "RM18,450.00", kind: "Amount", token: "AMOUNT_BAND_5_91b2f0c47e" },
  " for INV-2207 to account ",
  { text: "5140 1234 5678", kind: "Bank account", token: "BANKACC_3d8f62a1e9" },
  ", and call me on ",
  { text: "012-345 6789", kind: "Phone", token: "PHONE_b05c7e2d14" },
  " if anything is unclear.",
];

function reduced() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function PrivacyScan() {
  const [ref, inView] = useInView<HTMLDivElement>();
  const [live, setLive] = useState(() => reduced());
  useEffect(() => {
    if (!inView || live) return;
    const t = window.setTimeout(() => setLive(true), 150);
    return () => window.clearTimeout(t);
  }, [inView, live]);
  function replay() {
    if (reduced()) return;
    setLive(false); // the effect above turns it back on, so every transition plays again
  }
  let n = 0;

  return (
    <div className={"lv-scan" + (live ? " is-live" : "")} ref={ref}>
      <figure className="lv-scan-card is-raw">
        <figcaption>
          <span>Arrives in your inbox</span>
          <em>Supplier email · synthetic</em>
        </figcaption>
        <p>
          {EMAIL.map((part, i) =>
            typeof part === "string" ? (
              <Fragment key={i}>{part}</Fragment>
            ) : (
              <mark key={i} style={{ ["--i" as string]: n++ }}>
                {part.text}
                <small>{part.kind}</small>
              </mark>
            ),
          )}
        </p>
        <span className="lv-scan-beam" aria-hidden="true" />
      </figure>

      <div className="lv-scan-arrow" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
        <span>Detected on our own server, before any AI call</span>
      </div>

      <figure className="lv-scan-card is-safe">
        <figcaption>
          <span>What the AI reads</span>
          <em>Tokens only</em>
        </figcaption>
        <p>
          {(() => {
            let k = 0;
            return EMAIL.map((part, i) =>
              typeof part === "string" ? (
                <Fragment key={i}>{part}</Fragment>
              ) : (
                <code key={i} style={{ ["--i" as string]: k++ }}>{part.token}</code>
              ),
            );
          })()}
        </p>
        <p className="lv-scan-foot">The real values stay in an encrypted vault. Only roles allowed to see them get them back, and each reveal is logged.</p>
      </figure>

      <button type="button" className="lv-route-btn lv-scan-replay" onClick={replay}>Replay</button>
    </div>
  );
}
