import { useI18n } from "../lib/i18n";
import "./records.css";

/**
 * Whether each sentence of an answer was found in the sources it cites. A lexical
 * check: every figure must appear in a source, and most of the words.
 */
export function GroundingChip({ grounding }: { grounding: { sentences: number; supported: number; unsupported: number[] } }) {
  const { tx } = useI18n();
  const all = grounding.supported === grounding.sentences;
  const text = all
    ? tx("Every sentence found in its sources")
    : tx("{n} of {total} sentences not found in the sources: check sentence {which}", {
        n: grounding.sentences - grounding.supported,
        total: grounding.sentences,
        which: grounding.unsupported.join(", "),
      });
  return (
    <span className={"rc-chip " + (all ? "is-green" : "is-amber")} title={tx("Each sentence is checked against the sources it cites: its figures must appear there, and most of its words.")}>
      {text}
    </span>
  );
}
