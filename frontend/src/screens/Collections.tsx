import { useCallback, useEffect, useMemo, useState, type DragEvent } from "react";
import { Sidebar, AppTopBar } from "../components/Nav";
import { SectionTabs } from "../components/SectionTabs";
import { SavedViewsBar } from "../components/SavedViewsBar";
import { RecordPanel, Who } from "../components/RecordPanel";
import { useAuth } from "../auth/AuthProvider";
import { useAppState } from "../lib/appState";
import { useI18n } from "../lib/i18n";
import { ApiError, friendlyLoadError } from "../api/client";
import { ringgit } from "../api/topicE";
import { displayCase, isPlaceholderName } from "../lib/customerAggregation";
import {
  askForReminder,
  clearHold,
  fetchBoard,
  fetchHolds,
  NO_FILTERS,
  setHold,
  type BoardCard,
  type BoardStage,
  type CollectionsBoard,
  type Hold,
  type HoldKind,
  type SavedViewFilters,
} from "../api/collaboration";
import "./Collections.css";

const STAGE_LABEL: Record<BoardStage, string> = {
  later: "Later",
  due_soon: "Due in 14 days",
  overdue: "Overdue",
  on_hold: "On hold",
  reminder: "Awaiting approval",
  paid: "Paid (last 30 days)",
};
const STAGE_TONE: Record<BoardStage, string> = {
  later: "grey", due_soon: "blue", overdue: "red", on_hold: "amber", reminder: "blue", paid: "green",
};
const HOLD_LABEL: Record<HoldKind, string> = { disputed: "Disputed", promised: "Promised to pay", paused: "Customer paused" };
const WORK_ROLES = new Set(["finance_ops", "owner_director"]);
const MOVABLE: BoardStage[] = ["due_soon", "overdue", "later"];
const OPEN: BoardStage[] = ["due_soon", "overdue", "later", "on_hold", "reminder"];

function shortDate(iso: string | null): string {
  return iso ? new Date(iso + "T00:00:00").toLocaleDateString("en-MY", { day: "numeric", month: "short" }) : "—";
}

function isoDaysAhead(days: number): string {
  const day = new Date();
  day.setDate(day.getDate() + days);
  return `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, "0")}-${String(day.getDate()).padStart(2, "0")}`;
}

function customerName(card: BoardCard, tx: (s: string) => string): string {
  return isPlaceholderName(card.customer_label) ? tx("Protected customer") : displayCase(card.customer_label);
}

/** The chips a card shows: how late it is, and why nobody is chasing it. */
function StatusChips({ card }: { card: BoardCard }) {
  const { tx } = useI18n();
  const chips: [string, string][] = [];
  if (card.days_overdue > 0) chips.push(["is-red", tx("{n} days overdue", { n: card.days_overdue })]);
  else if (card.stage === "paid") chips.push(["is-green", tx("Paid")]);
  else chips.push(["is-plain", tx("Due {date}", { date: shortDate(card.due_date) })]);
  if (card.hold) {
    chips.push(["is-amber", card.hold.kind === "promised"
      ? tx("Promised by {date}", { date: shortDate(card.hold.until) })
      : tx(HOLD_LABEL[card.hold.kind])]);
  }
  if (card.promise_broken_on) chips.push(["is-red is-outline", tx("Promise missed {date}", { date: shortDate(card.promise_broken_on) })]);
  if (card.stage === "reminder") chips.push(["is-blue", tx("Reminder waiting")]);
  return <div className="rc-chips">{chips.map(([tone, text]) => <span key={text} className={"rc-chip " + tone}>{text}</span>)}</div>;
}

function Card({ card, canMove, onOpen, onDragStart }: {
  card: BoardCard;
  canMove: boolean;
  onOpen: (card: BoardCard) => void;
  onDragStart: (event: DragEvent, card: BoardCard) => void;
}) {
  const { tx } = useI18n();
  const movable = canMove && MOVABLE.includes(card.stage);
  // Ledger lines without a reference are named by due date, already shown in the chips.
  const label = card.label.startsWith("Invoice due") ? tx("Invoice") : card.label;
  return (
    <li className={"dd-card is-" + card.stage} draggable={movable} onDragStart={(e) => onDragStart(e, card)}>
      <button type="button" className="dd-card-open" onClick={() => onOpen(card)} aria-label={tx("Open {label}", { label })}>
        <span className="dd-card-top">
          <span className="dd-card-label">{label}</span>
          <span className="dd-card-amount">{ringgit(card.amount)}</span>
        </span>
        <Who name={customerName(card, tx)} />
        <StatusChips card={card} />
      </button>
    </li>
  );
}

