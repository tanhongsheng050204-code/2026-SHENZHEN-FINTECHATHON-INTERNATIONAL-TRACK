/** Exactly one microphone directive, allowing this origin only. */
export function microphoneIsSelfOnly(value) {
  const directives = value.split(",").map((part) => part.trim())
    .filter((part) => /^microphone\s*=/.test(part));
  return directives.length === 1 && directives[0] === "microphone=(self)";
}
