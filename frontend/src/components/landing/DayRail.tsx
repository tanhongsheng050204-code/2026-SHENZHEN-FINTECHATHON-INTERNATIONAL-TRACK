import { useEffect, useRef, useState, type ReactNode } from "react";
import { EARLY, FIXED, LOW, MINIMUM, MOVES, chart, rm } from "./cashSeries";

/**
 * One working day at the synthetic importer. A sticky rail follows the reader; each
 * panel's small scene plays when the panel reaches the middle of the screen.
 */

const C = chart(440, 170, { left: 8, right: 8, top: 10, bottom: 18 });
const LIKELY = C.path(MOVES);
const SCENARIO = C.path(EARLY, 21, 30);

function MiniChart({ withScenario }: { withScenario: boolean }) {
  return (
    <svg className="lv-mini-chart" viewBox={`0 0 ${C.width} ${C.height}`} role="img"
      aria-label={`Forecast: cash falls to ${rm(LOW)} on day 23${withScenario ? `; with Customer C paying early it stays at ${rm(FIXED)}` : ""}.`}>
      <rect className="lv-zone" x={C.pad.left} y={C.y(MINIMUM)} width={C.width - C.pad.left - C.pad.right} height={C.height - C.pad.bottom - C.y(MINIMUM)} />
      <line className="lv-min" x1={C.pad.left} x2={C.width - C.pad.right} y1={C.y(MINIMUM)} y2={C.y(MINIMUM)} />
      <path className="lv-line" d={LIKELY} pathLength={1} />
      <path className={"lv-line is-scenario" + (withScenario ? " is-on" : "")} d={SCENARIO} pathLength={1} />
      <circle className="lv-dip" cx={C.x(23)} cy={C.y(LOW)} r="4.5" />
    </svg>
  );
}

function Gap() {
  return (
    <div className="lv-scene">
      <MiniChart withScenario={false} />
      <div className="lv-alert">
        <strong>Lowest balance in 30 days: {rm(LOW)}</strong>
        <span>Below your {rm(MINIMUM)} minimum on day 23 · sent to the owner and finance</span>
      </div>
    </div>
  );
}

function BankReady() {
  return (
    <div className="lv-scene lv-bank">
      <div className="lv-match">
        <p className="lv-match-head"><strong>Import trade financing</strong><em>Eligible</em></p>
        <ul>
          <li>Import payables 52% <small>needs at least 20%</small></li>
          <li>Months trading 38 <small>needs at least 24</small></li>
        </ul>
        <p className="lv-match-src">Modelled on EXIM Bank Malaysia's import financing · synthetic demo product</p>
      </div>
      <div className="lv-passport">
        <span className="lv-passport-title">Financing Readiness Passport</span>
        <span className="lv-passport-row">Cash-flow health <b>Shortfall risk; gap under RM50k</b></span>
        <span className="lv-passport-row">Validated e-invoices <b>16%</b></span>
        <span className="lv-stamp">Verified · chain intact</span>
      </div>
    </div>
  );
}

function Chase() {
  return (
    <div className="lv-scene lv-board">
      <div className="lv-col">
        <p className="lv-col-head">Drafted by Finance</p>
        <div className="lv-ticket is-moving">
          <span className="lv-ticket-who"><i className="is-finance">F</i>Finance agent</span>
          <strong>Ask Customer C to pay RM31,000 before day 23</strong>
          <span className="lv-ticket-foot">L2 · owner approves</span>
        </div>
        <div className="lv-ticket is-ghost"><span className="lv-ticket-who"><i className="is-finance">F</i>Finance agent</span><strong>Reminder for a second customer</strong></div>
      </div>
      <div className="lv-col is-target">
        <p className="lv-col-head">Approved by Owner</p>
        <div className="lv-drop" aria-hidden="true" />
      </div>
    </div>
  );
}

function PayEveryone() {
  const [early, setEarly] = useState(false);
  return (
    <div className="lv-scene">
      <MiniChart withScenario={early} />
      <button type="button" className={"lv-toggle" + (early ? " is-on" : "")} aria-pressed={early} onClick={() => setEarly((v) => !v)}>
        <span className="lv-toggle-knob" aria-hidden="true" />
        Collect Customer C's RM31,000 before day 23
      </button>
      <p className="lv-scene-note" aria-live="polite">
        {early ? `Cash stays at ${rm(FIXED)}, above your minimum. A what-if only: no real date changes.` : `As things stand, cash falls to ${rm(LOW)} on day 23.`}
      </p>
    </div>
  );
}