/** One receivable as a record: what it is, then what a person can do with it. */
function ReceivablePanel({ card, canWork, onClose, onChanged }: {
  card: BoardCard;
  canWork: boolean;
  onClose: () => void;
  onChanged: (notice: string) => void;
}) {
  const { tx } = useI18n();
  const { show } = useAppState();
  const [busy, setBusy] = useState(false);
  const [promise, setPromise] = useState(false);
  // A customer who is late promises a date soon; one not yet due usually the due date.
  const [until, setUntil] = useState(() =>
    card.days_overdue === 0 && card.due_date && card.due_date <= isoDaysAhead(90) && card.due_date >= isoDaysAhead(0)
      ? card.due_date
      : isoDaysAhead(7));
  const [error, setError] = useState<string | null>(null);
  const label = card.label.startsWith("Invoice due") ? tx("Invoice") : card.label;
  const open = card.stage !== "paid";

  const act = async (work: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError(null);
    try {
      await work();
      onChanged(done);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "";
      setError(code === "promise_date_out_of_range" ? tx("Choose a date from today to 90 days ahead.") : friendlyLoadError(code));
    } finally {
      setBusy(false);
    }
  };

  return (
    <RecordPanel kicker={tx("Receivable")} title={`${label} · ${ringgit(card.amount)}`} onClose={onClose}>
      <section className="rc-section">
        <h3>{tx("Details")}</h3>
        <dl className="rc-attrs">
          <dt>{tx("Customer")}</dt><dd><Who name={customerName(card, tx)} /></dd>
          <dt>{tx("Amount")}</dt><dd>{ringgit(card.amount)}</dd>
          <dt>{tx("Due")}</dt><dd>{shortDate(card.due_date)}</dd>
          <dt>{tx("Status")}</dt><dd><StatusChips card={card} /></dd>
          <dt>{tx("Column")}</dt><dd>{tx(STAGE_LABEL[card.stage])}</dd>
        </dl>
      </section>
      {canWork && open && (
        <section className="rc-section">
          <h3>{tx("Actions")}</h3>
          <div className="rc-actions">
            {MOVABLE.includes(card.stage) && (
              <button type="button" className="rc-action is-primary" disabled={busy}
                onClick={() => void act(() => askForReminder(card.ref), tx("A reminder for {label} is waiting for approval in the review inbox. Nothing has been sent.", { label }))}>
                {tx("Ask for a reminder")}<small>{tx("A person approves it first")}</small>
              </button>
            )}
            {card.stage === "reminder" && (
              <button type="button" className="rc-action" onClick={() => show("inbox")}>{tx("Open in review inbox")}<small>→</small></button>
            )}
            {card.hold ? (
              <button type="button" className="rc-action" disabled={busy}
                onClick={() => void act(() => clearHold(card.hold!.target), tx("Chasing resumed for {label}.", { label }))}>
                {card.hold.kind === "paused" ? tx("Resume chasing this customer") : tx("Resume chasing")}
                <small>{tx("Reminders and automations apply again")}</small>
              </button>
            ) : (
              <>
                <button type="button" className="rc-action" disabled={busy}
                  onClick={() => void act(() => setHold(card.ref, "disputed"), tx("{label} is marked as disputed. Nobody chases it until the dispute is resolved.", { label }))}>
                  {tx("Mark as disputed")}<small>{tx("Stops reminders; keeps its age")}</small>
                </button>
                {promise ? (
                  <form className="rc-inline" onSubmit={(e) => { e.preventDefault(); void act(() => setHold(card.ref, "promised", until), tx("Promise recorded. Chasing resumes after {date} if it is still unpaid.", { date: shortDate(until) })); }}>
                    <label>{tx("Customer promised to pay by")}
                      <input type="date" value={until} min={isoDaysAhead(0)} max={isoDaysAhead(90)} onChange={(e) => setUntil(e.target.value)} required />
                    </label>
                    <button type="submit" className="rc-mini" disabled={busy}>{tx("Save")}</button>
                    <button type="button" className="rc-mini" onClick={() => setPromise(false)}>{tx("Cancel")}</button>
                  </form>
                ) : (
                  <button type="button" className="rc-action" disabled={busy} onClick={() => setPromise(true)}>
                    {tx("Record a promise to pay")}<small>{tx("Pauses chasing until that date")}</small>
                  </button>
                )}
                {card.customer_id !== null && (
                  <button type="button" className="rc-action" disabled={busy}
                    onClick={() => void act(() => setHold(`customer:${card.customer_id}`, "paused"), tx("Chasing is paused for {name}.", { name: customerName(card, tx) }))}>
                    {tx("Don't chase this customer")}<small>{tx("Every invoice of theirs")}</small>
                  </button>
                )}
              </>
            )}
          </div>
          {error && <p className="fb-inbox-error" role="alert">{error}</p>}
        </section>
      )}
      <p className="rc-note">{tx("Nothing is sent from here. Reminders are drafted for approval in the review inbox, and every change is recorded on the audit trail.")}</p>
    </RecordPanel>
  );
}

