import { useEffect, useRef, useState } from "react";

/**
 * The landing page's one orchestrated moment: the synthetic demo company's next
 * 90 days of cash, drawn as the balance actually moves (in steps). It dips below
 * the owner's minimum on day 23, DuitDuit proposes asking one customer to pay
 * early, and the new line clears the minimum. Every figure comes from the demo
 * seed (seed/topic_e.py). With reduced motion, the final frame shows at once.
 */

type Move = [day: number, amount: number];

const OPENING = 116_400;
const MINIMUM = 50_000;
const MOVES: Move[] = [
  [6, -14_800], [11, 24_500], [21, 18_200], [23, -62_000], [23, -61_740], [26, 9_400],
  [30, 31_000], [36, -14_800], [38, 42_000], [43, 38_500], [46, -5_500], [53, -62_000], [54, 27_600],
  [58, -48_300], [60, 18_200], [61, 44_200], [66, -14_800], [70, 35_400], [75, -37_800], [80, 52_300],
  [83, -62_000], [87, 39_800],
];
// Asking Customer C to pay the day-30 invoice before day 23.
const EARLY: Move[] = MOVES.map(([day, amount]) => (day === 30 && amount === 31_000 ? [21, amount] : [day, amount]));

const W = 720;
const H = 340;
const PAD = { left: 18, right: 18, top: 28, bottom: 40 };
const MAX = 200_000;
const x = (day: number) => PAD.left + (day / 90) * (W - PAD.left - PAD.right);
const y = (rm: number) => PAD.top + (1 - Math.max(0, rm) / MAX) * (H - PAD.top - PAD.bottom);

function stepPath(moves: Move[], fromDay = 0, toDay = 90): string {
  const sorted = [...moves].sort((a, b) => a[0] - b[0]);
  let balance = OPENING;
  let path = "";
  let day = 0;
  for (const [d, amount] of sorted) {
    if (d < fromDay) {
      balance += amount;
      continue;
    }
    if (d > toDay) break;
    if (!path) path = `M${x(Math.max(fromDay, day))},${y(balance)}`;
    path += `H${x(d)}`;
    balance += amount;
    path += `V${y(balance)}`;
    day = d;
  }
  return path + `H${x(toDay)}`;
}

function balanceOn(moves: Move[], day: number): number {
  return moves.filter(([d]) => d <= day).reduce((total, [, amount]) => total + amount, OPENING);
}

const LIKELY = stepPath(MOVES);
// Only the stretch that differs: from the early receipt until the paths rejoin.
const SCENARIO = stepPath(EARLY, 21, 30);
const LOW = balanceOn(MOVES, 23); // 20,560
const GAP = MINIMUM - LOW; // 29,440
const FIXED = balanceOn(EARLY, 23); // 51,560

function reduced() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function useCount(target: number, start: boolean, delay: number, duration = 900) {
  const [value, setValue] = useState(() => (reduced() ? target : 0));
  useEffect(() => {
    if (!start || reduced()) return;
    let raf = 0;
    const timer = window.setTimeout(() => {
      const begin = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - begin) / duration);
        setValue(Math.round(target * (1 - Math.pow(1 - t, 3))));
        if (t < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }, delay);
    return () => {
      window.clearTimeout(timer);
      cancelAnimationFrame(raf);
    };
  }, [start, target, delay, duration]);
  return value;
}

const rm = (n: number) => `RM${n.toLocaleString("en-MY")}`;

export function RunwayFilm() {
  const [take, setTake] = useState(0);
  const [playing, setPlaying] = useState(false);
  const frame = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (reduced()) return;
    // Start on the next frame so the drawing transitions run from their start state.
    const raf = requestAnimationFrame(() => setPlaying(true));
    return () => cancelAnimationFrame(raf);
  }, [take]);

  const gap = useCount(GAP, playing, 2300);

  const replay = () => {
    setPlaying(false);
    setTake((n) => n + 1);
  };

  const done = reduced() || playing;
  return (
    <div ref={frame} key={take} className={"lx-film" + (done ? " is-playing" : "")}>
      <div className="lx-film-head">
        <span className="lx-film-title">Next 90 days of cash</span>
        <span className="lx-film-tag">Synthetic demo company</span>
      </div>
      <svg className="lx-film-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Forecast: cash falls to ${rm(LOW)} on day 23, ${rm(GAP)} below the ${rm(MINIMUM)} minimum. Asking one customer to pay early keeps it at ${rm(FIXED)}.`}>
        {[0, 30, 60, 90].map((d) => (
          <g key={d}>
            <line className="lx-grid" x1={x(d)} x2={x(d)} y1={PAD.top} y2={H - PAD.bottom} />
            <text className="lx-axis" x={x(d)} y={H - 14} textAnchor={d === 0 ? "start" : d === 90 ? "end" : "middle"}>{d === 0 ? "Today" : `Day ${d}`}</text>
          </g>
        ))}
        <rect className="lx-danger-zone" x={PAD.left} y={y(MINIMUM)} width={W - PAD.left - PAD.right} height={H - PAD.bottom - y(MINIMUM)} />
        <line className="lx-min" x1={PAD.left} x2={W - PAD.right} y1={y(MINIMUM)} y2={y(MINIMUM)} />
        <text className="lx-min-label" x={PAD.left + 6} y={y(MINIMUM) + 18} textAnchor="start">Your minimum {rm(MINIMUM)}</text>
        <path className="lx-line" d={LIKELY} pathLength={1} />
        <path className="lx-line is-scenario" d={SCENARIO} pathLength={1} />
        <g className="lx-dip" transform={`translate(${x(23)},${y(LOW)})`}>
          <circle className="lx-dip-ring" r="14" />
          <circle className="lx-dip-dot" r="5" />
        </g>
        <g className="lx-fix" transform={`translate(${x(23)},${y(FIXED)})`}>
          <circle className="lx-fix-dot" r="5" />
        </g>
      </svg>
      <div className="lx-film-legend" aria-hidden="true">
        <span><i />Likely balance</span>
        <span><i className="is-scenario" />If Customer C pays early</span>
        <span><i className="is-min" />Your minimum</span>
      </div>
      <div className="lx-film-callout">
        <span className="lx-film-day">Day 23 · payroll and a supplier payment land together</span>
        <span className="lx-film-gap">{rm(gap)} short</span>
      </div>
      <div className="lx-film-agent" role="status">
        <span className="lx-film-agent-mark" aria-hidden="true" />
        <div>
          <strong>Ask Customer C to pay RM31,000 before day 23</strong>
          <span>Cash stays at {rm(FIXED)}. The reminder is drafted and waits for your approval.</span>
        </div>
      </div>
      <button type="button" className="lx-film-replay" onClick={replay} aria-label="Play the forecast again">Play again</button>
    </div>
  );
}
