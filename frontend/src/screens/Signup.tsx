import { useState } from "react";
import { AuthStory } from "../components/AuthStory";
import { authMode } from "../api/session";
import { AuthFlow, type AuthFlowMode } from "../components/AuthFlow";
import { useAppState } from "../lib/appState";

export default function Signup() {
  const { show } = useAppState();
  const [flowMode, setFlowMode] = useState<AuthFlowMode>("signup");
  return (
    <div className="fb-root fb-mkt lx lx-auth">
      <div className="fb-mkt-auth-wrap">
        <AuthStory
          from="signup"
          title="Set up your company's copilot."
          body="Access follows a verified identity and the role your company assigns. Nobody can give themselves more."
        />
        <div className="fb-mkt-auth-form-wrap">
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
      </div>
    </div>
  );
}
