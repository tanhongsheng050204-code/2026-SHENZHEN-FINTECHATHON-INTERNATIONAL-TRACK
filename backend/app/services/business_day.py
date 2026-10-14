"""The day a company's figures are read for.

A real company is read for today. The synthetic demo company is read for the day its
seed was built for (SyntheticTenantSeed.as_of): its bank lines, bills, payroll and
invoices are dated around that day, so read against the calendar its story would drift
away (from 1 November 2026 the default seed shows no cash gap at all). Every screen that
counts days for the demo company counts them from the seed day, and says so where it
shows a date.
"""

import datetime as dt

from app.models import SyntheticTenantSeed


def today(db, tenant_id) -> dt.date:
    if db is not None:
        seed = db.get(SyntheticTenantSeed, str(tenant_id))
        if seed is not None and seed.as_of is not None:
            return seed.as_of
    return dt.date.today()
