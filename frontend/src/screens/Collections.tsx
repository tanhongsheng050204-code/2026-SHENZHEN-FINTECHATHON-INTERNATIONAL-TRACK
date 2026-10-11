import { useCallback, useEffect, useMemo, useState, type DragEvent } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { SectionTabs } from "../components/SectionTabs";
import { SavedViewsBar } from "../components/SavedViewsBar";
import { useAuth } from "../auth/AuthProvider";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import { ApiError, friendlyLoadError } from "../api/client";
import { ringgit } from "../api/topicE";
import { displayCase, isPlaceholderName } from "../lib/customerAggregation";
import {
  askForReminder,
  fetchBoard,
  NO_FILTERS,
  type BoardCard,
  type BoardStage,
  type CollectionsBoard,
  type SavedViewFilters,
} from "../api/collaboration";
import "./Collections.css";

const STAGE_LABEL: Record<BoardStage, string> = {
  later: "Later",
  due_soon: "Due in 14 days",
  overdue: "Overdue",
  reminder: "Reminder waiting for approval",
  paid: "Paid (last 30 days)",
};
const WORK_ROLES = new Set(["finance_ops", "owner_director"]);
const MOVABLE: BoardStage[] = ["due_soon", "overdue", "later"];

function shortDate(iso: string | null): string {
  return iso ? new Date(iso + "T00:00:00").toLocaleDateString("en-MY", { day: "numeric", month: "short" }) : "—";
}

function Card({ card, canMove, busy, onRemind, onDragStart }: {
  card: BoardCard;
  canMove: boolean;
  busy: boolean;
  onRemind: (card: BoardCard) => void;
  onDragStart: (event: DragEvent, card: BoardCard) => void;
}) {
  const { tx } = useI18n();
  const { show } = useAppState();
  const movable = canMove && MOVABLE.includes(card.stage);
  return (
    <li className={"dd-card is-" + card.stage} draggable={movable} onDragStart={(e) => onDragStart(e, card)}>
      <div className="dd-card-top">
        <span className="dd-card-amount">{ringgit(card.amount)}</span>
        {/* Ledger lines without a reference are named by due date, already shown below. */}
        <span className="dd-card-label">{card.label.startsWith("Invoice due") ? tx("Invoice") : card.label}</span>
      </div>
      <div className="dd-card-who">{isPlaceholderName(card.customer_label) ? tx("Protected customer") : displayCase(card.customer_label)}</div>
      <div className="dd-card-when">
        {card.stage === "overdue"
          ? tx("{n} days overdue", { n: card.days_overdue })
          : card.stage === "paid"
            ? tx("Paid")
            : tx("Due {date}", { date: shortDate(card.due_date) })}
      </div>
      {movable && (
        <button type="button" className="dd-card-action" disabled={busy} onClick={() => onRemind(card)}>
          {busy ? tx("Preparing…") : tx("Ask for a reminder")}
        </button>
      )}
      {card.stage === "reminder" && (
        <button type="button" className="dd-card-action" onClick={() => show("inbox")}>{tx("Open in review inbox")}</button>
      )}
    </li>
  );
}

export default function Collections() {
  const { t, tx } = useI18n();
  const { identity } = useAuth();
  const canMove = WORK_ROLES.has(identity?.role ?? "");
  const [board, setBoard] = useState<CollectionsBoard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [filters, setFilters] = useState<SavedViewFilters>(NO_FILTERS);

  const load = useCallback(() => {
    fetchBoard().then((b) => { setBoard(b); setError(null); }).catch((e: Error) => setError(friendlyLoadError(e.message)));
  }, []);
  useEffect(() => { load(); }, [load]);

  const remind = async (card: BoardCard) => {
    setBusy(card.ref);
    setNotice(null);
    try {
      await askForReminder(card.ref);
      setNotice(tx("A reminder for {label} is waiting for approval in the review inbox. Nothing has been sent.", { label: card.label }));
      load();
    } catch (e) {
      setError(friendlyLoadError(e instanceof ApiError ? e.code : ""));
    } finally {
      setBusy(null);
    }
  };

  const onDragStart = (event: DragEvent, card: BoardCard) => {
    event.dataTransfer.setData("text/plain", card.ref);
    event.dataTransfer.effectAllowed = "move";
  };
  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    const ref = event.dataTransfer.getData("text/plain");
    const card = board?.columns.flatMap((c) => c.cards).find((c) => c.ref === ref);
    if (card && MOVABLE.includes(card.stage)) void remind(card);
  };

  const columns = useMemo(
    () => (board?.columns ?? []).filter((c) => filters.stages.length === 0 || filters.stages.includes(c.stage)),
    [board, filters.stages],
  );

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="collections" />
      <AppTopBar current="collections" />
      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.money")}</div>
        <h1>{t("nav.cashFinance")}</h1>
        <p>{tx("Every unpaid invoice in one place. Drag a card to Reminder, or press Ask for a reminder: the Collections agent drafts it and a person approves it before anything is sent.")}</p>
        <SectionTabs section="money" current="collections" />
      </header>
      <div className="fb-page-body">
        {board?.data_mode === "stub" && <div className="fb-callout">{t("cash.stub")}</div>}
        {error && <div className="fb-callout" role="alert">{error}</div>}
        {notice && <div className="fb-callout" role="status">{notice}</div>}
        <SavedViewsBar screen="collections" filters={filters} onApply={setFilters} />
        <div className="dd-board-filters" role="group" aria-label={tx("Show columns")}>
          <span className="dd-views-label">{tx("Show")}</span>
          {(Object.keys(STAGE_LABEL) as BoardStage[]).map((stage) => {
            const on = filters.stages.includes(stage);
            return (
              <button key={stage} type="button" aria-pressed={on} className={on ? "is-on" : undefined}
                onClick={() => setFilters((f) => ({ ...f, stages: on ? f.stages.filter((s) => s !== stage) : [...f.stages, stage] }))}>
                {tx(STAGE_LABEL[stage])}
              </button>
            );
          })}
        </div>
        {!board && !error && <div className="fb-callout">{tx("Loading…")}</div>}
        {board && (
          <div className="dd-board">
            {columns.map((column) => {
              const target = column.stage === "reminder" && canMove;
              return (
                <section
                  key={column.stage}
                  className={"dd-column is-" + column.stage + (target && dragOver ? " is-target" : "")}
                  aria-label={tx(STAGE_LABEL[column.stage])}
                  onDragOver={target ? (e) => { e.preventDefault(); setDragOver(true); } : undefined}
                  onDragLeave={target ? () => setDragOver(false) : undefined}
                  onDrop={target ? onDrop : undefined}
                >
                  <header>
                    <h2>{tx(STAGE_LABEL[column.stage])}</h2>
                    <span>{column.cards.length} · {ringgit(column.total)}</span>
                  </header>
                  {column.cards.length === 0 ? (
                    <p className="dd-column-empty">{target ? tx("Drop a card here to ask for a reminder.") : tx("Nothing here.")}</p>
                  ) : (
                    <ul>
                      {column.cards.map((card) => (
                        <Card key={card.ref} card={card} canMove={canMove} busy={busy === card.ref} onRemind={(c) => void remind(c)} onDragStart={onDragStart} />
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
