"""
Step definitions for the Health Check feature.
"""

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/health_check.feature")


# ── Shared state fixture ────────────────────────────────────────────────────
@pytest.fixture()
def response_holder():
    """Mutable container so steps can share the HTTP response object."""
    return {}


# ── When steps ──────────────────────────────────────────────────────────────
@when("I request the root health endpoint", target_fixture="response_holder")
def request_root_health(client):
    resp = client.get("/health")
    return {"response": resp}


@when("I request the API v1 health endpoint", target_fixture="response_holder")
def request_api_v1_health(client):
    resp = client.get("/api/v1/health")
    return {"response": resp}


@when("I request the web health endpoint", target_fixture="response_holder")
def request_web_health(client):
    resp = client.get("/web/health")
    return {"response": resp}


# ── Then steps ──────────────────────────────────────────────────────────────
@then(parsers.parse("I should receive a {status_code:d} status code"))
def check_status_code(response_holder, status_code):
    assert response_holder["response"].status_code == status_code


@then(parsers.parse('the response should contain status "{value}"'))
def check_status_field(response_holder, value):
    body = response_holder["response"].json()
    assert body["status"] == value


@then(parsers.parse('the response should contain app "{value}"'))
def check_app_field(response_holder, value):
    body = response_holder["response"].json()
    assert body["app"] == value


@then(parsers.parse('the response should contain layer "{value}"'))
def check_layer_field(response_holder, value):
    body = response_holder["response"].json()
    assert body["layer"] == value
