"""Agentic retrieval: when a sentence is not found in its sources, search again once."""

from app.schemas import CitedAnswer
from app.services.agentic_retrieval import refine
from app.services.retrieval import RetrievalHit


def _hit(n: int, text: str) -> RetrievalHit:
    return RetrievalHit(
        content_id=n,
        source_record_id=f"r{n}",
        source_system="email",
        record_type="message",
        occurred_at=None,
        protected_excerpt=text,
        protected_summary=None,
        similarity=0.8,
    )


FIRST = [_hit(1, "The customer disputed the carton count on the delivery.")]
FOUND = _hit(2, "Statement: the customer still owes 98000 on the October shipment.")


def _answers(*answers):
    calls = []

    def answer(question, hits):
        calls.append((question, [h.content_id for h in hits]))
        return answers[min(len(calls) - 1, len(answers) - 1)], "test"

    return answer, calls


def test_a_grounded_answer_is_not_searched_again():
    answer, calls = _answers(
        CitedAnswer(
            answer="The customer disputed the carton count [SOURCE-1].", citations=["SOURCE-1"]
        )
    )
    searches = []
    result = refine(
        "What did the customer dispute?",
        FIRST,
        answer("What did the customer dispute?", FIRST)[0],
        answer=answer,
        search=lambda q: searches.append(q) or [],
    )
    assert (result.rounds, result.improved) == (1, False)
    assert searches == [] and len(calls) == 1


def test_an_unsupported_figure_triggers_one_more_search_that_finds_it():
    first = CitedAnswer(
        answer="The customer disputed the carton count [SOURCE-1]. They owe 98000 [SOURCE-1].",
        citations=["SOURCE-1"],
    )
    second = CitedAnswer(
        answer="The customer disputed the carton count [SOURCE-1]. "
        "They still owe 98000 [SOURCE-2].",
        citations=["SOURCE-1", "SOURCE-2"],
    )
    answer, calls = _answers(second)
    searches = []

    result = refine(
        "What does the customer owe?",
        FIRST,
        first,
        answer=answer,
        search=lambda q: searches.append(q) or [FOUND],
    )

    assert (result.rounds, result.improved) == (2, True)
    assert result.answer is second
    assert [h.content_id for h in result.hits] == [1, 2]
    # The follow-up search uses the question and the unsupported sentence's own words.
    assert "What does the customer owe?" in searches[0] and "98000" in searches[0]
    assert len(calls) == 1


def test_a_retry_that_is_no_better_keeps_the_first_answer():
    first = CitedAnswer(
        answer="The customer disputed the carton count [SOURCE-1]. They owe 98000 [SOURCE-1].",
        citations=["SOURCE-1"],
    )
    worse = CitedAnswer(answer="A warehouse lease was signed [SOURCE-2].", citations=["SOURCE-2"])
    answer, _ = _answers(worse)

    result = refine("Owe?", FIRST, first, answer=answer, search=lambda q: [FOUND])
    assert (result.rounds, result.improved) == (2, False)
    assert result.answer is first and [h.content_id for h in result.hits] == [1]


def test_nothing_new_found_means_no_second_answer():
    first = CitedAnswer(
        answer="They owe 98000 [SOURCE-1].",
        citations=["SOURCE-1"],
    )
    answer, calls = _answers(first)

    result = refine("Owe?", FIRST, first, answer=answer, search=lambda q: list(FIRST))
    assert (result.rounds, result.improved) == (2, False)
    assert calls == []


def test_an_insufficient_evidence_answer_is_left_alone():
    first = CitedAnswer(answer="No matching records.", citations=[], insufficient_evidence=True)
    answer, calls = _answers(first)
    searches = []

    result = refine(
        "Owe?", FIRST, first, answer=answer, search=lambda q: searches.append(q) or [FOUND]
    )
    assert result.rounds == 1 and searches == [] and calls == []


def test_the_query_route_searches_again_and_reports_two_rounds(monkeypatch):
    from app.routes.query import query
    from app.schemas import QueryRequest
    from app.services.retrieval import _hit_from_row
    from tests.auth_support import principal
    from tests.test_conversations import _database, _ready_record

    engine, db = _database()
    carton = _ready_record(db, "email:carton", "email")
    carton.content_text = "The customer disputed the carton count on the delivery."
    owed = _ready_record(db, "email:owed", "email")
    owed.content_text = "Statement: the customer still owes 98000 on the October shipment."
    db.commit()
    searches = []

    def retrieve(_db, question, _embedding, k, filters):
        searches.append(question)
        return [_hit_from_row(carton, 0.9)] if len(searches) == 1 else [_hit_from_row(owed, 0.8)]

    answers = iter(
        [
            CitedAnswer(
                answer="The customer disputed the carton count [SOURCE-1]. "
                "They owe 98000 [SOURCE-1].",
                citations=["SOURCE-1"],
            ),
            CitedAnswer(
                answer="The customer disputed the carton count [SOURCE-1]. "
                "They still owe 98000 [SOURCE-2].",
                citations=["SOURCE-1", "SOURCE-2"],
            ),
        ]
    )
    monkeypatch.setattr("app.routes.query.retrieve_hybrid_hits", retrieve)
    monkeypatch.setattr("app.routes.query.embed_query_cached", lambda q: ([0.0], "test"))
    monkeypatch.setattr(
        "app.routes.query.answer_all_query_with_citations",
        lambda question, hits, **kw: (next(answers), "test"),
    )
    try:
        response = query(
            QueryRequest(question="What did the customer dispute and what do they owe?"),
            principal(),
            db,
        )
        assert len(searches) == 2
        assert response.grounding.rounds == 2 and response.grounding.improved is True
        assert response.grounding.unsupported == []
        assert [c.source_record_id for c in response.citations] == ["email:carton", "email:owed"]
    finally:
        db.close()
        engine.dispose()


def test_no_second_round_once_the_time_budget_is_spent():
    # The website's proxy gives an answer about 25 seconds; a second model call that
    # would run past that is skipped, and the first answer is returned as it is.
    answer, calls = _answers(
        CitedAnswer(answer="The customer owes 98000 [SOURCE-1].", citations=["SOURCE-1"])
    )
    first, _ = answer("How much is owed?", FIRST)
    searched = []

    refined = refine(
        "How much is owed?",
        FIRST,
        first,
        answer=answer,
        search=lambda q: searched.append(q) or [FOUND],
        has_time=lambda: False,
    )

    assert (refined.rounds, refined.improved) == (1, False)
    assert searched == [] and len(calls) == 1
