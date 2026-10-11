import { useEffect, useState } from "react";
import { fetchSavedViews, removeView, saveView, type SavedView, type SavedViewFilters, type SavedViewScreen } from "../api/collaboration";
import { ApiError, friendlyLoadError } from "../api/client";
import { ringgit } from "../api/topicE";
import { useAuth } from "../auth/AuthProvider";
import { useI18n } from "../lib/i18n";
import "../screens/Collections.css";

const PRIORITY: Record<string, string> = { urgent: "Urgent", high: "High", monitoring: "Monitoring", healthy: "Healthy" };
const STAGE: Record<string, string> = { later: "Later", due_soon: "Due soon", overdue: "Overdue", reminder: "Reminder", paid: "Paid" };

/** A view's name, written from its filters; views carry no free text. */
function viewName(filters: SavedViewFilters, tx: (s: string, v?: Record<string, string | number>) => string): string {
  const parts: string[] = [];
  if (filters.priorities.length) parts.push(filters.priorities.map((p) => tx(PRIORITY[p])).join(" + "));
  if (filters.stages.length) parts.push(filters.stages.map((s) => tx(STAGE[s])).join(" + "));
  if (filters.min_overdue) parts.push(tx("overdue ≥ {amount}", { amount: ringgit(filters.min_overdue) }));
  if (filters.min_outstanding) parts.push(tx("outstanding ≥ {amount}", { amount: ringgit(filters.min_outstanding) }));
  if (filters.unconfirmed_only) parts.push(tx("unconfirmed"));
  return parts.length ? parts.join(" · ") : tx("Everything");
}

function isEmpty(filters: SavedViewFilters): boolean {
  return !filters.priorities.length && !filters.stages.length && !filters.min_overdue && !filters.min_outstanding && !filters.unconfirmed_only;
}

/** Saved filters for a screen: apply one, save the current filters, remove your own. */
export function SavedViewsBar({ screen, filters, onApply }: { screen: SavedViewScreen; filters: SavedViewFilters; onApply: (f: SavedViewFilters) => void }) {
  const { tx } = useI18n();
  const { identity } = useAuth();
  const isOwner = identity?.role === "owner_director";
  const [views, setViews] = useState<SavedView[]>([]);
  const [shared, setShared] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchSavedViews(screen).then((v) => active && setViews(v)).catch(() => undefined);
    return () => { active = false; };
  }, [screen]);

  const save = async () => {
    setError(null);
    try {
      const view = await saveView(screen, filters, shared);
      setViews((list) => [...list, view]);
    } catch (e) {
      setError(friendlyLoadError(e instanceof ApiError ? e.code : ""));
    }
  };

  const drop = async (id: string) => {
    setError(null);
    try {
      await removeView(id);
      setViews((list) => list.filter((v) => v.id !== id));
    } catch (e) {
      setError(friendlyLoadError(e instanceof ApiError ? e.code : ""));
    }
  };

  return (
    <div className="dd-views" role="group" aria-label={tx("Saved views")}>
      <span className="dd-views-label">{tx("Saved views")}</span>
      {views.map((view) => (
        <span key={view.id} className="dd-view">
          <button type="button" onClick={() => onApply(view.filters)} title={view.shared ? tx("Shared with the team") : tx("Only you")}>
            {viewName(view.filters, tx)}{view.shared ? "" : " 🔒"}
          </button>
          {(view.mine || (isOwner && view.shared)) && (
            <button type="button" className="dd-view-remove" aria-label={tx("Remove view {name}", { name: viewName(view.filters, tx) })} onClick={() => void drop(view.id)}>×</button>
          )}
        </span>
      ))}
      {!isEmpty(filters) && (
        <>
          <button type="button" className="dd-view-save" onClick={() => void save()}>{tx("Save this view")}</button>
          <label><input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} />{tx("Share with the team")}</label>
          <button type="button" onClick={() => onApply({ priorities: [], stages: [], min_overdue: null, min_outstanding: null, unconfirmed_only: false })}>{tx("Clear filters")}</button>
        </>
      )}
      {error && <span className="fb-inbox-error" role="alert">{error}</span>}
    </div>
  );
}
