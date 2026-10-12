import { useEffect, useState } from "react";
import { fetchPolicyChecks, type PolicyCheck } from "../api/insights";
import { useI18n } from "../lib/i18n";
import "./records.css";

const NAMES: Record<PolicyCheck["name"], string> = {
  evidence: "Evidence",
  owner_escalation: "Owner escalation",
  two_person_rule: "Two-person rule",
  holds: "Holds on chasing",
  anomalies: "Unusual activity",
};
const TONE: Record<PolicyCheck["status"], [string, string]> = {
  pass: ["is-green", "Pass"],
  warn: ["is-amber", "Check"],
  fail: ["is-red", "Stop"],
};

/** The checker agent's findings on one review item: it adds information, never decides. */
export function CheckerPanel({ actionId }: { actionId: string }) {
  const { tx } = useI18n();
  const [checks, setChecks] = useState<PolicyCheck[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    fetchPolicyChecks(actionId).then((c) => active && setChecks(c)).catch(() => active && setFailed(true));
    return () => { active = false; };
  }, [actionId]);
  if (failed) return null;
  const problems = (checks ?? []).filter((c) => c.status !== "pass").length;
  return (
    <section className="rc-section dd-checker" aria-label={tx("Checker agent")}>
      <h3>
        {tx("Checker agent")}{" "}
        {checks && <span className={"rc-chip " + (problems ? "is-amber" : "is-green")}>{problems ? tx("{n} to look at", { n: problems }) : tx("All checks passed")}</span>}
      </h3>
      {checks === null ? (
        <p className="rc-note">{tx("Checking…")}</p>
      ) : (
        <ul className="rc-list">
          {checks.map((c) => {
            const [tone, label] = TONE[c.status];
            return (
              <li key={c.name}>
                <span className={"rc-chip " + tone}>{tx(label)}</span>
                <div className="rc-list-main"><strong>{tx(NAMES[c.name])}</strong><span>{tx(c.detail)}</span></div>
              </li>
            );
          })}
        </ul>
      )}
      <p className="rc-note">{tx("A second agent checks every item against company policy. It cannot approve, reject or change anything.")}</p>
    </section>
  );
}
