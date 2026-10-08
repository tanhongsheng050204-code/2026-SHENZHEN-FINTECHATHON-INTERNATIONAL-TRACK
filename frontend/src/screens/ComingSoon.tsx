import { Sidebar, AppTopBar } from "../components/Nav";
import { EmptyState } from "../components/EmptyState";
import { useAppState, type Screen } from "../lib/appState";
import { useI18n } from "../lib/i18n";

// Placeholder for Topic E pages whose sidebar entry exists before the page
// itself is built, so navigation never falls through to the landing page.
export default function ComingSoon({ screen, titleKey }: { screen: Screen; titleKey: string }) {
  const { t } = useI18n();
  const { show } = useAppState();
  return (
    <div className="fb-root fb-shell">
      <Sidebar current={screen} />
      <AppTopBar current={screen} />
      <header className="fb-app-header">
        <h1>{t(titleKey)}</h1>
      </header>
      <div className="fb-page-body">
        <EmptyState
          title={t("soon.title")}
          description={t("soon.desc")}
          action={{ label: t("inbox.title"), onClick: () => show("inbox") }}
        />
      </div>
    </div>
  );
}
