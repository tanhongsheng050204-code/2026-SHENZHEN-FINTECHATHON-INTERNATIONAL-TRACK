/**
 * A banknote-style guilloche rosette, drawn once as inline SVG. Security printing
 * is how money proves it is genuine; DuitDuit uses the same motif where it talks
 * about proof and protection. Decorative only.
 */

function rosette(R: number, r: number, d: number, steps = 1400): string {
  // Hypotrochoid: a point at distance d from the centre of a circle of radius r
  // rolling inside a circle of radius R. Integer ratios close the curve.
  const turns = r / gcd(R, r);
  const points: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * Math.PI * 2 * turns;
    const k = (R - r) / r;
    const x = (R - r) * Math.cos(t) + d * Math.cos(k * t);
    const y = (R - r) * Math.sin(t) - d * Math.sin(k * t);
    points.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }
  return "M" + points.join("L") + "Z";
}

function gcd(a: number, b: number): number {
  return b === 0 ? a : gcd(b, a % b);
}

const CURVES = [rosette(180, 48, 92), rosette(150, 35, 70), rosette(210, 66, 120), rosette(120, 27, 54)];

export function Guilloche({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="-260 -260 520 520" aria-hidden="true" focusable="false">
      {CURVES.map((d, i) => (
        <path key={i} d={d} fill="none" stroke="currentColor" strokeWidth={0.6} opacity={0.55 - i * 0.08} />
      ))}
    </svg>
  );
}
