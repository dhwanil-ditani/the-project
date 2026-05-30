"""
Pydantic schemas for the Double-Entry Expenses module.

Covers Account/Transaction CRUD and the FinancialDashboardMetrics
schema used by the dashboard endpoint.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator


# ── Account schemas ─────────────────────────────────────────────────────────
class AccountCreate(BaseModel):
    """Payload for creating a new account."""

    name: str
    type: str  # "Bank", "Cash", or "System"
    current_balance: Decimal = Decimal("0.00")


class AccountUpdate(BaseModel):
    """Payload for updating an existing account. All fields optional."""

    name: str | None = None
    type: str | None = None
    current_balance: Decimal | None = None


class AccountResponse(BaseModel):
    """Full account representation returned by the API."""

    id: int
    name: str
    type: str
    current_balance: Decimal

    model_config = ConfigDict(from_attributes=True)


# ── Transaction schemas ─────────────────────────────────────────────────────
class TransactionCreate(BaseModel):
    """
    Payload for creating a new transaction.

    Validation: ``to_account_id`` must not equal ``from_account_id``
    to prevent self-loop entries.
    """

    amount: Decimal
    date: datetime | None = None
    description: str
    category: str
    from_account_id: int
    to_account_id: int | None = None

    @model_validator(mode="after")
    def validate_no_self_loop(self) -> "TransactionCreate":
        if (
            self.to_account_id is not None
            and self.to_account_id == self.from_account_id
        ):
            raise ValueError(
                "to_account_id must not equal from_account_id (self-loop)"
            )
        return self


class TransactionResponse(BaseModel):
    """Full transaction representation returned by the API."""

    id: int
    amount: Decimal
    date: datetime
    description: str
    category: str
    from_account_id: int
    to_account_id: int | None

    model_config = ConfigDict(from_attributes=True)


# ── Dashboard metrics schema ───────────────────────────────────────────────
class FinancialDashboardMetrics(BaseModel):
    """
    Aggregated financial metrics for the expenses dashboard.

    * ``monthly_spending``: total outflows this month, excluding
      internal transfers (to_account_id is not null) and System
      account outflows (income seeding).
    * ``mom_spending_change_pct``: month-over-month change as a
      percentage (e.g. 15.0 = +15%).
    * ``category_breakdown``: spending grouped by category this month.
    * ``net_worth``: sum of all Bank + Cash account balances.
    """

    monthly_spending: Decimal
    mom_spending_change_pct: float
    category_breakdown: dict[str, Decimal]
    net_worth: Decimal
