// Which roles may see each kind of protected value in clear text. Mirrors
// ACL_POLICY in backend/app/security/tokenize.py; the server enforces it, this
// only explains it. Everyone else sees a masked value, and each reveal is logged.
import { useI18n } from "../lib/i18n";

const ROWS: [string, string][] = [
  ["Names of people and companies", "Owner, Finance, Compliance, Staff"],
  ["Phone numbers and email addresses", "Owner, Finance, Compliance"],
  ["Bank account numbers", "Owner, Finance, Compliance"],
  ["Exact amounts (others see a range)", "Owner, Finance, Compliance"],
  ["Home and business addresses", "Owner, Compliance"],
  ["IC (NRIC) numbers", "Owner, Compliance"],
  ["Card numbers", "Compliance only"],
];

export function WhoCanSee() {
  const { tx } = useI18n();
  return (
    <details className="dd-whocansee">
      <summary>{tx("Who can see protected details?")}</summary>
      <p>{tx("DuitDuit replaces these values with tokens before any AI sees them. When an answer shows them, only these roles get the real value; everyone else sees it masked, and every reveal is logged.")}</p>
      <table>
        <thead><tr><th scope="col">{tx("Detail")}</th><th scope="col">{tx("Shown in full to")}</th></tr></thead>
        <tbody>
          {ROWS.map(([kind, who]) => <tr key={kind}><td>{tx(kind)}</td><td>{tx(who)}</td></tr>)}
        </tbody>
      </table>
      <p>{tx("To see one answer through every role: sign in as Compliance, ask a question, then press Compare policies under the answer. It shows side by side what the Owner, Finance and Staff would each see. No new AI call is made.")}</p>
    </details>
  );
}