function WhereMoneyWent() {
  const months = [
    { m: "Jul", net: 20_000 },
    { m: "Aug", net: 23_800 },
    { m: "Sep", net: 39_200 },
  ];
  return (
    <div className="lv-scene">
      <div className="lv-pnl" role="img" aria-label="Net result by month: July RM20,000, August RM23,800, September RM39,200">
        {months.map((row, i) => (
          <div key={row.m} className="lv-pnl-col" style={{ ["--i" as string]: i }}>
            <span className="lv-pnl-net">{rm(row.net)}</span>
            <span className="lv-pnl-bar" style={{ height: `${(row.net / 40_000) * 100}%` }} />
            <span className="lv-pnl-m">{row.m}</span>
          </div>
        ))}
      </div>
      <dl className="lv-ratios">
        <div><dt>Gross margin</dt><dd>49.5%</dd></div>
        <div><dt>Days to get paid</dt><dd>46.0</dd></div>
        <div><dt>Largest customer</dt><dd>29.3%</dd></div>
      </dl>
      <p className="lv-scene-note">September: RM39,200 net on RM249,400 of revenue. Every ratio shows its formula.</p>
    </div>
  );
}

function CloseMonth() {
  return (
    <div className="lv-scene">
      <p className="lv-close-head"><strong>September 2026 bank lines</strong><span>9 of 10 matched</span></p>
      <ol className="lv-lines">
        {Array.from({ length: 9 }, (_, i) => <li key={i} style={{ ["--i" as string]: i }}><span className="lv-tick" aria-hidden="true" />Matched to a record</li>)}
        <li className="is-open" style={{ ["--i" as string]: 9 }}><span className="lv-tick" aria-hidden="true" />RM1,250.00 out on 27 Sep · no record yet, waits for a person</li>
      </ol>
    </div>
  );
}

const STEPS: { time: string; title: string; rest: string; scene: ReactNode }[] = [
  { time: "08:00", title: "Know the gap.", rest: "The forecast reads every bill, payroll run and invoice, and the morning briefing tells each person what needs them.", scene: <Gap /> },
  { time: "09:00", title: "Walk into the bank ready.", rest: "Each product is checked rule by rule against your records, and the lender can verify the Passport you share.", scene: <BankReady /> },
  { time: "10:30", title: "Chase, politely.", rest: "The finance agent drafts one reminder for each customer due before the gap. The owner approves; nothing goes out on its own.", scene: <Chase /> },
  { time: "14:00", title: "Ask before you pay.", rest: "Try a what-if: collect one invoice earlier and watch the gap close.", scene: <PayEveryone /> },
  { time: "16:00", title: "See where the money went.", rest: "A monthly profit and loss, margins and ratios from the same records as the forecast, so the numbers agree.", scene: <WhereMoneyWent /> },
  { time: "17:00", title: "Close the month honestly.", rest: "Nine of ten September bank lines match a record. The tenth waits for a person to explain it, not a guess.", scene: <CloseMonth /> },
];

export function DayRail() {
  const [active, setActive] = useState(0);
  const panels = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    const watch = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const index = Number((entry.target as HTMLElement).dataset.index);
          if (entry.isIntersecting) {
            setActive(index);
            entry.target.classList.add("is-active");
          }
        }
      },
      { rootMargin: "-42% 0px -42% 0px" },
    );
    panels.current.forEach((p) => p && watch.observe(p));
    return () => watch.disconnect();
  }, []);

  return (
    <div className="lv-day">
      <ol className="lv-rail" aria-label="A working day with DuitDuit">
        {STEPS.map((s, i) => (
          <li key={s.time} className={i === active ? "is-current" : undefined}>
            <button type="button" onClick={() => panels.current[i]?.scrollIntoView({ behavior: "smooth", block: "center" })} aria-current={i === active ? "step" : undefined}>
              <span>{s.time}</span>
              {s.title.replace(/\.$/, "")}
            </button>
          </li>
        ))}
      </ol>
      <div className="lv-panels">
        {STEPS.map((s, i) => (
          <section key={s.time} className="lv-panel" data-index={i} ref={(node) => { panels.current[i] = node; }} aria-labelledby={`lv-step-${i}`}>
            <p className="lv-panel-time">{s.time}</p>
            <h3 id={`lv-step-${i}`} className="lv-two-tone"><span>{s.title}</span> {s.rest}</h3>
            <div className="lv-panel-stage">{s.scene}</div>
          </section>
        ))}
      </div>
    </div>
  );
}
