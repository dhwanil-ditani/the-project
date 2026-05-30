"""
Step definitions for the Personal Knowledge Base feature.
"""

import pytest
from pytest_bdd import parsers, scenarios, then, when, given

scenarios("../features/notes.feature")


# ── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture()
def response_holder():
    """Mutable dict to hold the HTTP response between steps."""
    return {}


@pytest.fixture()
def note_map():
    """Maps note titles to their IDs for cross-step reference."""
    return {}


# ── Given steps ─────────────────────────────────────────────────────────────
@given(
    parsers.parse('a note "{title}" with content "{content}"'),
)
def seed_note(client, title, content, note_map):
    resp = client.post(
        "/api/v1/notes/",
        json={"title": title, "content": content},
    )
    assert resp.status_code == 201
    note_map[title] = resp.json()["id"]


# ── When steps ──────────────────────────────────────────────────────────────
@when(
    parsers.parse('I create a note "{title}" with content "{content}"'),
    target_fixture="response_holder",
)
def create_note(client, title, content, note_map):
    resp = client.post(
        "/api/v1/notes/",
        json={"title": title, "content": content},
    )
    if resp.status_code == 201:
        note_map[title] = resp.json()["id"]
    return {"response": resp}


@when(
    parsers.parse('I update note "{title}" with content "{content}"'),
    target_fixture="response_holder",
)
def update_note(client, title, content, note_map):
    note_id = note_map[title]
    resp = client.put(
        f"/api/v1/notes/{note_id}",
        json={"content": content},
    )
    return {"response": resp}


@when("I list all notes", target_fixture="response_holder")
def list_notes(client):
    resp = client.get("/api/v1/notes/")
    return {"response": resp}


# ── Then steps ──────────────────────────────────────────────────────────────
@then(parsers.parse("I should receive a {status_code:d} status code"))
def check_status(response_holder, status_code):
    assert response_holder["response"].status_code == status_code


@then(parsers.parse('a note titled "{title}" should exist as a placeholder'))
def check_placeholder_exists(client, title, note_map):
    resp = client.get("/api/v1/notes/")
    assert resp.status_code == 200
    notes = resp.json()
    matching = [n for n in notes if n["title"] == title]
    assert len(matching) == 1, f"Expected placeholder '{title}', found: {[n['title'] for n in notes]}"
    # Placeholder has empty content
    assert matching[0]["content"] == ""
    note_map[title] = matching[0]["id"]


@then(parsers.parse("the graph should have {count:d} nodes"))
def check_node_count(client, count):
    resp = client.get("/api/v1/notes/graph")
    assert resp.status_code == 200
    assert len(resp.json()["nodes"]) == count


@then(parsers.parse("the graph should have {count:d} edges"))
def check_edge_count(client, count):
    resp = client.get("/api/v1/notes/graph")
    assert resp.status_code == 200
    assert len(resp.json()["edges"]) == count


@then(parsers.parse('there should be an edge from "{from_title}" to "{to_title}"'))
def check_edge_exists(client, from_title, to_title, note_map):
    # Resolve IDs
    _ensure_note_ids(client, note_map, from_title, to_title)

    from_id = note_map[from_title]
    to_id = note_map[to_title]

    resp = client.get("/api/v1/notes/graph")
    assert resp.status_code == 200
    edges = resp.json()["edges"]

    matching = [e for e in edges if e["from_id"] == from_id and e["to_id"] == to_id]
    assert len(matching) == 1, (
        f"Expected edge {from_title}({from_id}) → {to_title}({to_id}), "
        f"found edges: {edges}"
    )


@then(parsers.parse('there should be no edge from "{from_title}" to "{to_title}"'))
def check_edge_not_exists(client, from_title, to_title, note_map):
    _ensure_note_ids(client, note_map, from_title, to_title)

    from_id = note_map[from_title]
    to_id = note_map[to_title]

    resp = client.get("/api/v1/notes/graph")
    assert resp.status_code == 200
    edges = resp.json()["edges"]

    matching = [e for e in edges if e["from_id"] == from_id and e["to_id"] == to_id]
    assert len(matching) == 0, (
        f"Expected NO edge {from_title}({from_id}) → {to_title}({to_id}), "
        f"but found: {matching}"
    )


@then(parsers.parse("the response should contain {count:d} notes"))
def check_notes_count(response_holder, count):
    body = response_holder["response"].json()
    assert len(body) == count


# ── Helpers ─────────────────────────────────────────────────────────────────
def _ensure_note_ids(client, note_map, *titles):
    """Load note IDs from the API if not already cached in note_map."""
    missing = [t for t in titles if t not in note_map]
    if missing:
        resp = client.get("/api/v1/notes/")
        assert resp.status_code == 200
        for note in resp.json():
            if note["title"] in missing:
                note_map[note["title"]] = note["id"]
