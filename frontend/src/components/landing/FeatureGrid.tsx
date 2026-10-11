import "./Platform.css";

// Attio-style bento of smaller capabilities, each with a tiny picture of itself.
// Every card describes something built; the forecast check says it is not
// measured yet.

export function FeatureGrid() {
  return (
    <div className="fg">
      <article className="fg-card is-wide">
        <div className="fg-art fg-views" aria-hidden="true">
          <span className="is-on">Urgent + High · overdue ≥ RM10,000</span><span>Due soon</span><span>Unconfirmed 🔒</span>
        </div>
        <h3>Saved views</h3>
        <p>Keep the lists you check every day, privately or shared with the team.</p>
      </article>
      <article className="fg-card">
        <div className="fg-art fg-note" aria-hidden="true">RM24,500 overdue across 1 invoice; the oldest is 20 days late.</div>
        <h3>Risk notes</h3>
        <p>One sentence per customer, written by rules from its records, never by a model.</p>
      </article>
      <article className="fg-card">
        <div className="fg-art fg-chat" aria-hidden="true"><b>DuitDuit</b> 3 items wait for review (Finance 2, Owner 1)</div>
        <h3>Slack and WhatsApp</h3>
        <p>A one-line notice when work is waiting. No titles, amounts or names.</p>
      </article>
      <article className="fg-card">
        <div className="fg-art fg-zh" aria-hidden="true">中文 · BM · EN</div>
        <h3>In Chinese, Malay and English</h3>
        <p>The main screens read in Chinese, and goals typed in any of the three reach the right agent.</p>
      </article>
      <article className="fg-card">
        <div className="fg-art fg-check" aria-hidden="true">
          <span><b>Forecast check</b> Not measured yet</span><span>First comparison when a statement covers the day</span>
        </div>
        <h3>A forecast that keeps score</h3>
        <p>Each day's forecast is kept and compared with the bank balance once a statement covers that day.</p>
      </article>
    </div>
  );
}
