"""
Step definitions for the Unified Tasks Engine feature.
"""

from datetime import datetime, timedelta, timezone

import pytest
from pytest_bdd import parsers, scenarios, then, when, given

scenarios("../features/tasks.feature")


# ── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture()
def response_holder():
    """Mutable dict to hold the HTTP response between steps."""
    return {}


@pytest.fixture()
def rule_holder():
    """Mutable dict to hold the created rule's data."""
    return {}


@pytest.fixture()
def task_holder():
    """Mutable dict to hold the created task's data."""
    return {}


# ── Given steps — Lazy Evaluation scenarios ─────────────────────────────────
@given(
    parsers.parse('a non-strict recurring rule "{title}" with daily schedule'),
    target_fixture="rule_holder",
)
def create_non_strict_rule(client, title):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    resp = client.post(
        "/api/v1/recurring/",
        json={
            "task_title": title,
            "rrule_string": "FREQ=DAILY",
            "is_strict": False,
            "next_due": yesterday,
        },
    )
    assert resp.status_code == 201
    return resp.json()


@given(
    parsers.parse('a strict recurring rule "{title}" with monthly schedule'),
    target_fixture="rule_holder",
)
def create_strict_rule(client, title):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    resp = client.post(
        "/api/v1/recurring/",
        json={
            "task_title": title,
            "rrule_string": "FREQ=MONTHLY",
            "is_strict": True,
            "next_due": yesterday,
        },
    )
    assert resp.status_code == 201
    return resp.json()


@given(
    parsers.parse('a pending task "{title}" linked to that rule due yesterday'),
    target_fixture="task_holder",
)
def create_linked_task_due_yesterday(client, title, rule_holder):
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    resp = client.post(
        "/api/v1/tasks/",
        json={
            "title": title,
            "due_date": yesterday,
            "rule_id": rule_holder["id"],
        },
    )
    assert resp.status_code == 201
    return resp.json()


@given(
    parsers.parse("there are {count:d} tasks in the database"),
    target_fixture="task_holder",
)
def seed_tasks(client, count):
    ids = []
    for i in range(count):
        resp = client.post(
            "/api/v1/tasks/",
            json={"title": f"Task {i}", "priority": "Medium"},
        )
        assert resp.status_code == 201
        ids.append(resp.json()["id"])
    return {"ids": ids}


@given(
    parsers.parse('a pending high priority task "{title}" due today'),
    target_fixture="task_holder",
)
def create_high_priority_task(client, title):
    now = datetime.now(timezone.utc).isoformat()
    resp = client.post(
        "/api/v1/tasks/",
        json={"title": title, "priority": "High", "due_date": now},
    )
    assert resp.status_code == 201
    return resp.json()


@given(
    parsers.parse('a pending low priority task "{title}" due today'),
)
def create_low_priority_task(client, title):
    now = datetime.now(timezone.utc).isoformat()
    resp = client.post(
        "/api/v1/tasks/",
        json={"title": title, "priority": "Low", "due_date": now},
    )
    assert resp.status_code == 201


@given(
    parsers.parse('a pending medium priority task "{title}" due today'),
)
def create_medium_priority_task(client, title):
    now = datetime.now(timezone.utc).isoformat()
    resp = client.post(
        "/api/v1/tasks/",
        json={"title": title, "priority": "Medium", "due_date": now},
    )
    assert resp.status_code == 201


# ── When steps ──────────────────────────────────────────────────────────────
@when("I load the today dashboard", target_fixture="response_holder")
def load_dashboard(client):
    resp = client.get("/api/v1/dashboard/today")
    return {"response": resp}


@when(
    parsers.parse('I create a task with title "{title}" and priority "{priority}"'),
    target_fixture="response_holder",
)
def create_task_api(client, title, priority):
    resp = client.post(
        "/api/v1/tasks/",
        json={"title": title, "priority": priority},
    )
    return {"response": resp}


@when("I list all tasks", target_fixture="response_holder")
def list_tasks_api(client):
    resp = client.get("/api/v1/tasks/")
    return {"response": resp}


@when(
    parsers.parse('I create a recurring rule "{title}" with rrule "{rrule}"'),
    target_fixture="response_holder",
)
def create_rule_api(client, title, rrule):
    resp = client.post(
        "/api/v1/recurring/",
        json={"task_title": title, "rrule_string": rrule},
    )
    return {"response": resp}


# ── Then steps ──────────────────────────────────────────────────────────────
@then(parsers.parse("I should receive a {status_code:d} status code"))
def check_status(response_holder, status_code):
    assert response_holder["response"].status_code == status_code


@then(parsers.parse('the original task status should be "{expected_status}"'))
def check_original_task_missed(client, task_holder, expected_status):
    task_id = task_holder["id"]
    resp = client.get(f"/api/v1/tasks/{task_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == expected_status


@then(
    parsers.parse(
        'a new pending task "{title}" should be spawned for the future'
    )
)
def check_spawned_task(client, title, task_holder):
    original_id = task_holder["id"]
    resp = client.get("/api/v1/tasks/")
    assert resp.status_code == 200
    tasks = resp.json()

    # Find a task with the same title but different ID and Pending status
    spawned = [
        t for t in tasks
        if t["title"] == title and t["id"] != original_id and t["status"] == "Pending"
    ]
    assert len(spawned) >= 1, f"Expected a spawned task '{title}', found: {tasks}"


@then(parsers.parse('the overdue task "{title}" should still be "{expected_status}"'))
def check_strict_task_still_pending(client, title, expected_status, task_holder):
    task_id = task_holder["id"]
    resp = client.get(f"/api/v1/tasks/{task_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == title
    assert body["status"] == expected_status


@then(parsers.parse('the task response should have title "{title}"'))
def check_task_title(response_holder, title):
    body = response_holder["response"].json()
    assert body["title"] == title


@then(parsers.parse('the task response should have priority "{priority}"'))
def check_task_priority(response_holder, priority):
    body = response_holder["response"].json()
    assert body["priority"] == priority


@then(parsers.parse("the response should contain {count:d} tasks"))
def check_tasks_count(response_holder, count):
    body = response_holder["response"].json()
    assert len(body) == count


@then(parsers.parse('the rule response should have task_title "{title}"'))
def check_rule_title(response_holder, title):
    body = response_holder["response"].json()
    assert body["task_title"] == title


@then(parsers.parse('the first action item should be "{title}"'))
def check_first_item(response_holder, title):
    body = response_holder["response"].json()
    assert len(body) > 0, "Dashboard returned no items"
    assert body[0]["title"] == title


@then(parsers.parse('the last action item should be "{title}"'))
def check_last_item(response_holder, title):
    body = response_holder["response"].json()
    assert len(body) > 0, "Dashboard returned no items"
    assert body[-1]["title"] == title
