import { useEffect, useState, type FormEvent } from "react";
import { addComment, fetchComments, type ReviewComment } from "../api/collaboration";
import { ApiError, friendlyActionError } from "../api/client";
import type { JobFunction } from "../api/topicE";
import { useI18n } from "../lib/i18n";
import { JOB_LABELS } from "../lib/jobFunctions";
import { Avatar } from "./Collaboration";

const ROLE_JOB: Record<string, JobFunction> = {
  owner_director: "owner",
  finance_ops: "finance",
  compliance: "compliance",
  general_employee: "sales",
};
const ROLE_LABEL: Record<string, string> = {
  owner_director: "Owner",
  finance_ops: "Finance",
  compliance: "Compliance",
  general_employee: "Team member",
};
const MENTIONABLE: JobFunction[] = ["owner", "finance", "operations", "sales", "customer_service", "procurement", "hr", "compliance"];

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-MY", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

/**
 * The discussion on one review item. People write comments and @mention a
 * position; a mention is a notification, never an approval. Personal details are
 * stored and shown as placeholders such as ‹name›, and authors appear by role.
 */
export function ReviewComments({ actionId }: { actionId: string }) {
  const { tx } = useI18n();
  const [comments, setComments] = useState<ReviewComment[] | null>(null);
  const [text, setText] = useState("");
  const [mentions, setMentions] = useState<JobFunction[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // The inbox remounts this per item (key={actionId}), so state starts empty.
    let active = true;
    fetchComments(actionId)
      .then((rows) => active && setComments(rows))
      .catch(() => active && setComments([]));
    return () => { active = false; };
  }, [actionId]);

  const toggle = (job: JobFunction) => setMentions((list) => (list.includes(job) ? list.filter((j) => j !== job) : [...list, job]));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const comment = await addComment(actionId, text.trim(), mentions);
      setComments((list) => [...(list ?? []), comment]);
      setText("");
      setMentions([]);
    } catch (e) {
      const code = e instanceof ApiError ? e.code : e instanceof Error ? e.message : "";
      setError(code === "comment_quarantined"
        ? tx("That comment reads like an instruction to the AI, so it was blocked. Rephrase it as a note to people.")
        : friendlyActionError(code));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="dd-comments">
      <div className="fb-inbox-label">{tx("Comments")}</div>
      {comments === null && <p className="fb-inbox-muted">{tx("Loading…")}</p>}
      {comments !== null && comments.length === 0 && <p className="fb-inbox-muted">{tx("No comments yet. Ask a question or @mention a position.")}</p>}
      {comments !== null && comments.length > 0 && (
        <ol className="dd-comment-list">
          {comments.map((c) => (
            <li key={c.id}>
              <Avatar job={ROLE_JOB[c.author_role]} label={ROLE_LABEL[c.author_role] ?? c.author_role} />
              <div>
                <div className="dd-comment-head">
                  <strong>{c.by_me ? tx("You") : tx(ROLE_LABEL[c.author_role] ?? c.author_role)}</strong>
                  <time dateTime={c.created_at}>{when(c.created_at)}</time>
                </div>
                <p>
                  {c.mentions.map((job) => <span key={job} className="dd-mention">@{tx(JOB_LABELS[job])}</span>)}
                  {c.text}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
      <form className="dd-comment-form" onSubmit={(e) => void submit(e)}>
        <label className="fb-sr-only" htmlFor={`comment-${actionId}`}>{tx("Write a comment")}</label>
        <textarea id={`comment-${actionId}`} rows={2} maxLength={1000} value={text} placeholder={tx("Write a comment…")} onChange={(e) => setText(e.target.value)} />
        <div className="dd-comment-tools">
          <div className="dd-mention-picker" role="group" aria-label={tx("Mention a position")}>
            {MENTIONABLE.map((job) => (
              <button key={job} type="button" aria-pressed={mentions.includes(job)} className={mentions.includes(job) ? "is-on" : undefined} onClick={() => toggle(job)}>
                @{tx(JOB_LABELS[job])}
              </button>
            ))}
          </div>
          <button className="fb-btn fb-btn-solid" type="submit" disabled={busy || !text.trim()}>{busy ? tx("Posting…") : tx("Comment")}</button>
        </div>
        <p className="fb-inbox-muted dd-comment-note">{tx("Names, emails and phone numbers are hidden before the comment is saved.")}</p>
        {error && <div className="fb-inbox-error" role="alert">{error}</div>}
      </form>
    </div>
  );
}
