import { lazy, Suspense, useEffect } from "react";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { AppStateProvider, useAppState } from "./lib/appState";
import { I18nProvider } from "./lib/i18n";
import { ThemeProvider } from "./lib/theme";
import { UiChromeProvider } from "./lib/uiChrome";
import { AskDrawer } from "./components/AskDrawer";
import { QuickActionsPalette } from "./components/QuickActionsPalette";
import { StepUpPrompt } from "./components/StepUpPrompt";
import { ServerStatusBanner } from "./components/ServerStatusBanner";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { LogoMark } from "./components/Logo";
import { sharedRouteFor } from "./lib/sharedRoutes";
import { PAGE_TITLES, PUBLIC_SCREENS } from "./lib/screens";

// Route-level code splitting: a visitor to the marketing landing page
// shouldn't have to download the chat interface, invoice forms, and
// finance charts before the page they actually asked for can render.
// After a redeploy, a page left open asks for code files that no longer exist.
// Reload once to pick up the new build instead of showing an error.
function fresh<T>(load: () => Promise<T>): Promise<T> {
  return load().catch((error: unknown) => {
    let reloaded = false;
    try { reloaded = sessionStorage.getItem("dd-reloaded-for-build") === "1"; } catch { /* storage blocked */ }
    if (!reloaded) {
      try { sessionStorage.setItem("dd-reloaded-for-build", "1"); } catch { /* storage blocked */ }
      window.location.reload();
      return new Promise<T>(() => undefined);
    }
    throw error;
  }).then((module) => {
    try { sessionStorage.removeItem("dd-reloaded-for-build"); } catch { /* storage blocked */ }
    return module;
  });
}

const Landing = lazy(() => fresh(() => import("./screens/Landing")));
const Login = lazy(() => fresh(() => import("./screens/Login")));
const Signup = lazy(() => fresh(() => import("./screens/Signup")));
const Onboarding = lazy(() => fresh(() => import("./screens/Onboarding")));
const Security = lazy(() => fresh(() => import("./screens/Security")));
const Legal = lazy(() => fresh(() => import("./screens/Legal")));
const Pricing = lazy(() => fresh(() => import("./screens/Pricing")));
const Changelog = lazy(() => fresh(() => import("./screens/Changelog")));
const Help = lazy(() => fresh(() => import("./screens/Help")));
const Home = lazy(() => fresh(() => import("./screens/Home")));
const Agents = lazy(() => fresh(() => import("./screens/Agents")));
const Customers = lazy(() => fresh(() => import("./screens/Customers")));
const Einvoice = lazy(() => fresh(() => import("./screens/Einvoice")));
const EinvoiceDetail = lazy(() => fresh(() => import("./screens/EinvoiceDetail")));
const Finance = lazy(() => fresh(() => import("./screens/Finance")));
const Analysis = lazy(() => fresh(() => import("./screens/Analysis")));
const Collections = lazy(() => fresh(() => import("./screens/Collections")));
const Audit = lazy(() => fresh(() => import("./screens/Audit")));
const Approvals = lazy(() => fresh(() => import("./screens/Approvals")));
const Ingestion = lazy(() => fresh(() => import("./screens/Ingestion")));
const Settings = lazy(() => fresh(() => import("./screens/Settings")));
const ReviewInbox = lazy(() => fresh(() => import("./screens/ReviewInbox")));
const CashFlow = lazy(() => fresh(() => import("./screens/CashFlow")));
const Financing = lazy(() => fresh(() => import("./screens/Financing")));
const Positions = lazy(() => fresh(() => import("./screens/Positions")));
const Autonomy = lazy(() => fresh(() => import("./screens/Autonomy")));
const Team = lazy(() => fresh(() => import("./screens/Team")));
const Trust = lazy(() => fresh(() => import("./screens/Trust")));
const SecurityActivity = lazy(() => fresh(() => import("./screens/SecurityActivity")));
const CompanySettings = lazy(() => fresh(() => import("./screens/CompanySettings")));
const SharedView = lazy(() => fresh(() => import("./screens/SharedView")));

function Screens() {
  const { screen, show, setAskRole } = useAppState();
  const { identity, loading } = useAuth();
  const isPublic = PUBLIC_SCREENS.includes(screen);

  useEffect(() => {
    if (identity) setAskRole(identity.role);
  }, [identity, setAskRole]);

  useEffect(() => {
    document.title = `${PAGE_TITLES[screen]} · DuitDuit`;
  }, [screen]);

  useEffect(() => {
    if (!loading && !identity && !isPublic) show("login");
    if (!loading && identity && (screen === "login" || screen === "signup")) show("home");
  }, [identity, isPublic, loading, screen, show]);

  // Links shared with lenders and auditors open without signing in.
  const shared = sharedRouteFor(window.location.pathname);
  if (shared) return <SharedView route={shared} />;

  if (loading) {
    return <div className="fb-root"><div className="fb-callout">Checking secure session…</div></div>;
  }

  switch (screen) {
    case "landing": return <Landing />;
    case "login": return <Login />;
    case "signup": return <Signup />;
    case "onboarding": return <Onboarding />;
    case "security": return <Security />;
    case "legal": return <Legal />;
    case "pricing": return <Pricing />;
    case "changelog": return <Changelog />;
    case "help": return <Help />;
    case "home": return <Home />;
    case "agents": return <Agents />;
    case "customers": return <Customers />;
    case "einvoice": return <Einvoice />;
    case "einvoice-detail": return <EinvoiceDetail />;
    case "finance": return <Finance />;
    case "analysis": return <Analysis />;
    case "collections": return <Collections />;
    case "audit": return <Audit />;
    case "approvals": return <Approvals />;
    case "ingestion": return <Ingestion />;
    case "settings": return <Settings />;
    case "inbox": return <ReviewInbox />;
    case "cashflow": return <CashFlow />;
    case "financing": return <Financing />;
    case "positions": return <Positions />;
    case "autonomy": return <Autonomy />;
    case "team": return <Team />;
    case "trust": return <Trust />;
    case "activity": return <SecurityActivity />;
    case "company": return <CompanySettings />;
    default: return <Landing />;
  }
}

const RouteFallback = (
  <div className="fb-route-loading">
    <div className="fb-route-loading-mark"><LogoMark large /></div>
    <div className="fb-route-loading-spinner" aria-hidden="true" />
  </div>
);

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <I18nProvider>
          <AppStateProvider>
            <AuthProvider>
              <UiChromeProvider>
                <ServerStatusBanner />
                <Suspense fallback={RouteFallback}>
                  <Screens />
                </Suspense>
                <AskDrawer />
                <QuickActionsPalette />
                <StepUpPrompt />
              </UiChromeProvider>
            </AuthProvider>
          </AppStateProvider>
        </I18nProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
