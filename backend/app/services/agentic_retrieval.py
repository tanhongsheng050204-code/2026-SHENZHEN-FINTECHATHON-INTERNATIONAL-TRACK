"""Agentic retrieval: check the answer, and search again once when it is not grounded.

After the first answer, the grounding check looks for sentences that the cited
sources do not support. If there are any, the agent builds a follow-up search from
the question and those sentences' own words (protected text only: tokens, never
raw personal data), adds what it finds to the sources, and asks for the answer
once more. It keeps whichever answer is better grounded, never a worse one, and
reports how many rounds it took. At most one extra round, so cost and latency are
bounded.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.schemas import CitedAnswer
from app.services.grounding import check
from app.services.retrieval import RetrievalHit

_CITATION = re.compile(r"\[?\bSOURCE-\d+\b\]?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
MAX_EXTRA_HITS = 5


@dataclass(frozen=True)
class Refined:
    hits: list[RetrievalHit]
    answer: CitedAnswer
    rounds: int
    improved: bool


def _cited(hits: list[RetrievalHit], answer: CitedAnswer) -> list[str]:
    return [
        hit.retrieval_text
        for index, hit in enumerate(hits, 1)
        if f"SOURCE-{index}" in answer.citations
    ]


def _share(hits: list[RetrievalHit], answer: CitedAnswer) -> float:
    if answer.insufficient_evidence:
        return -1.0
    report = check(answer.answer, _cited(hits, answer))
    if report is None or report.sentences == 0:
        return 0.0
    return report.supported / report.sentences


def _follow_up(question: str, answer: CitedAnswer, unsupported: list[int]) -> str:
    text = _CITATION.sub("", answer.answer)
    sentences = [s for s in _SENTENCE.split(text.strip()) if s.strip()]
    missing = [sentences[i - 1] for i in unsupported if 0 < i <= len(sentences)]
    return f"{question} {' '.join(missing)}".strip()


def refine(
    question: str,
    hits: list[RetrievalHit],
    first: CitedAnswer,
    *,
    answer: Callable[[str, list[RetrievalHit]], tuple[CitedAnswer, str]],
    search: Callable[[str], list[RetrievalHit]],
) -> Refined:
    """One answer, checked; at most one more search and answer if it is not grounded."""
    if first.insufficient_evidence:
        return Refined(hits, first, 1, False)
    report = check(first.answer, _cited(hits, first))
    if report is None or not report.unsupported:
        return Refined(hits, first, 1, False)
    seen = {hit.content_id for hit in hits}
    extra = [
        hit
        for hit in search(_follow_up(question, first, report.unsupported))
        if hit.content_id not in seen
    ][:MAX_EXTRA_HITS]
    if not extra:
        return Refined(hits, first, 2, False)  # searched again, found nothing new
    merged = [*hits, *extra]
    second, _mode = answer(question, merged)
    if _share(merged, second) > _share(hits, first):
        return Refined(merged, second, 2, True)
    return Refined(hits, first, 2, False)
