"""
Expenses API — CRUD endpoints for Accounts, Transactions, and Financial Dashboard.

Mounted at ``/api/v1`` via the v1 router.
"""

from datetime import datetime, timezone
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.expenses import Account, AccountType, Transaction
from src.schemas.expenses import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    FinancialDashboardMetrics,
    TransactionCreate,
    TransactionResponse,
)
from src.services.ledger import initialize_system_equity, process_transaction

router = APIRouter(tags=["expenses"])


# ═══════════════════════════════════════════════════════════════════════════
#  Account CRUD
# ═══════════════════════════════════════════════════════════════════════════

def _get_account_or_404(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with id {account_id} not found",
        )
    return account


@router.post(
    "/accounts/init",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def seed_system_equity(
    db: Session = Depends(get_db),
) -> Account:
    """Bootstrap the Initial Equity system account."""
    account = initialize_system_equity(db)
    return account


@router.post(
    "/accounts/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED
)
async def create_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
) -> Account:
    """Create a new financial account."""
    account = Account(
        name=payload.name,
        type=AccountType(payload.type),
        current_balance=payload.current_balance,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/accounts/", response_model=list[AccountResponse])
async def list_accounts(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[Account]:
    """Return a paginated list of all accounts."""
    stmt = select(Account).offset(skip).limit(limit).order_by(Account.id)
    return list(db.execute(stmt).scalars().all())


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: int,
    db: Session = Depends(get_db),
) -> Account:
    """Retrieve a single account by ID."""
    return _get_account_or_404(db, account_id)


@router.put("/accounts/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: int,
    payload: AccountUpdate,
    db: Session = Depends(get_db),
) -> Account:
    """Update an existing account."""
    account = _get_account_or_404(db, account_id)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == "type" and value is not None:
            value = AccountType(value)
        setattr(account, field, value)

    db.commit()
    db.refresh(account)
    return account


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete an account by ID."""
    account = _get_account_or_404(db, account_id)
    db.delete(account)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  Transaction CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post(
    "/transactions/",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    payload: TransactionCreate,
    db: Session = Depends(get_db),
) -> Transaction:
    """
    Create a new transaction and apply balance changes.

    Balance rules are enforced by the ledger service.
    """
    # Verify from_account exists
    from_account = db.get(Account, payload.from_account_id)
    if from_account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"from_account_id {payload.from_account_id} not found",
        )

    # Verify to_account exists (if provided)
    to_account = None
    if payload.to_account_id is not None:
        to_account = db.get(Account, payload.to_account_id)
        if to_account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"to_account_id {payload.to_account_id} not found",
            )

    txn = Transaction(
        amount=payload.amount,
        date=payload.date or datetime.now(timezone.utc),
        description=payload.description,
        category=payload.category,
        from_account_id=payload.from_account_id,
        to_account_id=payload.to_account_id,
    )
    db.add(txn)
    db.flush()  # Assign ID and load relationships

    # Reload relationships so process_transaction can access from_account/to_account
    db.refresh(txn)

    # Apply balance changes
    process_transaction(db, txn)

    db.commit()
    db.refresh(txn)
    return txn


@router.get("/transactions/", response_model=list[TransactionResponse])
async def list_transactions(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[Transaction]:
    """Return a paginated list of all transactions."""
    stmt = select(Transaction).offset(skip).limit(limit).order_by(Transaction.id.desc())
    return list(db.execute(stmt).scalars().all())


@router.get("/transactions/{txn_id}", response_model=TransactionResponse)
async def get_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
) -> Transaction:
    """Retrieve a single transaction by ID."""
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {txn_id} not found",
        )
    return txn


@router.delete("/transactions/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a transaction by ID (does NOT reverse balance changes)."""
    txn = db.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction with id {txn_id} not found",
        )
    db.delete(txn)
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════
#  Financial Dashboard
# ═══════════════════════════════════════════════════════════════════════════

def _compute_monthly_spending(
    db: Session, month_start: datetime, month_end: datetime
) -> tuple[Decimal, dict[str, Decimal]]:
    """
    Compute total spending and category breakdown for a date range.

    Spending = outflows from non-System accounts where to_account_id IS NULL
    (pure expenses only, excluding internal transfers and System outflows).
    """
    stmt = select(Transaction).where(
        Transaction.date >= month_start,
        Transaction.date < month_end,
        Transaction.to_account_id.is_(None),  # pure expenses only
    )
    transactions = list(db.execute(stmt).scalars().all())

    total = Decimal("0.00")
    breakdown: dict[str, Decimal] = {}

    for txn in transactions:
        # Exclude outflows from System accounts (income seeding)
        from_acct = db.get(Account, txn.from_account_id)
        if from_acct is not None and from_acct.type == AccountType.SYSTEM:
            continue

        amount = Decimal(str(txn.amount))
        total += amount
        category = txn.category
        breakdown[category] = breakdown.get(category, Decimal("0.00")) + amount

    return total, breakdown


@router.get("/expenses/dashboard", response_model=FinancialDashboardMetrics)
async def expenses_dashboard(
    db: Session = Depends(get_db),
) -> FinancialDashboardMetrics:
    """
    Compute and return financial dashboard metrics.

    * Monthly spending for the current calendar month.
    * Month-over-month spending change as a percentage.
    * Category breakdown for the current month.
    * Net worth = sum of all Bank + Cash account balances.
    """
    now = datetime.now(timezone.utc)

    # Current month boundaries
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month_start = (current_month_start + relativedelta(months=1))

    # Previous month boundaries
    prev_month_start = current_month_start - relativedelta(months=1)

    # ── Monthly spending ────────────────────────────────────────────────
    monthly_spending, category_breakdown = _compute_monthly_spending(
        db, current_month_start, next_month_start
    )

    # ── Previous month spending (for MoM) ───────────────────────────────
    prev_spending, _ = _compute_monthly_spending(
        db, prev_month_start, current_month_start
    )

    # ── Month-over-month change ─────────────────────────────────────────
    if prev_spending == Decimal("0.00"):
        mom_pct = 0.0 if monthly_spending == Decimal("0.00") else 100.0
    else:
        mom_pct = float(
            ((monthly_spending - prev_spending) / prev_spending) * 100
        )

    # ── Net worth ───────────────────────────────────────────────────────
    accounts_stmt = select(Account).where(
        Account.type.in_([AccountType.BANK, AccountType.CASH])
    )
    accounts = list(db.execute(accounts_stmt).scalars().all())
    net_worth = sum(
        (Decimal(str(a.current_balance)) for a in accounts), Decimal("0.00")
    )

    return FinancialDashboardMetrics(
        monthly_spending=monthly_spending,
        mom_spending_change_pct=round(mom_pct, 2),
        category_breakdown=category_breakdown,
        net_worth=net_worth,
    )
