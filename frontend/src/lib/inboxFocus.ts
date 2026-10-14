// Which review-inbox item to open next, set by a link elsewhere in the app
// (an agent run, a playbook) and taken once by the inbox when it loads.
let pending: string | null = null;

export function focusInboxItem(id: string) {
  pending = id;
}

export function takeInboxFocus(): string | null {
  const id = pending;
  pending = null;
  return id;
}
