import { useEffect, useState } from "react";
import { fetchMySignIns, type SignIn } from "../api/security";
import { useI18n } from "../lib/i18n";
import "./records.css";

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-MY", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Your own recent sign-ins, so you can spot one that was not you. */
export function SignInsPanel() {
  const { tx } = useI18n();
  const [rows, setRows] = useState<SignIn[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    fetchMySignIns().then((r) => active && setRows(r)).catch(() => active && setFailed(true));
    return () => { active = false; };
  }, []);
  return (
    <section className="fb-settings-section">
      <h2>{tx("Your recent sign-ins")}</h2>
      <ul className="rc-list">
        {rows === null && !failed && <li className="rc-list-empty">{tx("Loading…")}</li>}
        {failed && <li className="rc-list-empty">{tx("Sign-ins could not be loaded.")}</li>}
        {rows?.length === 0 && <li className="rc-list-empty">{tx("No sign-ins recorded yet.")}</li>}
        {rows?.map((row) => (
          <li key={`${row.at}-${row.browser}-${row.system}`}>
            <div className="rc-list-main">
              <strong>{tx("{browser} on {system}", { browser: row.browser, system: row.system })}{row.new_device && <span className="rc-chip is-amber" style={{ marginLeft: ".4rem" }}>{tx("New device")}</span>}</strong>
              <span>{when(row.at)} · {row.method === "demo" ? tx("Demo sign-in") : tx("Password and emailed code")}</span>
            </div>
          </li>
        ))}
      </ul>
      {rows?.some((row) => row.method === "demo") && (
        <p className="fb-fine">{tx("The demo company is shared, so this list includes other visitors' sign-ins, and its password and sign-out everywhere are locked.")}</p>
      )}
      <p className="fb-fine">{tx("If a sign-in was not you, change your password and use Sign out everywhere. Only the browser type and system are kept, never your address.")}</p>
    </section>
  );
}
