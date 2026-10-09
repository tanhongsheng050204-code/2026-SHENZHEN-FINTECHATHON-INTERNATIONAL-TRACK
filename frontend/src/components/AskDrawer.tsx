import { useRef, useState, type ReactNode } from "react";
import { useAppState } from "../lib/appState";
import { useUiChrome } from "../lib/uiChrome";
import { askQuestion, type QueryCitation } from "../api/client";
import { interpretCommand } from "../api/topicE";
import { AssistantReply } from "./AssistantReply";

interface DrawerMessage {
  id: number;
  from: "user" | "agent";
  text: string;
  citations?: QueryCitation[];
  thinking?: boolean;
  isError?: boolean;
  node?: ReactNode;
}

let drawerMsgId = 1;

export function AskDrawer() {
  const { askOpen, closeAsk } = useUiChrome();
  const { show } = useAppState();
  const [messages, setMessages] = useState<DrawerMessage[]>([
    { id: drawerMsgId++, from: "agent", text: "Ask a question, or tell me what to do: \"open cash flow\", \"can I cover payroll?\", \"approve the reminder drafts\". I always check with you before changing anything." },
  ]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
    });
  };

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessages((m) => [...m, { id: drawerMsgId++, from: "user", text: trimmed }]);
    setInput("");
    const thinkingId = drawerMsgId++;
    setMessages((m) => [...m, { id: thinkingId, from: "agent", text: "", thinking: true }]);
    scrollToBottom();

    try {
      const plan = await interpretCommand(trimmed);
      if (plan.kind !== "answer") {
        setMessages((m) => m.map((msg) => (
          msg.id === thinkingId
            ? { ...msg, thinking: false, text: "", node: <AssistantReply plan={plan} onNavigate={closeAsk} /> }
            : msg
        )));
        scrollToBottom();
        return;
      }
    } catch {
      // An older backend without the assistant: answer as before.
    }

    let finalText: string;
    let citations: QueryCitation[] = [];
    let isError = false;
    try {
      const response = await askQuestion(trimmed, conversationId);
      setConversationId(response.conversation_id);
      finalText = response.answer;
      citations = response.citations;
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : "The request failed unexpectedly.";
      finalText = `DuitDuit could not answer this question: ${detail}`;
      isError = true;
    }

    setMessages((m) => m.map((msg) => (
      msg.id === thinkingId
        ? { ...msg, thinking: false, text: finalText, citations, isError }
        : msg
    )));
    scrollToBottom();
  };

  if (!askOpen) return null;

  return (
    <div className="fb-drawer-backdrop" onClick={closeAsk}>
      <aside className="fb-drawer" role="dialog" aria-modal="true" aria-label="Ask DuitDuit" onClick={(event) => event.stopPropagation()}>
        <div className="fb-drawer-head">
          <span className="fb-drawer-title">Ask DuitDuit</span>
          <button className="fb-icon-btn" type="button" onClick={closeAsk} aria-label="Close">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
        </div>
        <div className="fb-drawer-messages" ref={listRef}>
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={"fb-chat-bubble " + msg.from + (msg.isError ? " is-error" : "")}
              role={msg.isError ? "alert" : undefined}
            >
              {msg.thinking ? (
                <div className="fb-thinking" role="status"><span></span><span></span><span></span></div>
              ) : (
                <>
                  {msg.text && <span style={{ whiteSpace: "pre-wrap" }}>{msg.text}</span>}
                  {msg.node}
                  {!!msg.citations?.length && (
                    <div className="fb-fine" style={{ marginTop: ".5rem" }}>{msg.citations.length} cited source{msg.citations.length === 1 ? "" : "s"}</div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
        <div className="fb-drawer-footer">
          <button className="fb-btn fb-btn-outline" style={{ width: "100%", marginBottom: ".6rem" }} type="button" onClick={() => { closeAsk(); show("agents"); }}>
            Open in Ask
          </button>
          <div className="fb-drawer-input-row">
            <input
              className="fb-composer2-input"
              type="text"
              placeholder="Ask anything…"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => { if (event.key === "Enter") send(input); }}
            />
            <button className="fb-send-btn2" type="button" onClick={() => send(input)} aria-label="Send">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}
