"""
Step definitions for the Bookmarks CRUD feature.
"""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import parsers, scenarios, then, when, given

scenarios("../features/bookmarks.feature")


# ── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture()
def bookmark_payload():
    """Mutable dict to hold the bookmark creation payload."""
    return {}


@pytest.fixture()
def response_holder():
    """Mutable dict to hold the HTTP response between steps."""
    return {}


@pytest.fixture()
def bookmark_id_holder():
    """Mutable dict to track a created bookmark's ID."""
    return {}


# ── Mock scraper ────────────────────────────────────────────────────────────
def _mock_scraper():
    """Return a patched scraper that returns deterministic metadata."""
    from src.services.scraper import ScrapedMetadata

    mock = AsyncMock(
        return_value=ScrapedMetadata(
            title="Scraped Title",
            description="Scraped description from the page.",
            favicon_url="https://example.com/favicon.ico",
        )
    )
    return patch("src.api.v1.bookmarks.scrape_url_metadata", mock)


# ── Given steps ─────────────────────────────────────────────────────────────
@given(
    parsers.parse('I have a bookmark payload with url "{url}" and title "{title}"'),
    target_fixture="bookmark_payload",
)
def payload_with_title(url, title):
    return {"url": url, "title": title}


@given(
    parsers.parse('I have a bookmark payload with url "{url}" and no title'),
    target_fixture="bookmark_payload",
)
def payload_without_title(url):
    return {"url": url}


@given(
    parsers.parse("there are {count:d} bookmarks in the database"),
    target_fixture="bookmark_id_holder",
)
def seed_bookmarks(client, count):
    ids = []
    for i in range(count):
        resp = client.post(
            "/api/v1/bookmarks/",
            json={"url": f"https://example.com/{i}", "title": f"Bookmark {i}"},
        )
        assert resp.status_code == 201
        ids.append(resp.json()["id"])
    return {"ids": ids}


@given(
    parsers.parse('there is a bookmark with url "{url}" in the database'),
    target_fixture="bookmark_id_holder",
)
def seed_single_bookmark(client, url):
    resp = client.post(
        "/api/v1/bookmarks/",
        json={"url": url, "title": "Seeded Bookmark"},
    )
    assert resp.status_code == 201
    return {"id": resp.json()["id"]}


@given(
    parsers.parse(
        'I have a bookmark payload with url "{url}" and tags "{tags_csv}"'
    ),
    target_fixture="bookmark_payload",
)
def payload_with_tags(url, tags_csv):
    tags = [t.strip() for t in tags_csv.split(",")]
    return {"url": url, "title": "Tagged Bookmark", "tags": tags}


# ── When steps ──────────────────────────────────────────────────────────────
@when("I create the bookmark", target_fixture="response_holder")
def create_bookmark(client, bookmark_payload):
    needs_scraping = "title" not in bookmark_payload or bookmark_payload.get("title") is None

    if needs_scraping:
        with _mock_scraper():
            resp = client.post("/api/v1/bookmarks/", json=bookmark_payload)
    else:
        resp = client.post("/api/v1/bookmarks/", json=bookmark_payload)

    return {"response": resp}


@when("I list all bookmarks", target_fixture="response_holder")
def list_bookmarks(client):
    resp = client.get("/api/v1/bookmarks/")
    return {"response": resp}


@when("I get the bookmark by its ID", target_fixture="response_holder")
def get_bookmark(client, bookmark_id_holder):
    bid = bookmark_id_holder.get("id") or bookmark_id_holder.get("ids", [None])[0]
    resp = client.get(f"/api/v1/bookmarks/{bid}")
    return {"response": resp}


@when("I delete the bookmark by its ID", target_fixture="response_holder")
def delete_bookmark(client, bookmark_id_holder):
    bid = bookmark_id_holder.get("id")
    resp = client.delete(f"/api/v1/bookmarks/{bid}")
    return {"response": resp}


# ── Then steps ──────────────────────────────────────────────────────────────
@then(parsers.parse("I should receive a {status_code:d} status code"))
def check_status(response_holder, status_code):
    assert response_holder["response"].status_code == status_code


@then(parsers.parse('the bookmark response should have title "{title}"'))
def check_title(response_holder, title):
    body = response_holder["response"].json()
    assert body["title"] == title


@then(parsers.parse('the bookmark response should have url "{url}"'))
def check_url(response_holder, url):
    body = response_holder["response"].json()
    assert body["url"] == url


@then("the bookmark response should have a scraped title")
def check_scraped_title(response_holder):
    body = response_holder["response"].json()
    assert body["title"] == "Scraped Title"
    assert body["description"] == "Scraped description from the page."


@then(parsers.parse("the response should contain {count:d} bookmarks"))
def check_bookmark_count(response_holder, count):
    body = response_holder["response"].json()
    assert len(body) == count


@then(parsers.parse("the bookmark response should have {count:d} tags"))
def check_tag_count(response_holder, count):
    body = response_holder["response"].json()
    assert len(body["tags"]) == count
