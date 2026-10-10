import { useEffect, useState } from "react";
import { onServerReachability, serverReachable, trackedFetch } from "../lib/connectivity";
import "./ServerStatusBanner.css";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/** One sentence when the API can't be reached, with a way to try again. */
export function ServerStatusBanner() {
  const [reachable, setReachable] = useState(serverReachable());
  const [checking, setChecking] = useState(false);

  useEffect(() => onServerReachability(setReachable), []);

  if (reachable) return null;

  const retry = async () => {
    setChecking(true);
    try {
      const response = await trackedFetch(`${BASE_URL}/health`, { cache: "no-store" });
      if (response.ok) window.location.reload();
    } catch {
      // Still unreachable: the banner stays.
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="dd-offline" role="alert">
      <span>DuitDuit can't reach its server right now. Your data is safe. Try again in a moment.</span>
      <button type="button" onClick={() => void retry()} disabled={checking}>
        {checking ? "Checking…" : "Try again"}
      </button>
    </div>
  );
}
