"""Reset the shared demo company now, instead of waiting for the daily reset.

Switches stopped agents back on, restores the seeded settings and puts decided
review items back in the inbox. Nothing is deleted: the reset is one more event on
the company's workflow chain. Only the configured demo tenant can be reset.

Usage: python -m scripts.reset_demo_company
"""

from app.config import get_settings
from app.db import SessionLocal
from app.services.demo_reset import reset


def main() -> None:
    tenant_id = get_settings().demo_tenant_id
    with SessionLocal() as db:
        restored = reset(db, tenant_id)
    print(f"Demo company {tenant_id} reset: {', '.join(restored)}")


if __name__ == "__main__":
    main()
