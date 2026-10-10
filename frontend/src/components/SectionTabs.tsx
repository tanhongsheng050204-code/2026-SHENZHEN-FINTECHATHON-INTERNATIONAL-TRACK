import { useAuth } from "../auth/AuthProvider";
import { canOpen } from "../lib/access";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import type { Screen } from "../lib/screens";

// Pages that belong together share one tab row, so a merged area reads as one
// place: Review inbox + Workflows, Cash flow + Financial intelligence, and
// Trust + Audit & access.
const SECTIONS: Record<string, { screen: Screen; key: string }[]> = {
  inbox: [
    { screen: "inbox", key: "tabs.agentProposals" },
    { screen: "approvals", key: "tabs.recommendations" },
  ],
  money: [
    { screen: "cashflow", key: "tabs.forecast" },
    { screen: "finance", key: "tabs.intelligence" },
    { screen: "analysis", key: "tabs.analysis" },
  ],
  trust: [
    { screen: "trust", key: "tabs.posture" },
    { screen: "audit", key: "tabs.audit" },
  ],
};

export function SectionTabs({ section, current }: { section: keyof typeof SECTIONS; current: Screen }) {
  const { show, askRole } = useAppState();
  const { identity } = useAuth();
  const { t } = useI18n();
  const role = identity?.role ?? askRole;
  const tabs = SECTIONS[section].filter((tab) => canOpen(tab.screen, role));
  if (tabs.length < 2) return null;
  return (
    <nav className="fb-section-tabs" aria-label={t(`tabs.section.${section}`)}>
      {tabs.map((tab) => (
        <button
          key={tab.screen}
          type="button"
          aria-current={tab.screen === current ? "page" : undefined}
          className={tab.screen === current ? "is-current" : undefined}
          onClick={() => show(tab.screen)}
        >
          {t(tab.key)}
        </button>
      ))}
    </nav>
  );
}
