import { useId } from "react";

export function LogoMark({ large }: { large?: boolean }) {
  const gradientId = useId();
  return (
    <svg className={large ? "fb-logo-mark-lg" : "fb-logo-mark"} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1F8FE0" />
          <stop offset="1" stopColor="#17B892" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${gradientId})`} />
      {/* DuitDuit: two linked coins */}
      <circle cx="12.5" cy="16" r="6.6" stroke="#fff" strokeWidth="2.2" />
      <circle cx="19.5" cy="16" r="6.6" stroke="#fff" strokeWidth="2.2" />
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
