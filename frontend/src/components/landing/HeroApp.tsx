import { useEffect, useRef, useState } from "react";
import { LogoMark } from "../Logo";
import { EARLY, FIXED, GAP, LOW, MINIMUM, MOVES, chart, prefersReducedMotion, rm } from "./cashSeries";

/**
 * The landing page's one orchestrated moment: DuitDuit itself, working. The owner
 * asks a question, the answer and forecast arrive, the finance agent drafts a
 * reminder into the review inbox, and the owner approves it. Plays once when it
 * scrolls into view; with reduced motion the final frame shows at once. Every
 * figure is the synthetic demo company's (seed/topic_e.py).
 */

const QUESTION = "Can I pay everyone this month?";
const FINAL = 5;
// When each step begins, in milliseconds after the window comes into view.
const SCHEDULE = [0, 700, 2400, 4500, 6300, 8200];

const C = chart(520, 190, { left: 8, right: 8, top: 12, bottom: 22 });
const LIKELY = C.path(MOVES);
const SCENARIO = C.path(EARLY, 21, 30);

function useTyped(text: string, start: boolean, instant: boolean) {
  // The window remounts on replay, so the count always starts from zero.
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (instant || !start) return;
    const timer = window.setInterval(() => {
      setCount((n) => {
        if (n >= text.length) {
          window.clearInterval(timer);
          return n;
        }
        return n + 1;
      });
    }, 42);
    return () => window.clearInterval(timer);
  }, [start, instant, text]);
  return instant ? text : text.slice(0, count);
}

export function HeroApp() {
  const instant = prefersReducedMotion();
  const [step, setStep] = useState(instant ? FINAL : -1);
  const [take, setTake] = useState(0);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (instant) return;
    const node = root.current;
    if (!node) return;
    const timers: number[] = [];
    const run = () => SCHEDULE.forEach((at, i) => timers.push(window.setTimeout(() => setStep(i), at)));
    const seen = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          seen.disconnect();
          run();
        }
      },
      { threshold: 0.35 },
    );
    seen.observe(node);
    return () => {
      seen.disconnect();
      timers.forEach((t) => window.clearTimeout(t));
    };
  }, [instant, take]);

  const typed = useTyped(QUESTION, step >= 1, instant);
  const at = (n: number) => (step >= n ? " is-on" : "");

  const replay = () => {
    setStep(-1);
    setTake((n) => n + 1);
  };

  return (
    <div ref={root} className={"lv-app" + (step >= 0 ? " is-live" : "")} key={take}>
      <div className="lv-app-bar">
        <span className="lv-app-workspace">
          <LogoMark />
          <span>Synthetic Home Goods Importer</span>
        </span>
        {step >= FINAL && !instant && (
          <button type="button" className="lv-app-replay" onClick={replay}>Play again</button>
        )}
        <span className="lv-app-people" aria-hidden="true">
          <i className="is-owner">O</i>
          <i className="is-finance">F</i>
          <i className="is-compliance">C</i>
        </span>
      </div>

      <div className="lv-app-body">
        <nav className="lv-app-nav" aria-hidden="true">
          <span>Today</span>
          <span className="is-current">Ask DuitDuit</span>
          <span>
            Review inbox <b className={"lv-app-badge" + (step >= 3 && step < 4 ? " is-bump" : "")}>{step >= 3 && step < 4 ? 3 : 2}</b>
          </span>
          <span>Cash &amp; finance</span>
          <span>Financing &amp; Passport</span>
          <span>Trust &amp; audit</span>
        </nav>

        <div className="lv-app-main">
          <p className="lv-app-hello">Good morning, Owner.</p>
          <div className="lv-app-ask">
            <span className="lv-app-typed">{typed}</span>
            <span className={"lv-app-caret" + (step >= 1 && step < 2 ? " is-blinking" : "")} aria-hidden="true" />
          </div>

          <div className={"lv-app-answer" + at(2)}>
            <p>
              <strong>Not without action.</strong> The next 30 days fall {rm(GAP)} under your {rm(MINIMUM)} minimum, around day 23,
              when payroll and a supplier payment land together.
            </p>
            <svg className="lv-app-chart" viewBox={`0 0 ${C.width} ${C.height}`} role="img"
              aria-label={`Forecast: cash falls to ${rm(LOW)} on day 23. If Customer C pays early it stays at ${rm(FIXED)}.`}>
              <rect className="lv-zone" x={C.pad.left} y={C.y(MINIMUM)} width={C.width - C.pad.left - C.pad.right} height={C.height - C.pad.bottom - C.y(MINIMUM)} />
              <line className="lv-min" x1={C.pad.left} x2={C.width - C.pad.right} y1={C.y(MINIMUM)} y2={C.y(MINIMUM)} />
              <path className="lv-line" d={LIKELY} pathLength={1} />
              <path className={"lv-line is-scenario" + at(4)} d={SCENARIO} pathLength={1} />
              <circle className="lv-dip" cx={C.x(23)} cy={C.y(LOW)} r="5" />
              <text className="lv-axis" x={C.pad.left} y={C.height - 6}>Today</text>
              <text className="lv-axis" x={C.width - C.pad.right} y={C.height - 6} textAnchor="end">Day 90</text>
            </svg>
            <p className={"lv-app-fix" + at(4)}>If Customer C pays early, cash stays at {rm(FIXED)}.</p>
          </div>
        </div>

        <aside className="lv-app-inbox" aria-label="Review inbox">
          <p className="lv-app-inbox-title">Waiting for you</p>
          <div className={"lv-card is-new" + at(3) + (step >= 4 ? " is-approved" : "")}>
            <span className="lv-card-who"><i className="is-finance">F</i>Finance agent drafted</span>
            <strong>Reminder to Customer C: pay RM31,000 before day 23</strong>
            <span className="lv-card-foot">
              <em>L2 · owner approves</em>
              <span className="lv-card-action">{step >= 4 ? "Approved" : "Approve"}</span>
            </span>
          </div>
          <div className="lv-card">
            <span className="lv-card-who"><i className="is-finance">F</i>Financing agent drafted</span>
            <strong>Bank meeting: review lender sharing</strong>
            <span className="lv-card-foot"><em>L2 · owner approves</em></span>
          </div>
          <div className="lv-card">
            <span className="lv-card-who"><i className="is-sales">S</i>Sales agent drafted</span>
            <strong>Payment reminder for customer #1</strong>
            <span className="lv-card-foot"><em>L2 · owner approves</em></span>
          </div>
          <p className={"lv-app-sent" + at(4)}>Approved and recorded on the audit chain. Nothing went out on its own.</p>
        </aside>
      </div>

    </div>
  );
}
