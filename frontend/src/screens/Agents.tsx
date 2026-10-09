import { useEffect, useRef, useState } from "react";
import { AgentRunPanel } from "../components/AgentRunPanel";
import { AssistantReply } from "../components/AssistantReply";
import { BriefingCard } from "../components/BriefingCard";
import { VoiceInput } from "../components/VoiceInput";
import { interpretCommand } from "../api/topicE";
import { useAuth } from "../auth/AuthProvider";
import { useAppState } from "../lib/appState";
import { useI18n, FB_UI_STRINGS } from "../lib/i18n";
import { FB_UNIFIED_FALLBACK } from "../data/sampleData";
import { Sidebar, AppTopBar } from "../components/Nav";
import { LogoMark } from "../components/Logo";
import {
  IntelligenceExperience,
  StandaloneExposureReceipt,
  StructuredCitationResults,
} from "../components/intelligence/IntelligenceExperience";
import { matchEinvoiceReadinessEmbed, resolveChatReply, type ChatReply } from "../components/embeds/ChatEmbeds";
import { listRecentConversations, recordConversationTurn, type RecentConversation } from "../lib/recentConversations";
import { OutreachComposerCard } from "../components/outreach/OutreachComposerCard";
import {
  askQuestion,
  ApiError,
  commitUpload,
  previewUpload,
  type QueryCitation,
  type CustomerIntelligenceBrief,
  type ExposureReceipt,
  type QueryIntent,
  type UploadCommitResponse,
  type UploadPreviewResponse,
} from "../api/client";

interface Message {
  id: number;
  from: "user" | "agent";
  text: string;
  timestamp: number;
  embed?: React.ReactNode;
  thinking?: boolean;
  protectedText?: string;
  citations?: QueryCitation[];
  showProtected?: boolean;
  mode?: string;
  queryIntent?: QueryIntent;
  rawQuestion?: string;
  modelQuestion?: string;
  turnId?: number;
  brief?: CustomerIntelligenceBrief;
  exposure?: ExposureReceipt;
  isFallback?: boolean;
}

interface ContextChip {
  label: string;
}

type UploadState = "idle" | "previewing" | "protected" | "committing" | "complete" | "failed";

// Reuses the same stroke paths as the Approvals/Search/e-Invoicing icons
// elsewhere in the app (Home cards, command palette) instead of emoji, so
// the suggestion chips match the rest of the product's icon language.
const ICON_APPROVALS = <path d="M9 12l2 2 4-4M12 3l8 4v5c0 4.5-3.2 8.5-8 10-4.8-1.5-8-5.5-8-10V7z" />;
const ICON_SEARCH = <><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></>;
const ICON_INVOICE = <path d="M6 2h9l3 3v17H6z M9 8h6M9 12h6M9 16h4" />;

const SUGGESTIONS = [
  { text: "Why are payment approvals being delayed, and what should we do next?", icon: ICON_APPROVALS },
  { text: "Summarize all approval-delay records and cite every source.", icon: ICON_APPROVALS },
  { text: "Which records have no assigned owner?", icon: ICON_SEARCH },
  { text: "How many high-priority approval delays came from email this week?", icon: ICON_APPROVALS },
  { text: "Which invoices need fixes before MyInvois submission?", icon: ICON_INVOICE },
];

let msgId = 1;
const now = () => Date.now();

