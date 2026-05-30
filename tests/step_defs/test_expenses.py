"""
Step definitions for the Double-Entry Expenses feature.
"""

from decimal import Decimal

import pytest
from pytest_bdd import parsers, scenarios, then, when, given

scenarios("../features/expenses.feature")


# ── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture()
def response_holder():
    """Mutable dict to hold the HTTP response between steps."""
    return {}


@pytest.fixture()
def account_map():
    """Maps account names to their IDs for cross-step reference."""
    return {}


# ── Given steps ─────────────────────────────────────────────────────────────
@given("the system equity account is initialized", target_fixture="account_map")
def init_system_equity(client):
    resp = client.post("/api/v1/accounts/init")
    assert resp.status_code == 201
    data = resp.json()
    return {"Initial Equity": data["id"]}


@given(
    parsers.parse('I create a bank account "{name}" with balance {balance:d}'),
)
def create_bank_account(client, name, balance, account_map):
    resp = client.post(
        "/api/v1/accounts/",
        json={"name": name, "type": "Bank", "current_balance": balance},
    )
    assert resp.status_code == 201
    account_map[name] = resp.json()["id"]


@given(
    parsers.parse('I transfer {amount:d} from Initial Equity to "{to_name}"'),
)
def seed_from_equity(client, amount, to_name, account_map):
    resp = client.post(
        "/api/v1/transactions/",
        json={
            "amount": amount,
            "description": f"Day-zero seed to {to_name}",
            "category": "Seed",
            "from_account_id": account_map["Initial Equity"],
            "to_account_id": account_map[to_name],
        },
    )
    assert resp.status_code == 201


# ── When steps ──────────────────────────────────────────────────────────────
@when(
    parsers.parse('I transfer {amount:d} from Initial Equity to "{to_name}"'),
    target_fixture="response_holder",
)
def transfer_from_equity(client, amount, to_name, account_map):
    resp = client.post(
        "/api/v1/transactions/",
        json={
            "amount": amount,
            "description": f"Day-zero seed to {to_name}",
            "category": "Seed",
            "from_account_id": account_map["Initial Equity"],
            "to_account_id": account_map[to_name],
        },
    )
    assert resp.status_code == 201
    return {"response": resp}


@when(
    parsers.parse('I transfer {amount:d} from "{from_name}" to "{to_name}"'),
    target_fixture="response_holder",
)
def transfer_between_accounts(client, amount, from_name, to_name, account_map):
    resp = client.post(
        "/api/v1/transactions/",
        json={
            "amount": amount,
            "description": f"Transfer {from_name} -> {to_name}",
            "category": "Transfer",
            "from_account_id": account_map[from_name],
            "to_account_id": account_map[to_name],
        },
    )
    assert resp.status_code == 201
    return {"response": resp}


@when(
    parsers.parse(
        'I log an expense of {amount:d} from "{from_name}" for "{desc}" category "{cat}"'
    ),
    target_fixture="response_holder",
)
def log_expense(client, amount, from_name, desc, cat, account_map):
    resp = client.post(
        "/api/v1/transactions/",
        json={
            "amount": amount,
            "description": desc,
            "category": cat,
            "from_account_id": account_map[from_name],
            # to_account_id is None → pure expense
        },
    )
    assert resp.status_code == 201
    return {"response": resp}


# ── Then steps ──────────────────────────────────────────────────────────────
@then(parsers.parse('the "{name}" account balance should be {expected:d}'))
def check_account_balance(client, name, expected, account_map):
    account_id = account_map[name]
    resp = client.get(f"/api/v1/accounts/{account_id}")
    assert resp.status_code == 200
    balance = Decimal(str(resp.json()["current_balance"]))
    assert balance == Decimal(str(expected)), (
        f"Expected balance {expected}, got {balance}"
    )


@then(parsers.parse("the monthly spending on the dashboard should be {expected:d}"))
def check_monthly_spending(client, expected):
    resp = client.get("/api/v1/expenses/dashboard")
    assert resp.status_code == 200
    spending = Decimal(str(resp.json()["monthly_spending"]))
    assert spending == Decimal(str(expected)), (
        f"Expected monthly spending {expected}, got {spending}"
    )


@then(parsers.parse("the net worth on the dashboard should be {expected:d}"))
def check_net_worth(client, expected):
    resp = client.get("/api/v1/expenses/dashboard")
    assert resp.status_code == 200
    net_worth = Decimal(str(resp.json()["net_worth"]))
    assert net_worth == Decimal(str(expected)), (
        f"Expected net worth {expected}, got {net_worth}"
    )


@then(parsers.parse('the category "{category}" spending should be {expected:d}'))
def check_category_spending(client, category, expected):
    resp = client.get("/api/v1/expenses/dashboard")
    assert resp.status_code == 200
    breakdown = resp.json()["category_breakdown"]
    actual = Decimal(str(breakdown.get(category, "0")))
    assert actual == Decimal(str(expected)), (
        f"Expected {category} spending {expected}, got {actual}"
    )
