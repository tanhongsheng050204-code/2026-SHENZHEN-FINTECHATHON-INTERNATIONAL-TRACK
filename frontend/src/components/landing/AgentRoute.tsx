// "Ask once": how the supervisor routes one question, as agent_runtime.plan() does it.
// For "Can we pay salaries this month?" the plan is cash + payroll, so Cash flow,
// Collections, Financing and HR & payroll run; Sales, Payables and Compliance do not.
// In the synthetic demo company the first three each leave one review-inbox item
// (HR's payroll check only proposes when pay day goes below the minimum).
import { useEffect, useRef, useState } from "react";
import { useInView } from "../../lib/interactivity";

type Agent = { id: string; name: string; y: number; used: boolean; proposes?: boolean; result: string };

const AGENTS: Agent[] = [
  { id: "cash", name: "Cash flow", y: 9, used: true, proposes: true, result: "Shortfall on day 23" },
  { id: "collect", name: "Collections", y: 22.5, used: true, proposes: true, result: "3 reminder drafts" },
  { id: "finance", name: "Financing", y: 36, used: true, proposes: true, result: "Invoice financing pack" },
  { id: "hr", name: "HR & payroll", y: 50, used: true, result: "Payroll checked, no proposal" },
  { id: "sales", name: "Sales", y: 64, used: false, result: "Not needed" },
  { id: "bills", name: "Payables", y: 77.5, used: false, result: "Not needed" },
  { id: "comply", name: "Compliance", y: 91, used: false, result: "Not needed" },
];

// The map keeps a fixed 760×480 shape, so node positions in % and the SVG paths agree.
const W = 760;
const H = 480;
const SUP = { x: 20, y: 50 };
const AGENT_X = 56;
const INBOX = { x: 88, y: 50 };
const USED = AGENTS.filter((a) => a.used).length;
const PROPOSALS = AGENTS.filter((a) => a.proposes).length;

// Phases: 1 question in, 2–8 one agent checked each, 9 verdict, 10 paths to the inbox, 11 done.
const CHECK_FIRST = 2;
const VERDICT = CHECK_FIRST + AGENTS.length;
const PATHS = VERDICT + 1;
const DONE = PATHS + 1;
const STEP_MS = 650;

function curve(x1: number, y1: number, x2: number, y2: number) {
  const [ax, ay, bx, by] = [(x1 * W) / 100, (y1 * H) / 100, (x2 * W) / 100, (y2 * H) / 100];
  const mid = (ax + bx) / 2;
  return `M${ax} ${ay} C${mid} ${ay} ${mid} ${by} ${bx} ${by}`;
}

function reduced() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function AgentRoute() {
  const [ref, inView] = useInView<HTMLDivElement>();
  const [phase, setPhase] = useState(() => (reduced() ? DONE : 0));
  const [paused, setPaused] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (inView && !started.current && phase === 0) {
      started.current = true;
      const t = window.setTimeout(() => setPhase(1), 300);
      return () => window.clearTimeout(t);
    }
  }, [inView, phase]);

  useEffect(() => {
    if (paused || phase === 0 || phase >= DONE) return;
    const t = window.setTimeout(() => setPhase((p) => p + 1), phase === VERDICT ? STEP_MS * 1.6 : STEP_MS);
    return () => window.clearTimeout(t);
  }, [phase, paused]);

  const checking = phase >= CHECK_FIRST && phase < VERDICT ? phase - CHECK_FIRST : -1;
  const checked = Math.min(Math.max(phase - CHECK_FIRST, 0), AGENTS.length);
  const verdict = phase >= VERDICT;

  const status =
    phase === 0 ? "Waiting for a question" :
    phase === 1 ? "Reading the question" :
    !verdict ? `Checking agents · ${checked + (checking >= 0 ? 1 : 0)} of ${AGENTS.length}` :
    phase < DONE ? `${USED} of ${AGENTS.length} agents relevant · preparing proposals` :
    `${USED} of ${AGENTS.length} agents ran · ${PROPOSALS} proposals wait for a person`;

  function replay() {
    setPaused(false);
    setPhase(reduced() ? DONE : 1);
  }

  return (
    <div className="lv-route" ref={ref}>
      <div className="lv-route-panel">
        <p className="lv-route-label">The owner asks</p>
        <p className={"lv-route-question" + (phase >= 1 ? " is-on" : "")}>Can we pay salaries this month?</p>
        <ol className="lv-route-log" aria-label="What the agents did">
          {AGENTS.map((a, i) => {
            const state = i < checked || verdict ? (a.used ? "is-used" : "is-skip") : i === checking ? "is-checking" : "";
            return (
              <li key={a.id} className={state}>
                <i aria-hidden="true" />
                <span>{a.name}</span>
                <em>{i < checked || verdict ? a.result : i === checking ? "Checking…" : ""}</em>
              </li>
            );
          })}
        </ol>
        <p className="lv-route-status" role="status" aria-live="polite">{status}</p>
        <div className="lv-route-actions">
          <button type="button" className="lv-route-btn" onClick={replay}>Replay</button>
          {phase > 0 && phase < DONE && (
            <button type="button" className="lv-route-btn" onClick={() => setPaused((v) => !v)} aria-pressed={paused}>
              {paused ? "Resume" : "Pause"}
            </button>
          )}
        </div>
      </div>

      <div className={"lv-route-map" + (phase >= DONE ? " is-done" : "")} aria-hidden="true">
        <svg className="lv-route-edges" viewBox={`0 0 ${W} ${H}`}>
          <path className={"lv-edge" + (phase >= 1 ? " is-on" : "")} d={curve(0, 50, SUP.x, SUP.y)} pathLength={1} />
          {AGENTS.map((a, i) => (
            <path
              key={"s" + a.id}
              className={"lv-edge" + (i === checking ? " is-scan" : "") + (verdict ? (a.used ? " is-on" : " is-off") : i < checked ? " is-seen" : "")}
              d={curve(SUP.x, SUP.y, AGENT_X, a.y)}
              pathLength={1}
            />
          ))}
          {AGENTS.filter((a) => a.proposes).map((a) => (
            <path key={"i" + a.id} className={"lv-edge is-gold" + (phase >= PATHS ? " is-on" : "")} d={curve(AGENT_X, a.y, INBOX.x, INBOX.y)} pathLength={1} />
          ))}
        </svg>

        <div className={"lv-node is-sup" + (phase >= 1 ? " is-on" : "")} style={{ left: SUP.x + "%", top: SUP.y + "%" }}>
          <strong>Supervisor</strong>
          <span>Routes the question</span>
        </div>
        {AGENTS.map((a, i) => (
          <div
            key={a.id}
            className={"lv-node is-agent" + (i === checking ? " is-checking" : "") + (verdict ? (a.used ? " is-on" : " is-off") : "")}
            style={{ left: AGENT_X + "%", top: a.y + "%" }}
          >
            <strong>{a.name}</strong>
          </div>
        ))}
        <div className={"lv-node is-inbox" + (phase >= DONE ? " is-on" : "")} style={{ left: INBOX.x + "%", top: INBOX.y + "%" }}>
          <strong>Review inbox</strong>
          <span>{phase >= DONE ? `${PROPOSALS} waiting for you` : "Waiting"}</span>
          <em>Nothing paid or sent</em>
        </div>
      </div>

      <p className="lv-route-note">
        The routing is the app's own for this question. Results come from the synthetic demo company.
      </p>
    </div>
  );
}
