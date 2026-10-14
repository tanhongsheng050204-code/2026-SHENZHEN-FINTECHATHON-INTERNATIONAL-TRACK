// Translates screen text that is written in plain English in the components
// rather than through tx(). It changes only text nodes and a few attributes
// whose whole text is a known sentence in the dictionaries, keeps the English
// so switching back restores it, and leaves anything marked translate="no".
// React keeps working because it only ever overwrites these nodes with new
// English, which is then translated again.
import { msFor } from "./i18nMs";
import { zhFor } from "./i18nZh";

type Lang = "en" | "zh" | "ms";

const ATTRS = ["placeholder", "title", "aria-label"];
const SKIP = "script, style, textarea, code, pre, [translate='no'], .notranslate, [data-dd-english]";

const englishOf = new WeakMap<Node, string>();
const shownAs = new WeakMap<Node, string>();
const attrEnglish = new WeakMap<Element, Map<string, string>>();
const attrShown = new WeakMap<Element, Map<string, string>>();

function translated(lang: Lang, english: string): string | null {
  const key = english.trim();
  if (!key || !/[A-Za-z]/.test(key)) return null;
  const text = lang === "zh" ? zhFor(key) : lang === "ms" ? msFor(key) : null;
  if (!text || text === key) return null;
  const start = english.indexOf(key);
  return english.slice(0, start) + text + english.slice(start + key.length);
}

function skipped(node: Node): boolean {
  const el = node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement;
  return !el || el.closest(SKIP) !== null;
}

function textNode(node: Text, lang: Lang) {
  const now = node.nodeValue ?? "";
  if (shownAs.get(node) === now) {
    if (lang === "en") {
      node.nodeValue = englishOf.get(node) ?? now;
      shownAs.delete(node);
      return;
    }
    const again = translated(lang, englishOf.get(node) ?? now);
    if (again && again !== now) {
      shownAs.set(node, again);
      node.nodeValue = again;
    }
    return;
  }
  if (lang === "en" || skipped(node)) return;
  const text = translated(lang, now);
  if (!text) return;
  englishOf.set(node, now);
  shownAs.set(node, text);
  node.nodeValue = text;
}

function attributes(el: Element, lang: Lang) {
  for (const name of ATTRS) {
    const now = el.getAttribute(name);
    if (now === null) continue;
    const shown = attrShown.get(el);
    const english = attrEnglish.get(el);
    if (shown?.get(name) === now) {
      const original = english?.get(name) ?? now;
      const next = lang === "en" ? original : translated(lang, original) ?? original;
      if (next !== now) el.setAttribute(name, next);
      if (lang === "en") shown.delete(name);
      else shown.set(name, next);
      continue;
    }
    if (lang === "en" || skipped(el)) continue;
    const text = translated(lang, now);
    if (!text) continue;
    if (!attrEnglish.has(el)) attrEnglish.set(el, new Map());
    if (!attrShown.has(el)) attrShown.set(el, new Map());
    attrEnglish.get(el)!.set(name, now);
    attrShown.get(el)!.set(name, text);
    el.setAttribute(name, text);
  }
}

function walk(root: Node, lang: Lang) {
  if (root.nodeType === Node.TEXT_NODE) {
    textNode(root as Text, lang);
    return;
  }
  if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) return;
  if (root.nodeType === Node.ELEMENT_NODE) attributes(root as Element, lang);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node.nodeType === Node.TEXT_NODE) textNode(node as Text, lang);
    else attributes(node as Element, lang);
  }
}

/** Keeps the page under root in the chosen language until the returned stop is called. */
export function translateDom(root: HTMLElement, lang: Lang): () => void {
  walk(root, lang);
  if (lang === "en") return () => {};
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      if (record.type === "characterData") textNode(record.target as Text, lang);
      else if (record.type === "attributes") attributes(record.target as Element, lang);
      else record.addedNodes.forEach((node) => walk(node, lang));
    }
  });
  observer.observe(root, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  return () => observer.disconnect();
}
