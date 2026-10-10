const INK = "#1E140D";
const FUR = "#F28C1E";
const CREAM = "#FFF6EA";

// DuitDuit's mark: a cartoon tiger on ringgit teal. public/favicon.svg holds the same drawing.
export function LogoMark({ large }: { large?: boolean }) {
  return (
    <svg className={large ? "fb-logo-mark-lg" : "fb-logo-mark"} viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <rect width="64" height="64" rx="16" fill="#0B7A6B" />
      <circle cx="15" cy="18" r="8" fill={FUR} />
      <circle cx="49" cy="18" r="8" fill={FUR} />
      <circle cx="15" cy="18" r="4" fill="#FFE3C2" />
      <circle cx="49" cy="18" r="4" fill="#FFE3C2" />
      <path d="M32 13c11 0 20 7 21 18 3 1 4 4 3 7-2 0-3 0-4 1 0 9-9 15-20 15S12 48 12 39c-1-1-2-1-4-1-1-3 0-6 3-7 1-11 10-18 21-18z" fill={FUR} />
      <path d="M32 14l-2.6 7h5.2zM25 16l1 6 3-1zM39 16l-1 6-3-1z" fill={INK} />
      <path d="M12 34l7 1-6 2zM12.6 40l6.4-1-5.4 3zM52 34l-7 1 6 2zM51.4 40l-6.4-1 5.4 3z" fill={INK} />
      <ellipse cx="26.5" cy="43" rx="7.5" ry="6.5" fill={CREAM} />
      <ellipse cx="37.5" cy="43" rx="7.5" ry="6.5" fill={CREAM} />
      <ellipse cx="24" cy="31" rx="3.2" ry="3.8" fill={INK} />
      <ellipse cx="40" cy="31" rx="3.2" ry="3.8" fill={INK} />
      <circle cx="25.2" cy="29.6" r="1.2" fill="#fff" />
      <circle cx="41.2" cy="29.6" r="1.2" fill="#fff" />
      <path d="M28.5 38h7c0 2.2-1.8 3.6-3.5 4.2-1.7-.6-3.5-2-3.5-4.2z" fill={INK} />
      <path
        d="M32 42.5v2.2M27.5 45.5c1.6 1.8 3.2 1.6 4.5-.8 1.3 2.4 2.9 2.6 4.5.8"
        stroke={INK}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Wordmark({
  onClick,
  large,
  style,
}: {
  onClick?: () => void;
  large?: boolean;
  style?: React.CSSProperties;
}) {
  if (!onClick) {
    return (
      <div className="fb-wordmark" style={{ pointerEvents: "none", ...style }}>
        <LogoMark large={large} />
        <span className="fb-wordmark-text">DuitDuit</span>
      </div>
    );
  }
  return (
    <button className="fb-wordmark" style={style} onClick={onClick}>
      <LogoMark large={large} />
      <span className="fb-wordmark-text">DuitDuit</span>
    </button>
  );
}
