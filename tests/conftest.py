"""Test fixtures and configuration."""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def test_client() -> TestClient:
    """API test client.

    :return: TestClient instance
    """
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    # Set test environment variables
    os.environ["TMDB_API_KEY"] = "test_api_key_12345"
    os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000,http://test.com"

    yield

    # Clean up (optional)
    if "TMDB_API_KEY" in os.environ:
        del os.environ["TMDB_API_KEY"]
    if "ALLOWED_ORIGINS" in os.environ:
        del os.environ["ALLOWED_ORIGINS"]


@pytest.fixture
def mock_tmdb_api_key():
    """Mock TMDB API key for testing."""
    with patch.dict(os.environ, {"TMDB_API_KEY": "test_api_key_12345"}):
        yield "test_api_key_12345"


@pytest.fixture
def sample_movie_data():
    """Sample movie data for testing."""
    return {
        "id": 27205,
        "original_title": "Inception",
        "overview": "Cobb, a skilled thief who commits corporate espionage...",
        "release_date": "2010-07-16",
        "vote_average": 8.4,
        "vote_count": 25000,
        "runtime": 148,
        "genres": [{"id": 28, "name": "Action"}, {"id": 878, "name": "Sci-Fi"}],
        "poster_path": "/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg",
        "backdrop_path": "/s3TBrRGB1iav7gFOCNx3H31MoES.jpg",
        "budget": 160000000,
        "revenue": 836836967,
        "status": "Released",
    }


@pytest.fixture
def sample_series_data():
    """Sample series data for testing."""
    return {
        "id": 1396,
        "name": "Breaking Bad",
        "overview": "When an unassuming chemistry teacher...",
        "first_air_date": "2008-01-20",
        "vote_average": 9.5,
        "vote_count": 15000,
        "genres": [{"id": 18, "name": "Drama"}, {"id": 80, "name": "Crime"}],
        "poster_path": "/ggFHVNu6YYI5L9pCfOacjizRGt.jpg",
        "backdrop_path": "/tsRy63Mu5cu8etL1X7ZLyf7UP1M.jpg",
        "number_of_seasons": 5,
        "number_of_episodes": 62,
        "status": "Ended",
    }


@pytest.fixture
def mock_search_results():
    """Mock search results for testing."""
    return [
        {
            "id": 27205,
            "original_title": "Inception",
            "overview": "Cobb, a skilled thief...",
            "release_date": "2010-07-16",
            "vote_average": 8.4,
            "poster": "https://image.tmdb.org/t/p/w500/...",
        },
        {
            "id": 550,
            "original_title": "Fight Club",
            "overview": "A ticking-time-bomb insomniac...",
            "release_date": "1999-10-15",
            "vote_average": 8.8,
            "poster": "https://image.tmdb.org/t/p/w500/...",
        },
    ]


@pytest.fixture
def mock_series_search_results():
    """Mock series search results for testing."""
    return [
        {
            "id": 1396,
            "name": "Breaking Bad",
            "air_date": "2008-01-20",
            "vote_avg": 9.5,
            "overview": "When an unassuming chemistry teacher...",
            "poster": "https://image.tmdb.org/t/p/w500/...",
        },
        {
            "id": 1399,
            "name": "Game of Thrones",
            "air_date": "2011-04-17",
            "vote_avg": 9.3,
            "overview": "Seven noble families fight for control...",
            "poster": "https://image.tmdb.org/t/p/w500/...",
        },
    ]
