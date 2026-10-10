import { authMode } from "../api/session";
import { useAppState } from "../lib/appState";
import { Guilloche } from "./Guilloche";
import { LogoMark } from "./Logo";

const BACKEND_LOCKS = [
  { title: "Your password", body: "Checked by the identity provider, never stored by DuitDuit." },
  { title: "A code sent to your email", body: "Proves the inbox is still yours." },
  { title: "Your authenticator app", body: "Asked again before any money decision." },
];

const PROVIDER_LOCKS = [
  { title: "Your identity", body: "Verified by the identity provider before DuitDuit sees a request." },
  { title: "A role the server assigns", body: "The browser cannot choose or raise its own permissions." },
  { title: "A recorded trail", body: "Every disclosure and decision is kept on a hash chain." },
];

/** The left panel of the sign-in and sign-up pages: what protects this session. */
export function AuthStory({ title, body, from }: { title: string; body: string; from: "login" | "signup" }) {
  const { show, goToSecurity } = useAppState();
  const locks = authMode === "backend" ? BACKEND_LOCKS : PROVIDER_LOCKS;
  return (
    <aside className="lx-auth-story" aria-label="How your sign-in is protected">
      <Guilloche className="lx-auth-guilloche" />
      <button className="lx-auth-brand" type="button" onClick={() => show("landing")}>
        <LogoMark large />DuitDuit
      </button>
      <div className="lx-auth-copy">
        <h1>{title}</h1>
        <p>{body}</p>
      </div>
      <ol className="lx-auth-locks">
        {locks.map((lock) => (
          <li key={lock.title}>
            <strong>{lock.title}</strong>
            <span>{lock.body}</span>
          </li>
        ))}
      </ol>
      <button className="lx-auth-link" type="button" onClick={() => goToSecurity(from)}>How DuitDuit protects your data</button>
    </aside>
  );
}
