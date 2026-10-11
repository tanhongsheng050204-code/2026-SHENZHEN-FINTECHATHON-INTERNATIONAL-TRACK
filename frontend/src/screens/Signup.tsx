import { useState } from "react";
import { AuthShell } from "../components/AuthShell";
import { authMode } from "../api/session";
import { AuthFlow, type AuthFlowMode } from "../components/AuthFlow";
import { useAppState } from "../lib/appState";

export default function Signup() {
  const { show } = useAppState();
  const [flowMode, setFlowMode] = useState<AuthFlowMode>("signup");
  return (
    <AuthShell from="signup">
        <div className="dd-auth-col">
          {authMode === "backend" ? (
            <AuthFlow mode={flowMode} onModeChange={setFlowMode} />
          ) : (
          <div className="fb-mkt-auth-form">
            <div className="fb-mkt-eyebrow is-plain">Request access</div>
            <h2>Ask the DuitDuit administrator to provision your account.</h2>
            <p className="fb-mkt-fine">The administrator creates your Supabase Auth user and assigns one backend-controlled DuitDuit role.</p>
            <button className="fb-mkt-btn is-accent is-lg" style={{ width: "100%", justifyContent: "center" }} type="button" onClick={() => show("login")}>Return to login</button>
          </div>
          )}
        </div>
    </AuthShell>
  );
}
