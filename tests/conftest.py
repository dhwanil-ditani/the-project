"""
Shared pytest fixtures for the test suite.
"""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture()
def client() -> TestClient:
    """Provide a synchronous test client for the FastAPI app."""
    return TestClient(app)
