"""Better retrieval: keyword reranking fused with vectors, and a grounding check on answers."""

from app.services import grounding
from app.services.retrieval import RetrievalHit, rerank


def _hit(n: int, text: str, similarity: float) -> RetrievalHit:
    return RetrievalHit(
        content_id=n,
        source_record_id=f"r{n}",
        source_system="email",
        record_type="message",
        occurred_at=None,
        protected_excerpt=text,
        protected_summary=None,
        similarity=similarity,
    )


def test_keywords_lift_the_record_that_actually_mentions_them():
    hits = [
        _hit(1, "Weekly newsletter about shipping trends", 0.82),
        _hit(2, "General update from the warehouse team", 0.80),
        _hit(3, "The customer disputed the carton count on the delivery", 0.78),
    ]
    ranked = rerank("Which customer disputed the carton delivery?", hits, k=3)

    assert ranked[0].content_id == 3
    assert {h.content_id for h in ranked} == {1, 2, 3}


def test_a_question_without_keywords_keeps_the_vector_order():
    hits = [_hit(1, "alpha", 0.9), _hit(2, "beta", 0.8)]
    assert [h.content_id for h in rerank("is it?", hits, k=2)] == [1, 2]


def test_rerank_keeps_at_most_k():
    hits = [_hit(n, f"invoice note {n}", 0.9 - n / 100) for n in range(1, 8)]
    assert len(rerank("invoice note", hits, k=3)) == 3


def test_a_sentence_found_in_its_source_is_supported():
    report = grounding.check(
        "CUST_1a2b3c4d5e disputed the carton count. Payment of 24500 is 20 days late.",
        ["CUST_1a2b3c4d5e disputed the carton count on INV-1041; 24500 overdue, 20 days late."],
    )
    assert (report.sentences, report.supported, report.unsupported) == (2, 2, [])


def test_a_figure_missing_from_every_source_is_not_supported():
    report = grounding.check(
        "The customer owes 98000 and disputed the carton count.",
        ["The customer disputed the carton count; 24500 is overdue."],
    )
    assert report.supported == 0 and report.unsupported == [1]


def test_a_sentence_of_unrelated_words_is_not_supported():
    report = grounding.check(
        "Cartons were disputed. Management approved a new warehouse lease yesterday.",
        ["The customer disputed the cartons delivered last week."],
    )
    assert (report.sentences, report.supported, report.unsupported) == (2, 1, [2])


def test_no_sources_means_nothing_to_check():
    assert grounding.check("Anything at all.", []) is None


def test_the_query_route_reports_how_grounded_the_answer_is(monkeypatch):
    from app.routes.query import query
    from app.schemas import CitedAnswer, QueryRequest
    from tests.auth_support import principal
    from tests.test_conversations import _database, _ready_record

    engine, db = _database()
    _ready_record(db, "email:grounded", "email")
    monkeypatch.setattr(
        "app.routes.query.answer_all_query_with_citations",
        lambda question, hits: (
            CitedAnswer(
                answer="The protected email content is relevant [SOURCE-1]. "
                "The customer owes 98000 for a warehouse lease.",
                citations=["SOURCE-1"],
                insufficient_evidence=False,
            ),
            "test",
        ),
    )
    try:
        response = query(QueryRequest(question="Summarize all records"), principal(), db)
        assert response.grounding is not None
        assert (response.grounding.sentences, response.grounding.supported) == (2, 1)
        assert response.grounding.unsupported == [2]
    finally:
        db.close()
        engine.dispose()
