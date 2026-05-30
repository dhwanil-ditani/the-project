"""
Core ledger logic for the Double-Entry Expenses module.

Provides:
  * ``initialize_system_equity(db)`` — bootstrap the "Initial Equity" System account.
  * ``process_transaction(db, txn)`` — apply balance changes following
    double-entry rules after a Transaction is created.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.expenses import Account, AccountType, Transaction


def initialize_system_equity(db: Session) -> Account:
    """
    Ensure the "Initial Equity" system account exists.

    If it already exists, return it unchanged. Otherwise create it
    with a zero balance.

    Returns the Account instance.
    """
    stmt = select(Account).where(
        Account.name == "Initial Equity",
        Account.type == AccountType.SYSTEM,
    )
    account = db.execute(stmt).scalar_one_or_none()

    if account is not None:
        return account

    account = Account(
        name="Initial Equity",
        type=AccountType.SYSTEM,
        current_balance=Decimal("0.00"),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def process_transaction(db: Session, txn: Transaction) -> None:
    """
    Apply balance adjustments for a transaction.

    Rules:
      * **Expense** (to_account is None):
          Deduct ``amount`` from ``from_account``.
      * **Self-transfer** (from Bank/Cash → to Bank/Cash):
          Deduct from ``from_account``, add to ``to_account``.
      * **Income / Day-Zero Setup** (from System → to Bank/Cash):
          Add ``amount`` to ``to_account``.
          (System account balance is not tracked meaningfully.)
    """
    from_account: Account = txn.from_account
    to_account: Account | None = txn.to_account
    amount = Decimal(str(txn.amount))

    if from_account.type == AccountType.SYSTEM:
        # Income / day-zero: credit the destination account only
        if to_account is not None:
            to_account.current_balance = Decimal(str(to_account.current_balance)) + amount
    else:
        # Deduct from the source account
        from_account.current_balance = Decimal(str(from_account.current_balance)) - amount

        # Credit the destination if this is a transfer
        if to_account is not None:
            to_account.current_balance = Decimal(str(to_account.current_balance)) + amount

    db.flush()
