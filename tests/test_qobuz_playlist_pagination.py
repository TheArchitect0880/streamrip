from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from streamrip.client.qobuz import QobuzClient


@pytest.fixture
def mock_config():
    config = MagicMock()
    session = MagicMock()
    qobuz = MagicMock()
    downloads = MagicMock()

    config.session = session
    session.qobuz = qobuz
    session.downloads = downloads

    qobuz.app_id = "12345"
    qobuz.email_or_userid = "test@example.com"
    qobuz.password_or_token = "test_token"
    qobuz.use_auth_token = True
    qobuz.secrets = ["secret1", "secret2"]
    downloads.verify_ssl = True
    downloads.requests_per_minute = 100

    return config


@pytest.fixture
def mock_qobuz_client(mock_config):
    with patch.object(QobuzClient, "login", AsyncMock(return_value=None)):
        with patch.object(QobuzClient, "get_session", AsyncMock()):
            client = QobuzClient(mock_config)
            client.session = MagicMock()
            client.logged_in = True
            client.secret = "test_secret"
            yield client


@pytest.mark.asyncio
async def test_get_playlist_pagination(mock_qobuz_client):
    first_page_response = {
        "tracks_count": 1200,
        "tracks": {
            "items": [{"id": f"track_{i}"} for i in range(500)],
        },
    }
    second_page_response = {
        "tracks": {
            "items": [{"id": f"track_{i}"} for i in range(500, 1000)],
        },
    }
    third_page_response = {
        "tracks": {
            "items": [{"id": f"track_{i}"} for i in range(1000, 1200)],
        },
    }

    async def mock_api_request(endpoint, params):
        if params.get("offset") == 0:
            return 200, first_page_response
        if params.get("offset") == 500:
            return 200, second_page_response
        if params.get("offset") == 1000:
            return 200, third_page_response
        return 404, {"message": "Not found"}

    mock_qobuz_client._api_request = AsyncMock(side_effect=mock_api_request)

    result = await mock_qobuz_client.get_playlist("test_playlist_id")

    assert mock_qobuz_client._api_request.call_count == 3
    assert len(result["tracks"]["items"]) == 1200
    for i in range(1200):
        assert result["tracks"]["items"][i]["id"] == f"track_{i}"


@pytest.mark.asyncio
async def test_get_playlist_small(mock_qobuz_client):
    small_playlist_response = {
        "tracks_count": 100,
        "tracks": {
            "items": [{"id": f"track_{i}"} for i in range(100)],
        },
    }

    mock_qobuz_client._api_request = AsyncMock(
        return_value=(200, small_playlist_response)
    )

    result = await mock_qobuz_client.get_playlist("test_small_playlist_id")

    assert mock_qobuz_client._api_request.call_count == 1
    assert len(result["tracks"]["items"]) == 100
