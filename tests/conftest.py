"""Test fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def test_client() -> TestClient:
    """API test client.

    :return:
    """
    return TestClient(app)
