"""The cash basis for the person asking: their tenant's records, else the demo company.

A tenant with an imported bank balance gets a live forecast (data_mode "live").
Any other tenant, including every tenant before the Plan 3 tables are deployed,
sees the synthetic demo company (data_mode "stub"), and the page says so.
"""

import datetime as dt

from app.auth.principal import AuthPrincipal
from app.services import cash_basis
from app.services.cashflow_engine import CashBasis
from app.stubs import cashflow as synthetic


def basis_for(db, principal: AuthPrincipal, as_of: dt.date) -> CashBasis:
    # Contract tests run the routes without a database.
    if db is not None:
        live = cash_basis.load(db, str(principal.tenant_id), as_of)
        if live is not None:
            return live
    return synthetic.BASIS