/** Everything nobody is chasing, and why, in one list. */
function HoldsPanel({ canWork, onClose, onChanged }: { canWork: boolean; onClose: () => void; onChanged: (notice: string) => void }) {
  const { tx } = useI18n();
  const [holds, setHolds] = useState<Hold[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    fetchHolds().then((h) => active && setHolds(h)).catch((e: Error) => active && setError(friendlyLoadError(e.message)));
    return () => { active = false; };
  }, []);
  const resume = async (hold: Hold) => {
    try {
      await clearHold(hold.target);
      setHolds((list) => (list ?? []).filter((h) => h.target !== hold.target));
      onChanged(tx("Chasing resumed for {label}.", { label: hold.kind === "paused" && isPlaceholderName(hold.label) ? tx("Protected customer") : hold.label }));
    } catch (e) {
      setError(friendlyLoadError(e instanceof ApiError ? e.code : ""));
    }
  };
  return (
    <RecordPanel kicker={tx("Collections")} title={tx("Not being chased")} onClose={onClose}>
      <p className="rc-note">{tx("Disputed invoices, promises to pay and paused customers. They still count as owed and keep their age.")}</p>
      {error && <p className="fb-inbox-error" role="alert">{error}</p>}
      <ul className="rc-list">
        {holds === null && <li className="rc-list-empty">{tx("Loading…")}</li>}
        {holds?.length === 0 && <li className="rc-list-empty">{tx("Everything unpaid is being followed up.")}</li>}
        {holds?.map((hold) => (
          <li key={hold.target}>
            <div className="rc-list-main">
              {hold.kind === "paused" ? (
                <strong><Who name={isPlaceholderName(hold.customer_label) ? tx("Protected customer") : displayCase(hold.customer_label)} /></strong>
              ) : (
                <>
                  <strong>{hold.label}</strong>
                  <Who name={isPlaceholderName(hold.customer_label) ? tx("Protected customer") : displayCase(hold.customer_label)} />
                </>
              )}
              <span>
                <span className="rc-chip is-amber">{tx(HOLD_LABEL[hold.kind])}</span>{" "}
                {hold.until && tx("until {date}", { date: shortDate(hold.until) })}
              </span>
            </div>
            {canWork && <button type="button" className="rc-mini" onClick={() => void resume(hold)}>{tx("Resume")}</button>}
          </li>
        ))}
      </ul>
    </RecordPanel>
  );
}

