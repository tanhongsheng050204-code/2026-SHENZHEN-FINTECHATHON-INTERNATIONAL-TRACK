"""With a shared store, the limit holds across API instances (known risk 6)."""

import os

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text

from app.security import rate_limit

DSN = os.environ.get("FINBRAIN_REVIEW_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="requires disposable migrated PostgreSQL")


def test_two_instances_share_one_count_and_store_no_raw_address():
    engine = create_engine(DSN)
    rate_limit.configure_store(engine)
    try:
        check = rate_limit.counter("shared-test", 2)
        check("203.0.113.9")
        rate_limit.reset()  # a second instance starts with an empty memory
        check("203.0.113.9")
        rate_limit.reset()
        with pytest.raises(HTTPException) as refused:
            check("203.0.113.9")
        assert refused.value.status_code == 429
        with engine.connect() as connection:
            stored = connection.execute(
                text("select identity_hash from rate_limit_windows where bucket='shared-test'")
            ).scalars().all()
        assert stored and all("203.0.113.9" not in value for value in stored)
    finally:
        rate_limit.configure_store(None)
        engine.dispose()


def test_without_a_store_the_count_stays_in_process():
    rate_limit.configure_store(None)
    rate_limit.reset()
    check = rate_limit.counter("local-test", 1)
    check("198.51.100.1")
    with pytest.raises(HTTPException):
        check("198.51.100.1")