export default function Agents() {
  const {
    askRole,
    sampleBanner,
    dismissSampleBanner,
    openApprovalRecommendation,
    pendingAskPrompt,
    clearPendingAskPrompt,
    currentCustomerKey,
    clearCustomerContext,
    displayName,
  } = useAppState();
  const { identity } = useAuth();
  const { lang, t } = useI18n();
  const [messages, setMessages] = useState<Message[]>([
    { id: msgId++, from: "agent", text: "Hi, I’m DuitDuit. Ask me about your records, or tell me what to do: “open cash flow”, “can I cover payroll this month?”, “approve the reminder drafts”. I always check with you before changing anything.", timestamp: now() },
  ]);
  const [input, setInput] = useState("");
  const [chips, setChips] = useState<ContextChip[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [uploadPreview, setUploadPreview] = useState<UploadPreviewResponse | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadCommitResponse | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [protectedTurnCount, setProtectedTurnCount] = useState(0);
  const [recentConversations, setRecentConversations] = useState<RecentConversation[]>(() => listRecentConversations());
  const [recentOpen, setRecentOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const lastMessageRef = useRef<HTMLDivElement>(null);
  const consumedHandoffRef = useRef<number | null>(null);
  const scopedCustomerId = currentCustomerKey?.startsWith("id:")
    ? Number(currentCustomerKey.slice(3))
    : null;
  const profileLabel = displayName || identity?.email || "You";
  const userInitial = profileLabel[0]?.toUpperCase() ?? "U";
  const formatTime = (ts: number) => new Date(ts).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      if (messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    });
  };

  // A finished answer can be much taller than the panel (headline, claims,
  // timeline, recommended action…) — scrolling to the container's absolute
  // bottom would crop its own heading off the top of the view, so scroll to
  // the top of the message itself instead of the bottom of the list.
  const scrollToLastMessage = () => {
    requestAnimationFrame(() => {
      lastMessageRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    let attachedNote = "";
    if (chips.length) {
      attachedNote = chips.map((c) => "📄 " + c.label).join(" · ") + "\n";
      setChips([]);
    }

    setMessages((m) => [...m, { id: msgId++, from: "user", text: attachedNote + trimmed, timestamp: now() }]);
    setInput("");
    const thinkingId = msgId++;
    setMessages((m) => [...m, { id: thinkingId, from: "agent", text: "", thinking: true, timestamp: now() }]);
    scrollToBottom();

    setTimeout(async () => {
      // The front door: open a page, start the agents, or prepare a decision to
      // confirm. Anything else is a question for the protected records below.
      try {
        const plan = await interpretCommand(trimmed);
        if (plan.kind !== "answer") {
          setMessages((list) => list.map((message) => (
            message.id === thinkingId
              ? { ...message, thinking: false, timestamp: now(), text: "", embed: <AssistantReply plan={plan} />, rawQuestion: trimmed }
              : message
          )));
          scrollToLastMessage();
          return;
        }
      } catch {
        // An older backend without the assistant: answer as before.
      }
      const fallback: ChatReply = resolveChatReply(trimmed, lang, FB_UNIFIED_FALLBACK[lang]);
      let finalText = fallback.text;
      let protectedText: string | undefined;
      let citations: QueryCitation[] = [];
      let mode = "scripted-demo";
      let queryIntent: QueryIntent | undefined;
      let embed = fallback.embed;
      let brief: CustomerIntelligenceBrief | undefined;
      let exposure: ExposureReceipt | undefined;
      let modelQuestion: string | undefined;
      let turnId: number | undefined;
      let isFallback = false;
      try {
        const response = await askQuestion(trimmed, conversationId, scopedCustomerId);
        setConversationId(response.conversation_id);
        if (response.conversation_id) {
          recordConversationTurn(response.conversation_id, trimmed);
          setRecentConversations(listRecentConversations());
        }
        setProtectedTurnCount((count) => count + 1);
        finalText = response.answer;
        protectedText = response.model_answer;
        citations = response.citations;
        mode = response.mode;
        queryIntent = response.query_intent;
        brief = response.intelligence_brief ?? undefined;
        exposure = response.exposure_receipt ?? undefined;
        modelQuestion = response.model_question;
        turnId = response.turn_id ?? undefined;
        embed = matchEinvoiceReadinessEmbed(trimmed) ?? undefined;
      } catch (error) {
        isFallback = true;
        embed = undefined;
        finalText = error instanceof ApiError
          ? `DuitDuit could not complete this request (${error.code}).${error.requestId ? ` Reference: ${error.requestId}` : ""}`
          : "DuitDuit could not reach the backend. Check the connection and try again.";
      }

      setMessages((messages) => messages.map((message) => (
        message.id === thinkingId
          ? {
              ...message,
              thinking: false,
              timestamp: now(),
              text: finalText,
              protectedText,
              citations,
              mode,
              queryIntent,
              embed,
              rawQuestion: trimmed,
              modelQuestion,
              turnId,
              brief,
              exposure,
              isFallback,
            }
          : message
      )));
      scrollToLastMessage();
    }, 650);
  };

  const handleSuggestion = (text: string) => send(text);

  // Generic handoffs may still opt into immediate sending. Each handoff has a
  // unique ID so React Strict Mode's development effect replay cannot submit
  // the same request twice.
  useEffect(() => {
    if (pendingAskPrompt && consumedHandoffRef.current !== pendingAskPrompt.id) {
      consumedHandoffRef.current = pendingAskPrompt.id;
      const prompt = pendingAskPrompt.prompt;
      clearPendingAskPrompt();
      void send(prompt);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingAskPrompt, clearPendingAskPrompt]);

  const startNewConversation = () => {
    setConversationId(null);
    setProtectedTurnCount(0);
    setChips([]);
    setMessages([
      {
        id: msgId++,
        from: "agent",
        text: "New protected conversation started. What would you like to investigate?",
        timestamp: now(),
      },
    ]);
  };

  // The backend keeps real turn history per conversation_id, but nothing
  // fetches it back — resuming just re-attaches to that id so the next
  // question gets answered with the right context, rather than pretending
  // to redisplay messages this browser never actually stored.
  const resumeConversation = (entry: RecentConversation) => {
    setConversationId(entry.id);
    setProtectedTurnCount(0);
    setChips([]);
    setRecentOpen(false);
    setMessages([
      {
        id: msgId++,
        from: "agent",
        text: `Continuing "${entry.title}" — ask your next question and DuitDuit will pick up where that conversation left off.`,
        timestamp: now(),
      },
    ]);
  };

  const clearUpload = () => {
    setSelectedFile(null);
    setUploadPreview(null);
    setUploadResult(null);
    setUploadError("");
    setUploadState("idle");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    setUploadPreview(null);
    setUploadResult(null);
    setUploadError("");
    setUploadState("previewing");
    try {
      setUploadPreview(await previewUpload(file));
      setUploadState("protected");
    } catch (requestError) {
      setUploadError(requestError instanceof Error ? requestError.message : "Preview failed.");
      setUploadState("failed");
    }
  };

  const protectAndIngestFile = async () => {
    if (!selectedFile || !uploadPreview || uploadState === "committing") return;
    setUploadState("committing");
    setUploadError("");
    try {
      const response = await commitUpload(
        selectedFile,
        uploadPreview.preview_digest,
      );
      setUploadResult(response);
      setUploadState("complete");
      setChips([{ label: `${response.ready_rows} protected source${response.ready_rows === 1 ? "" : "s"}` }]);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (requestError) {
      setUploadError(requestError instanceof Error ? requestError.message : "Ingestion failed.");
      setUploadState("failed");
    }
  };

  const removeChip = (i: number) => setChips((c) => c.filter((_, idx) => idx !== i));

  const hasConversation = messages.length > 1;
  const canRunAgents = askRole === "finance_ops" || askRole === "owner_director";

  return (
    <div className="fb-root fb-shell fb-chat-shell">
      <Sidebar current="agents" />
      <AppTopBar current="agents" />

      <div className="fb-chat-page">
        {sampleBanner && (
          <div className="fb-callout fb-sample-banner">
            <span>You're exploring DuitDuit with sample data from a demo workspace — connect your own sources anytime.</span>
            <button className="fb-icon-btn" type="button" onClick={dismissSampleBanner} aria-label="Dismiss">✕</button>
          </div>
        )}

        {!hasConversation && (
          <div className="fb-chat-welcome">
            <header className="fb-app-header" style={{ paddingBottom: "1rem" }}>
              <h1 className="fb-chat-welcome-title"><LogoMark large /> {t("agents.title")}</h1>
              <p>{t("agents.desc")}</p>
            </header>
            <section className="fb-cash-card fb-run-panel is-compact" aria-label="Your briefing"><BriefingCard /></section>
            {canRunAgents && <AgentRunPanel compact />}
          </div>
        )}

        <div className={"fb-chat-transcript-wrap" + (hasConversation ? " is-active" : " is-empty")}>
          <div className="fb-unified-chat-panel">
          <div className="fb-chat-messages fb-unified-messages" ref={messagesRef}>
            {messages.map((msg, idx) => (
              <div
                key={msg.id}
                ref={idx === messages.length - 1 ? lastMessageRef : undefined}
                className={"fb-chat-row " + msg.from + (msg.brief || msg.queryIntent === "list_records" ? " is-wide" : "")}
              >
                <span className={"fb-chat-avatar " + msg.from} aria-hidden="true">
                  {msg.from === "agent" ? <LogoMark large /> : userInitial}
                </span>
                <div className={"fb-chat-bubble " + msg.from + (msg.embed ? " has-embed" : "") + (msg.brief ? " has-intelligence" : "") + (msg.queryIntent === "list_records" ? " has-structured-records" : "")}>
                {msg.thinking ? (
                  <div className="fb-intel-building" role="status">
                    <span className="fb-thinking"><span></span><span></span><span></span></span>
                    <span>Searching protected knowledge…</span>
                  </div>
                ) : (
                  <>
                    {msg.isFallback && (
                      <div className="fb-intel-fallback" role="status">The live request failed; no sample answer was substituted.</div>
                    )}
                    {!msg.brief && msg.queryIntent !== "list_records" && (msg.text || msg.showProtected) && (
                      <span style={{ whiteSpace: "pre-wrap" }}>
                        {msg.showProtected && msg.protectedText ? msg.protectedText : msg.text}
                      </span>
                    )}
                    {msg.brief && msg.turnId && msg.rawQuestion && msg.modelQuestion && msg.protectedText && (
                      <IntelligenceExperience
                        brief={msg.brief}
                        citations={msg.citations ?? []}
                        exposure={msg.exposure ?? null}
                        turnId={msg.turnId}
                        rawQuestion={msg.rawQuestion}
                        modelQuestion={msg.modelQuestion}
                        protectedAnswer={msg.protectedText}
                        authorizedAnswer={msg.text}
                        role={askRole}
                        onOpenApprovals={openApprovalRecommendation}
                      />
                    )}
                    {msg.queryIntent === "list_records" && msg.turnId && msg.rawQuestion && msg.modelQuestion && msg.protectedText && (
                      <StructuredCitationResults
                        answer={msg.text}
                        citations={msg.citations ?? []}
                        exposure={msg.exposure ?? null}
                        turnId={msg.turnId}
                        rawQuestion={msg.rawQuestion}
                        modelQuestion={msg.modelQuestion}
                        protectedAnswer={msg.protectedText}
                      />
                    )}
                    {msg.from === "agent" && msg.protectedText && !msg.brief && msg.queryIntent !== "list_records" && (
                      <div className="fb-answer-actions">
                        <div className="fb-answer-actions-row">
                          {msg.exposure && msg.rawQuestion && msg.modelQuestion && (
                            <StandaloneExposureReceipt exposure={msg.exposure} rawQuestion={msg.rawQuestion} modelQuestion={msg.modelQuestion} protectedAnswer={msg.protectedText} authorizedAnswer={msg.text} />
                          )}
                          {!!msg.citations?.length && (
                            <details className="fb-answer-action-details">
                              <summary className="fb-btn fb-btn-outline fb-answer-action">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
                                Inspect {msg.citations.length} cited source{msg.citations.length === 1 ? "" : "s"}
                              </summary>
                              <div style={{ display: "grid", gap: ".5rem", marginTop: ".8rem" }}>
                                {msg.citations.map((citation) => (
                                  <div className="fb-rec-evidence" key={citation.citation_id}>
                                    <strong>{citation.citation_id}</strong> · {citation.source_system} · {citation.record_type ?? "record"}
                                    {citation.occurred_at ? ` · ${new Date(citation.occurred_at).toLocaleDateString()}` : ""}
                                    <div style={{ marginTop: ".35rem" }}>{citation.protected_excerpt}</div>
                                  </div>
                                ))}
                              </div>
                            </details>
                          )}
                        </div>
                        <span className="fb-fine">{msg.mode} · {msg.citations?.length ?? 0} cited sources</span>
                      </div>
                    )}
                    {msg.embed && <div className="fb-chat-embed">{msg.embed}</div>}
                    {msg.from === "agent" && scopedCustomerId !== null && msg.turnId && !msg.isFallback && (askRole === "finance_ops" || askRole === "owner_director") && (
                      <OutreachComposerCard customerId={scopedCustomerId} turnId={msg.turnId} role={askRole} />
                    )}
                  </>
                )}
                {!msg.thinking && <span className="fb-chat-time">{formatTime(msg.timestamp)}</span>}
                </div>
              </div>
            ))}
          </div>

          {!hasConversation && (
            <div className="fb-suggest-row">
              <span className="fb-eyebrow fb-suggest-label">Try asking</span>
              {SUGGESTIONS.map((s) => (
                <button key={s.text} className="fb-suggest-chip" type="button" title={s.text} onClick={() => handleSuggestion(s.text)}>
                  <span className="fb-suggest-chip-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{s.icon}</svg>
                  </span>
                  {s.text}
                </button>
              ))}
            </div>
          )}

          {uploadState !== "idle" && (
            <section className="fb-upload-preview" aria-live="polite">
              <div className="fb-upload-preview-head">
                <div>
                  <strong>
                    {uploadState === "previewing" ? "Protecting preview..." :
                      uploadState === "committing" ? "Protecting and ingesting..." :
                        uploadState === "complete" ? "Upload complete" :
                          uploadState === "failed" ? "Upload needs attention" :
                            "Protected preview"}
                  </strong>
                  {selectedFile && (
                    <div className="fb-fine">
                      {selectedFile.type || "Unknown type"} · {(selectedFile.size / 1024).toFixed(1)} KB
                    </div>
                  )}
                </div>
                <span className={`fb-status-pill ${uploadState === "complete" ? "is-active" : "is-review"}`}>
                  <span className="fb-status-dot"></span>{uploadState}
                </span>
              </div>

              {uploadPreview && (
                <>
                  <div className="fb-upload-stats">
                    <span>{uploadPreview.schema_name ?? uploadPreview.input_kind}</span>
                    <span>{uploadPreview.valid_rows} valid</span>
                    <span>{uploadPreview.invalid_rows} invalid</span>
                  </div>
                  <div className="fb-upload-samples">
                    {uploadPreview.protected_preview.slice(0, 3).map((item) => (
                      <div key={`${item.source_record_id}-${item.row_number ?? 0}`}>
                        {item.row_number ? `Row ${item.row_number}: ` : ""}{item.content_text}
                      </div>
                    ))}
                  </div>
                  {uploadPreview.valid_rows > Math.min(3, uploadPreview.protected_preview.length) && (
                    <div className="fb-fine">
                      Showing {Math.min(3, uploadPreview.protected_preview.length)} of {uploadPreview.valid_rows} protected rows<br />
                      + {uploadPreview.valid_rows - Math.min(3, uploadPreview.protected_preview.length)} additional row{uploadPreview.valid_rows - Math.min(3, uploadPreview.protected_preview.length) === 1 ? "" : "s"} will be ingested
                    </div>
                  )}
                  {[...uploadPreview.issues.map((issue) => issue.code), ...uploadPreview.warnings]
                    .map((notice) => <div className="fb-fine" key={notice}>{notice.replaceAll("_", " ")}</div>)}
                </>
              )}

              {uploadResult && (
                <div className="fb-upload-stats">
                  <span>{uploadResult.ready_rows} ready</span>
                  <span>{uploadResult.protected_rows} protected</span>
                  <span>{uploadResult.failed_rows} failed</span>
                </div>
              )}
              {uploadError && <div className="fb-upload-error" role="alert">{uploadError}</div>}

              <div className="fb-upload-actions">
                {uploadPreview && uploadState !== "complete" && (
                  <button
                    className="fb-btn fb-btn-solid"
                    type="button"
                    disabled={uploadState === "committing"}
                    onClick={protectAndIngestFile}
                  >
                    {uploadState === "committing" ? "Ingesting..." : "Protect and ingest"}
                  </button>
                )}
                <button className="fb-btn fb-btn-outline" type="button" onClick={clearUpload}>
                  {uploadState === "complete" ? "Close" : "Cancel"}
                </button>
              </div>
            </section>
          )}

          {chips.length > 0 && (
            <div className="fb-composer-chips">
              {chips.map((c, i) => (
                <span className="fb-composer-chip" key={i}>
                  📄 {c.label}
                  <button type="button" onClick={() => removeChip(i)} aria-label={"Remove " + c.label}>✕</button>
                </span>
              ))}
            </div>
          )}
          {scopedCustomerId !== null && (
            <div className="fb-composer-chips">
              <span className="fb-composer-chip">
                ◎ Customer #{scopedCustomerId} context
                <button
                  type="button"
                  onClick={() => {
                    clearCustomerContext();
                    startNewConversation();
                  }}
                  aria-label="Clear customer context"
                >✕</button>
              </span>
            </div>
          )}

          <div className="fb-composer2">
            <div className="fb-composer2-input-row">
              <input
                className="fb-composer2-input"
                type="text"
                placeholder={scopedCustomerId !== null ? `Ask about customer #${scopedCustomerId}…` : FB_UI_STRINGS[lang].placeholder}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") send(input); }}
              />
              <input
                type="file"
                accept=".txt,.md,.csv,.eml,.pdf,.docx,.png,.jpg,.jpeg,.webp,.bmp,.tiff"
                ref={fileInputRef}
                style={{ display: "none" }}
                onChange={handleFile}
              />
              <VoiceInput onTranscript={setInput} />
            </div>

            <div className="fb-composer2-toolbar-row">
              <div className="fb-composer2-tools">
                <div className="fb-composer2-tool-group">
                  <div
                    className="fb-recent-menu"
                    onBlur={(event) => {
                      if (!event.currentTarget.contains(event.relatedTarget as Node)) setRecentOpen(false);
                    }}
                  >
                    <button
                      className="fb-btn fb-btn-outline"
                      type="button"
                      onClick={() => setRecentOpen((v) => !v)}
                      aria-expanded={recentOpen}
                      title="Recent conversations (stored on this device only)"
                    >
                      Recent
                    </button>
                    {recentOpen && (
                      <div className="fb-recent-menu-panel" role="menu">
                        {recentConversations.length === 0 ? (
                          <div className="fb-fine" style={{ padding: ".8rem" }}>No recent conversations yet.</div>
                        ) : (
                          recentConversations.map((entry) => (
                            <button
                              key={entry.id}
                              className="fb-recent-menu-item"
                              type="button"
                              role="menuitem"
                              onClick={() => resumeConversation(entry)}
                            >
                              <span className="fb-recent-menu-title">{entry.title}</span>
                              <span className="fb-fine">
                                {entry.turnCount} turn{entry.turnCount === 1 ? "" : "s"} · {new Date(entry.lastActivityAt).toLocaleDateString()}
                              </span>
                            </button>
                          ))
                        )}
                        <div className="fb-recent-menu-footnote">Stored on this device only</div>
                      </div>
                    )}
                  </div>
                  {hasConversation && (
                    <button
                      className="fb-btn fb-btn-outline"
                      type="button"
                      onClick={startNewConversation}
                      title="Clear this conversation and start a new one"
                    >
                      New chat
                    </button>
                  )}
                </div>
                <span className="fb-composer2-divider" aria-hidden="true" />
                <button className="fb-icon-btn" type="button" title="Upload a file" onClick={() => fileInputRef.current?.click()} aria-label="Upload from computer">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21.44 11.05l-9.19 9.19a5 5 0 0 1-7.07-7.07l9.19-9.19a3.5 3.5 0 0 1 4.95 4.95l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" /></svg>
                </button>
                <span className="fb-composer-privacy-note" title="DuitDuit masks personal details before any question reaches the AI model.">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="4" y="10" width="16" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
                  Privacy protected{protectedTurnCount > 0 ? ` · ${protectedTurnCount} ${protectedTurnCount === 1 ? "reply" : "replies"}` : ""}
                </span>
              </div>
              <button className="fb-send-btn2" type="button" onClick={() => send(input)} aria-label={FB_UI_STRINGS[lang].send}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
              </button>
            </div>
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}