export default function Collections() {
  const { t, tx } = useI18n();
  const { identity } = useAuth();
  const canMove = WORK_ROLES.has(identity?.role ?? "");
  const [board, setBoard] = useState<CollectionsBoard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [filters, setFilters] = useState<SavedViewFilters>(NO_FILTERS);
  const [openRef, setOpenRef] = useState<string | null>(null);
  const [holdsOpen, setHoldsOpen] = useState(false);

  const load = useCallback(() => {
    fetchBoard().then((b) => { setBoard(b); setError(null); }).catch((e: Error) => setError(friendlyLoadError(e.message)));
  }, []);
  useEffect(() => { load(); }, [load]);

  const cards = useMemo(() => board?.columns.flatMap((c) => c.cards) ?? [], [board]);
  const opened = cards.find((c) => c.ref === openRef) ?? null;
  const closeCard = useCallback(() => setOpenRef(null), []);
  const closeHolds = useCallback(() => setHoldsOpen(false), []);
  const changed = (message: string) => { setNotice(message); load(); };

  const remind = async (card: BoardCard) => {
    setNotice(null);
    try {
      await askForReminder(card.ref);
      changed(tx("A reminder for {label} is waiting for approval in the review inbox. Nothing has been sent.", { label: card.label }));
    } catch (e) {
      setError(friendlyLoadError(e instanceof ApiError ? e.code : ""));
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
    const card = cards.find((c) => c.ref === ref);
    if (card && MOVABLE.includes(card.stage)) void remind(card);
  };

  const columns = useMemo(
    () => (board?.columns ?? []).filter((c) => filters.stages.length === 0 || filters.stages.includes(c.stage)),
    [board, filters.stages],
  );
  const owed = (board?.columns ?? []).filter((c) => OPEN.includes(c.stage)).reduce((sum, c) => sum + Number(c.total), 0);
  const late = (board?.columns ?? []).flatMap((c) => c.cards).filter((c) => c.days_overdue > 0).reduce((sum, c) => sum + Number(c.amount), 0);
  const held = board?.columns.find((c) => c.stage === "on_hold")?.cards.length ?? 0;

  return (
    <div className="fb-root fb-shell">
      <Sidebar current="collections" />
      <AppTopBar current="collections" />
      <header className="fb-app-header">
        <div className="fb-eyebrow">{t("nav.group.money")}</div>
        <h1>{t("nav.cashFinance")}</h1>
        <p>{tx("Every unpaid invoice in one place. Open a card to ask for a reminder, record a dispute or a promise to pay, or stop chasing a customer. A person approves every reminder before anything is sent.")}</p>
        <SectionTabs section="money" current="collections" />
      </header>
      <div className="fb-page-body">
        {board?.data_mode === "stub" && <div className="fb-callout">{t("cash.stub")}</div>}
        {error && <div className="fb-callout" role="alert">{error}</div>}
        {notice && <div className="fb-callout" role="status">{notice}</div>}
        {board && (
          <div className="dd-board-summary">
            <div><span>{tx("Owed to you")}</span><strong>{ringgit(String(owed))}</strong></div>
            <div><span>{tx("Overdue")}</span><strong className={late ? "is-late" : undefined}>{ringgit(String(late))}</strong></div>
            <button type="button" onClick={() => setHoldsOpen(true)}>
              <span>{tx("Not being chased")}</span><strong>{held}</strong>
            </button>
          </div>
        )}
        <div className="dd-board-toolbar">
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
                    <h2><span className={"dd-dot is-" + STAGE_TONE[column.stage]} aria-hidden="true" />{tx(STAGE_LABEL[column.stage])}<span className="dd-count">{column.cards.length}</span></h2>
                    <span className="dd-column-total">{ringgit(column.total)}</span>
                  </header>
                  {column.cards.length === 0 ? (
                    <p className="dd-column-empty">{target ? tx("Drop a card here to ask for a reminder.") : tx("Nothing here.")}</p>
                  ) : (
                    <ul>
                      {column.cards.map((card) => (
                        <Card key={card.ref} card={card} canMove={canMove} onOpen={(c) => setOpenRef(c.ref)} onDragStart={onDragStart} />
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </div>
      {opened && <ReceivablePanel key={opened.ref} card={opened} canWork={canMove} onClose={closeCard} onChanged={(m) => { changed(m); setOpenRef(null); }} />}
      {holdsOpen && <HoldsPanel canWork={canMove} onClose={closeHolds} onChanged={(m) => { setNotice(m); load(); }} />}
    </div>
  );
}
