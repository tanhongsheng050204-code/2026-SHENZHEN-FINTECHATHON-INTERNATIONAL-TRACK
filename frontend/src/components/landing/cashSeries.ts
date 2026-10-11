// The synthetic demo company's next 90 days of cash, from seed/topic_e.py.
// Shared by the landing page's hero window and its day rail.

export type Move = [day: number, amount: number];

export const OPENING = 116_400;
export const MINIMUM = 50_000;
export const MOVES: Move[] = [
  [6, -14_800], [11, 24_500], [21, 18_200], [23, -62_000], [23, -61_740], [26, 9_400],
  [30, 31_000], [36, -14_800], [38, 42_000], [43, 38_500], [46, -5_500], [53, -62_000], [54, 27_600],
  [58, -48_300], [60, 18_200], [61, 44_200], [66, -14_800], [70, 35_400], [75, -37_800], [80, 52_300],
  [83, -62_000], [87, 39_800],
];
// Asking Customer C to pay the day-30 invoice before day 23.
export const EARLY: Move[] = MOVES.map(([day, amount]) => (day === 30 && amount === 31_000 ? [21, amount] : [day, amount]));

export function balanceOn(moves: Move[], day: number): number {
  return moves.filter(([d]) => d <= day).reduce((total, [, amount]) => total + amount, OPENING);
}

export const LOW = balanceOn(MOVES, 23); // 20,560
export const GAP = MINIMUM - LOW; // 29,440
export const FIXED = balanceOn(EARLY, 23); // 51,560

export const rm = (n: number) => `RM${n.toLocaleString("en-MY")}`;

/** Coordinates for a chart of the given size, and step paths that follow the balance. */
export function chart(width: number, height: number, pad = { left: 12, right: 12, top: 16, bottom: 24 }, max = 200_000) {
  const x = (day: number) => pad.left + (day / 90) * (width - pad.left - pad.right);
  const y = (amount: number) => pad.top + (1 - Math.max(0, amount) / max) * (height - pad.top - pad.bottom);
  const path = (moves: Move[], fromDay = 0, toDay = 90) => {
    const sorted = [...moves].sort((a, b) => a[0] - b[0]);
    let balance = OPENING;
    let d = "";
    let day = 0;
    for (const [at, amount] of sorted) {
      if (at < fromDay) {
        balance += amount;
        continue;
      }
      if (at > toDay) break;
      if (!d) d = `M${x(Math.max(fromDay, day))},${y(balance)}`;
      d += `H${x(at)}`;
      balance += amount;
      d += `V${y(balance)}`;
      day = at;
    }
    return d + `H${x(toDay)}`;
  };
  return { x, y, path, pad, width, height };
}

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
