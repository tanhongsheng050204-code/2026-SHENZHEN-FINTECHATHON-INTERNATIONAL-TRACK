import { useEffect, useState } from "react";
import { useAppState } from "../lib/appState";
import { SCREENS, type Screen } from "../lib/screens";
import { friendlyLoadError } from "../api/client";
import { errorCode, fetchBriefing, type Briefing } from "../api/topicE";

/** DuitDuit's briefing: what needs this person today, each line opening its page. */
export function BriefingCard({ onNavigate }: { onNavigate?: () => void }) {
  const { show } = useAppState();
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchBriefing()
      .then((b) => active && setBriefing(b))
      .catch((e) => active && setError(friendlyLoadError(errorCode(e))));
    return () => { active = false; };
  }, []);

  if (error) return <p className="fb-inbox-muted">{error}</p>;
  if (!briefing) return <p className="fb-inbox-muted">Getting your briefing…</p>;

  const open = (screen: string | null) => {
    if (!screen || !(SCREENS as readonly string[]).includes(screen)) return;
    onNavigate?.();
    show(screen as Screen);
  };

  return (
    <div className="fb-assistant fb-briefing">
      <p><strong>{briefing.greeting}</strong></p>
      <ul className="fb-briefing-lines">
        {briefing.lines.map((line) => (
          <li key={line.kind} className={"is-" + line.tone}>
            <span>{line.text}</span>
            {line.screen && <button type="button" className="fb-cash-more" onClick={() => open(line.screen)}>Open →</button>}
          </li>
        ))}
      </ul>
    </div>
  );
}
