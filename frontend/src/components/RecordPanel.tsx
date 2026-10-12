import { useEffect, useRef, type ReactNode } from "react";
import { useI18n } from "../lib/i18n";
import "./records.css";

/**
 * A record opened in a panel on the right, over the page: a title, then sections.
 * Escape or the close button closes it, and focus returns to what opened it.
 */
export function RecordPanel({ kicker, title, onClose, children }: {
  kicker?: string;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const { tx } = useI18n();
  const panel = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  useEffect(() => { close.current = onClose; }, [onClose]);

  // Once per opening: focus inside, trap Tab, close on Escape, give focus back after.
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    panel.current?.querySelector<HTMLElement>("button, input, select, a")?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close.current();
      if (event.key !== "Tab" || !panel.current) return;
      const focusable = panel.current.querySelectorAll<HTMLElement>("button:not(:disabled), input, select, a[href]");
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      opener?.focus?.();
    };
  }, []);

  return (
    <>
      <div className="rc-scrim" onClick={onClose} aria-hidden="true" />
      <div className="rc-panel" role="dialog" aria-modal="true" aria-labelledby="rc-panel-title" ref={panel}>
        <div className="rc-panel-head">
          <div>
            {kicker && <p className="rc-panel-kicker">{kicker}</p>}
            <h2 id="rc-panel-title">{title}</h2>
          </div>
          <button type="button" className="rc-close" onClick={onClose} aria-label={tx("Close")}>×</button>
        </div>
        <div className="rc-panel-body">{children}</div>
      </div>
    </>
  );
}

export function Who({ name }: { name: string }) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return <span className="rc-who"><i aria-hidden="true">{initial}</i><span>{name}</span></span>;
}
