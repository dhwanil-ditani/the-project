"""
Double-Entry Expenses — SQLAlchemy models.

Every monetary movement is a Transaction that debits one Account and
(optionally) credits another, preserving the accounting equation.
The system bootstraps with an "Initial Equity" account of type System.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class AccountType(str, enum.Enum):
    """Classification of financial accounts."""

    BANK = "Bank"
    CASH = "Cash"
    SYSTEM = "System"


class Account(Base):
    """
    A financial account (bank, cash, or system).

    The system must always contain at least one account of type ``System``
    named "Initial Equity" that serves as the source of starting balances.
    """

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    type: Mapped[AccountType] = mapped_column(Enum(AccountType), nullable=False)
    current_balance: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=0.00
    )

    # Relationships — outbound and inbound transactions
    outgoing_transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="from_account",
        foreign_keys="Transaction.from_account_id",
        lazy="selectin",
    )
    incoming_transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="to_account",
        foreign_keys="Transaction.to_account_id",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Account(id={self.id}, name='{self.name}', "
            f"type={self.type.value}, balance={self.current_balance})>"
        )


class Transaction(Base):
    """
    A double-entry ledger row.

    * ``from_account_id`` — the account money leaves (required).
    * ``to_account_id``   — the account money enters (nullable for pure expenses).
    """

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    amount: Mapped[float] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False
    )
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    description: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)

    # Foreign keys
    from_account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("accounts.id"), nullable=False
    )
    to_account_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("accounts.id"), nullable=True
    )

    # Relationships
    from_account: Mapped["Account"] = relationship(
        back_populates="outgoing_transactions",
        foreign_keys=[from_account_id],
    )
    to_account: Mapped["Account | None"] = relationship(
        back_populates="incoming_transactions",
        foreign_keys=[to_account_id],
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, amount={self.amount}, "
            f"from={self.from_account_id} → to={self.to_account_id})>"
        )
