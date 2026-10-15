import { useState, type KeyboardEvent } from "react";
import "./Platform.css";

// Attio-style "explore the platform": a row of tabs and one app window that
// changes with them. Each window is drawn from the synthetic demo company's own
// figures (seed/topic_e.py and app/stubs), and says it is an illustration.

type Tab = { id: string; label: string; title: string; body: string };

const TABS: Tab[] = [
  { id: "collections", label: "Collections", title: "Who owes what, at a glance.", body: "Every unpaid invoice in one column. Drag one to Reminder and the Collections agent drafts it for approval." },
  { id: "inbox", label: "Review inbox", title: "Every proposal waits for a person.", body: "Each item shows what the agent prepared, the records it used and what approving does. People comment, @mention a colleague and decide. Money needs two of them." },
  { id: "automations", label: "Automations", title: "Follow-up, prepared on time.", body: "A reminder sequence moves from friendly to firm to a call, one approved step at a time." },
  { id: "ai", label: "AI connections", title: "Ask from your own AI tool.", body: "Connect Claude, or Chinese tools on DeepSeek, Qwen or Kimi, over MCP. Read-only, masked, recorded." },
];

function Window({ crumb, children }: { crumb: string; children: React.ReactNode }) {
  return (
    <div className="pl-window" role="img" aria-label={`Illustration: ${crumb}, with the synthetic demo company`}>
      <div className="pl-chrome">
        <span className="pl-dots" aria-hidden="true"><i /><i /><i /></span>
        <span className="pl-crumb">SYNTHETIC Importer <b>›</b> {crumb}</span>
      </div>
      <div className="pl-body" aria-hidden="true">{children}</div>
    </div>
  );
}

function Collections() {
  const columns = [
    { name: "Due in 14 days", total: "RM42,700", cards: [["INV-1041", "RM24,500", "Due 20 Oct"], ["INV-1043", "RM18,200", "Due 30 Oct"]] },
    { name: "Overdue", total: "RM31,000", cards: [["INV-1047", "RM31,000", "9 days overdue"]], tone: "is-late" },
    { name: "Reminder", total: "RM42,000", cards: [["INV-1052", "RM42,000", "Waiting for the owner"]], tone: "is-wait" },
    { name: "Paid", total: "RM52,000", cards: [["Customer D", "RM52,000", "Paid 25 Sep"]], tone: "is-paid" },
  ];
  return (
    <Window crumb="Collections board">
      <div className="pl-board">
        {columns.map((c) => (
          <div key={c.name} className={"pl-col " + (c.tone ?? "")}>
            <div className="pl-col-head"><b>{c.name}</b><span>{c.total}</span></div>
            {c.cards.map(([label, amount, when]) => (
              <div key={label} className="pl-card"><b>{amount}</b><span>{label}</span><em>{when}</em></div>
            ))}
          </div>
        ))}
      </div>
    </Window>
  );
}

function Inbox() {
  return (
    <Window crumb="Review inbox">
      <div className="pl-inbox">
        <ul className="pl-list">
          <li className="is-on"><i className="pl-lvl">L2</i><span>Send 3 approved reminders</span><em>Owner</em></li>
          <li><i className="pl-lvl is-l3">L3</i><span>Approve the October payroll run</span><em>Owner</em></li>
          <li><i className="pl-lvl">L1</i><span>Review 3 reminder drafts</span><em>Finance</em></li>
          <li><i className="pl-lvl">L1</i><span>Approve PO-778 · CNY 60,000</span><em>Purchasing</em></li>
        </ul>
        <div className="pl-detail">
          <b>Send 3 approved reminders</b>
          <span className="pl-muted">External action: the owner approves before anything is sent.</span>
          <div className="pl-thread">
            <div><i className="pl-av is-finance">F</i><p><mark>@Owner</mark> Customer C disputed the cartons, hold their reminder?</p></div>
            <div><i className="pl-av is-owner">O</i><p>Approved for A and B. I'll call ‹name› at C first.</p></div>
          </div>
          <div className="pl-actions"><span className="pl-btn is-solid">Approve</span><span className="pl-btn">Reject</span></div>
        </div>
      </div>
    </Window>
  );
}

function Automations() {
  const steps = [
    ["7 days overdue", "Friendly reminder", "Approved", "is-done"],
    ["14 days overdue", "Firm reminder", "Waiting for the owner", "is-wait"],
    ["28 days overdue", "Call the customer", "Not due yet", ""],
  ];
  return (
    <Window crumb="Company settings › Automations">
      <div className="pl-auto">
        <div className="pl-rule"><span className="pl-muted">When</span> an invoice is at least <b>7 days</b> overdue <span className="pl-muted">then</span> run the <b>reminder sequence</b></div>
        <ol className="pl-steps">
          {steps.map(([when, what, status, tone]) => (
            <li key={what} className={tone}><i /><div><b>{what}</b><span>{when}</span></div><em>{status}</em></li>
          ))}
        </ol>
        <p className="pl-muted">Checked every 15 minutes. Nothing is sent or paid by an automation.</p>
      </div>
    </Window>
  );
}

function Ai() {
  return (
    <Window crumb="An AI tool connected over MCP">
      <div className="pl-chat">
        <div className="pl-msg is-user">这个月现金够发工资吗？</div>
        <div className="pl-tool"><span>get_cash_forecast</span> horizon_days: 90 <em>read-only</em></div>
        <div className="pl-msg">够发工资，但第 23 天现金会降到 RM20,560，比最低余额 RM50,000 少 RM29,440。当天有工资 RM62,000 和一笔 CNY 98,000 的采购付款。可以在 DuitDuit 里请催款智能体提前催收。</div>
        <div className="pl-muted">The answer comes from DuitDuit's figures; the AI tool cannot approve, send or pay.</div>
      </div>
    </Window>
  );
}

const VIEWS: Record<string, () => React.ReactElement> = { collections: Collections, inbox: Inbox, automations: Automations, ai: Ai };

export function PlatformTabs() {
  const [current, setCurrent] = useState(TABS[0].id);
  const tab = TABS.find((t) => t.id === current) ?? TABS[0];
  const View = VIEWS[tab.id];
  const onKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const next = TABS[(index + (event.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length];
    setCurrent(next.id);
    document.getElementById(`pl-tab-${next.id}`)?.focus();
  };
  return (
    <div className="pl">
      <div className="pl-tabs" role="tablist" aria-label="Product">
        {TABS.map((t, i) => (
          <button key={t.id} id={`pl-tab-${t.id}`} type="button" role="tab" aria-selected={t.id === current} aria-controls="pl-panel" tabIndex={t.id === current ? 0 : -1}
            className={t.id === current ? "is-on" : undefined} onClick={() => setCurrent(t.id)} onKeyDown={(e) => onKey(e, i)}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="pl-stage" id="pl-panel" role="tabpanel" aria-labelledby={`pl-tab-${tab.id}`}>
        <div className="pl-copy">
          <h3>{tab.title}</h3>
          <p>{tab.body}</p>
        </div>
        <View />
      </div>
      <p className="lv-fine">Illustrations drawn from the synthetic demo company's figures.</p>
    </div>
  );
}
