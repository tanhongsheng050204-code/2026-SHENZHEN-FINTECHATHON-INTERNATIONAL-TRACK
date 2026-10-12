"""Groundedness check: is each sentence of an answer found in the sources it cites?

A sentence counts as supported when every figure in it appears in the cited text
and at least half of its content words do (words of four letters or more, and
protected tokens, outside a short stop list). Sentences with no content words are
not counted. This is a lexical check on protected text, not a model judging a
model: it can miss a correct paraphrase, but it cannot be talked into passing an
invented figure. The answer is shown either way; the result tells the reader which
sentences to check against the sources.
"""

import re

from app.schemas import GroundingReport

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_CITATION = re.compile(r"\[?\bSOURCE-\d+\b\]?")
_WORD = re.compile(r"[A-Za-z][A-Za-z_0-9-]{3,}")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_STOP = frozenset(
    "this that with from have been were they them their there what when which while will "
    "would could should about into over also only than then these those your yours each "
    "some more most such very just like after before because does done".split()
)
MIN_WORD_SHARE = 0.5


def _norm_number(value: str) -> str:
    return value.replace(",", "").rstrip(".")


def _words(text: str) -> set[str]:
    return {w.casefold() for w in _WORD.findall(text) if w.casefold() not in _STOP}


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def check(answer: str, cited_texts: list[str]) -> GroundingReport | None:
    if not cited_texts or not answer.strip():
        return None
    answer = _CITATION.sub("", answer)
    source = "\n".join(cited_texts)
    source_words = {_stem(w) for w in _words(source)}
    source_numbers = {_norm_number(n) for n in _NUMBER.findall(source)}
    counted = supported = 0
    unsupported: list[int] = []
    for index, sentence in enumerate(s for s in _SENTENCE.split(answer.strip()) if s.strip()):
        words = {_stem(w) for w in _words(sentence)}
        numbers = {_norm_number(n) for n in _NUMBER.findall(sentence)}
        if not words and not numbers:
            continue
        counted += 1
        share = len(words & source_words) / len(words) if words else 1.0
        if numbers <= source_numbers and share >= MIN_WORD_SHARE:
            supported += 1
        else:
            unsupported.append(index + 1)
    return GroundingReport(sentences=counted, supported=supported, unsupported=unsupported)
