// What DuitDuit reads, and how. Statuses say exactly what is built: a live
// connector, a mapped file import, or preparation without a live link.

type Status = "live" | "import" | "prepares";

const SOURCES: { name: string; what: string; status: Status; glyph: string }[] = [
  { name: "Bank statements", what: "Opening balance and every line in and out", status: "import", glyph: "M4 10h16M6 10v7m4-7v7m4-7v7m4-7v7M3 20h18M12 4l9 4H3z" },
  { name: "Bills and purchase orders", what: "What you owe, and when", status: "import", glyph: "M7 3h10v18l-2.5-1.5L12 21l-2.5-1.5L7 21zM10 8h4m-4 4h4" },
  { name: "Payroll", what: "Run totals; each person's line stays with HR", status: "import", glyph: "M8 8a4 4 0 1 0 8 0 4 4 0 1 0-8 0M4 21c0-4 4-6 8-6s8 2 8 6" },
  { name: "Sales and marketplace payouts", what: "Pipeline, payouts and marketing spend", status: "import", glyph: "M4 19l5-6 4 3 7-9M15 7h5v5" },
  { name: "LHDN e-invoices", what: "MyInvois-ready checks and PDFs; submission is not connected", status: "prepares", glyph: "M6 3h9l3 3v15H6zM9 13l2 2 4-4" },
  { name: "Gmail", what: "Reads the inbox you connect; sends only what you approve", status: "live", glyph: "M3 6h18v12H3zM3 7l9 7 9-7" },
  { name: "Telegram", what: "Snap a receipt to capture it; get the morning briefing", status: "live", glyph: "M21 4L3 11l6 2 2 6 3-4 5 4z" },
  { name: "Lenders", what: "A Passport link they can open and verify", status: "live", glyph: "M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1m-2 4a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1" },
];

const LABEL: Record<Status, string> = { live: "Live connector", import: "File import", prepares: "Prepares, not connected" };

export function SourcesGrid() {
  return (
    <ul className="lv-sources" aria-label="What DuitDuit reads">
      {SOURCES.map((s) => (
        <li key={s.name}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={s.glyph} /></svg>
          <strong>{s.name}</strong>
          <span>{s.what}</span>
          <em className={"is-" + s.status}>{LABEL[s.status]}</em>
        </li>
      ))}
    </ul>
  );
}
