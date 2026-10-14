// The recent chats on this browser: a title, the plain text of each message (so a
// chat reopens as it was) and, when the server confirmed one, its conversation id
// so a follow-up question keeps the server-side context. Cards and charts inside a
// reply are not kept; their text is. Stored on this device only, never synced,
// under the signed-in person's id, and removed when anyone signs out, so the next
// person on a shared browser never sees someone else's chats.

const LEGACY_KEY = "fb-recent-conversations";
const PREFIX = "fb-chats:";
let owner = "signed-out";

/** Whose chats are read and written; set from the signed-in identity. */
export function setConversationOwner(userId: string | null | undefined) {
  owner = userId ? userId.replace(/[^A-Za-z0-9-]/g, "") || "signed-out" : "signed-out";
}

const listKey = () => `${PREFIX}${owner}:list`;
const transcriptKey = (id: string) => `${PREFIX}${owner}:chat:${id}`;

/** Forget every stored chat on this browser, for every person. Called on sign-out. */
export function clearAllConversations() {
  try {
    const doomed: string[] = [];
    for (let i = 0; i < window.localStorage.length; i += 1) {
      const key = window.localStorage.key(i);
      if (key && (key.startsWith(PREFIX) || key === LEGACY_KEY || key.startsWith("fb-conversation-"))) doomed.push(key);
    }
    doomed.forEach((key) => window.localStorage.removeItem(key));
  } catch {
    // Storage disabled: nothing was stored.
  }
}

const MAX_ENTRIES = 20;
const MAX_MESSAGES = 60;
const MAX_TEXT = 4000;

export interface RecentConversation {
  id: string;
  serverId?: string | null;
  title: string;
  lastActivityAt: string;
  turnCount: number;
}

export interface SavedMessage {
  from: "user" | "agent";
  text: string;
  timestamp: number;
}

function readAll(): RecentConversation[] {
  try {
    const raw = window.localStorage.getItem(listKey());
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeAll(entries: RecentConversation[]) {
  try {
    const sorted = [...entries].sort((a, b) => b.lastActivityAt.localeCompare(a.lastActivityAt));
    for (const dropped of sorted.slice(MAX_ENTRIES)) window.localStorage.removeItem(transcriptKey(dropped.id));
    window.localStorage.setItem(listKey(), JSON.stringify(sorted.slice(0, MAX_ENTRIES)));
  } catch {
    // Private browsing or storage disabled: recent chats just won't persist.
  }
}

export function listRecentConversations(): RecentConversation[] {
  return readAll().sort((a, b) => new Date(b.lastActivityAt).getTime() - new Date(a.lastActivityAt).getTime());
}

/** Older entries were keyed by the server id itself. */
export function serverIdOf(entry: RecentConversation): string | null {
  if (entry.serverId) return entry.serverId;
  return entry.id.startsWith("local-") ? null : entry.id;
}

export function saveConversation(id: string, serverId: string | null, messages: SavedMessage[]) {
  const userTurns = messages.filter((m) => m.from === "user");
  if (userTurns.length === 0) return;
  const entries = readAll();
  const existing = entries.find((e) => e.id === id);
  const entry: RecentConversation = {
    id,
    serverId: serverId ?? existing?.serverId ?? null,
    title: (existing?.title ?? userTurns[0].text).trim().slice(0, 90),
    lastActivityAt: new Date().toISOString(),
    turnCount: userTurns.length,
  };
  writeAll([entry, ...entries.filter((e) => e.id !== id)]);
  try {
    const trimmed = messages.slice(-MAX_MESSAGES).map((m) => ({ ...m, text: m.text.slice(0, MAX_TEXT) }));
    window.localStorage.setItem(transcriptKey(id), JSON.stringify(trimmed));
  } catch {
    // Storage full or disabled: the chat still works, it just won't reopen.
  }
}

export function loadTranscript(id: string): SavedMessage[] {
  try {
    const raw = window.localStorage.getItem(transcriptKey(id));
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function removeConversation(id: string) {
  writeAll(readAll().filter((e) => e.id !== id));
  try {
    window.localStorage.removeItem(transcriptKey(id));
  } catch {
    // Nothing stored to remove.
  }
}

export function newLocalConversationId(): string {
  return "local-" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}
