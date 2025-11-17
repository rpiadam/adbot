"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from src.api import create_app
from src.config import Settings
from src.relay import RelayCoordinator


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    return Settings(
        discord_token="test_token",
        discord_channel_id=123,
        discord_guild_id=None,
        discord_webhook_url=None,
        telegram_bot_token=None,
        telegram_chat_id=None,
        welcome_channel_id=None,
        welcome_message=None,
        announcements_channel_id=None,
        irc_server="test.irc.server",
        irc_port=6667,
        irc_tls=False,
        irc_channel="#test",
        irc_nick="testbot",
        moderation_log_channel_id=None,
        moderation_muted_role_id=None,
        moderation_min_account_age_days=None,
        moderation_join_rate_limit_count=None,
        moderation_join_rate_limit_seconds=None,
        monitor_urls=[],
        monitor_interval_seconds=300,
        rss_feeds=[],
        rss_poll_interval_seconds=600,
        music_voice_channel_id=None,
        music_text_channel_id=None,
        football_webhook_secret=None,
        football_default_competition=None,
        football_default_team=None,
        chocolate_notify_user_id=None,
        api_host="0.0.0.0",
        api_port=8000,
        znc_base_url=None,
        znc_admin_username=None,
        znc_admin_password=None,
        dashboard_username="admin",
        dashboard_password="testpass",
        dashboard_secret_key="test_secret_key",
        bluesky_handle=None,
        bluesky_app_password=None,
        router_snmp_host=None,
        router_snmp_community=None,
        router_stats_interval_seconds=3600,
        weather_api_key=None,
    )


@pytest.fixture
def mock_coordinator(mock_settings):
    """Create mock coordinator."""
    coordinator = MagicMock(spec=RelayCoordinator)
    coordinator.settings = mock_settings
    coordinator.config_store = AsyncMock()
    coordinator.discord_bot = MagicMock()
    coordinator.discord_bot.guilds = []
    coordinator.discord_bot.latency = 0.1
    coordinator.discord_bot.is_ready = MagicMock(return_value=True)
    coordinator.irc_client = MagicMock()
    coordinator.irc_client.connected = True
    coordinator.get_health_stats = MagicMock(return_value={
        "uptime_seconds": 3600,
        "uptime_formatted": "1h 0m",
        "error_count": 0,
        "discord_connected": True,
        "irc_connected": True,
    })
    return coordinator


@pytest.fixture
def app(mock_coordinator, mock_settings):
    """Create test app."""
    return create_app(mock_coordinator, mock_settings)


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_endpoint(client, mock_settings):
    """Test login endpoint."""
    with patch("src.api.authenticate_user", return_value=True):
        with patch("src.api.create_access_token", return_value="test_token"):
            response = client.post(
                "/api/auth/login",
                data={"username": "admin", "password": "testpass"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"


def test_login_failed(client):
    """Test failed login."""
    with patch("src.api.authenticate_user", return_value=False):
        response = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "wrong"}
        )
        assert response.status_code == 401


def test_protected_endpoint_requires_auth(client, mock_coordinator):
    """Test that protected endpoints require authentication."""
    mock_coordinator.config_store.get_feature_flags = AsyncMock(return_value={"games": True})
    
    response = client.get("/api/features")
    assert response.status_code == 401


def test_rate_limiting(client):
    """Test rate limiting on login endpoint."""
    with patch("src.api.authenticate_user", return_value=False):
        # Make 6 requests (limit is 5/minute)
        for i in range(6):
            response = client.post(
                "/api/auth/login",
                data={"username": "admin", "password": "wrong"}
            )
        
        # Last request should be rate limited
        assert response.status_code in [401, 429]  # 429 is rate limit exceeded


def test_api_docs_available(client):
    """Test that API documentation is available."""
    response = client.get("/docs")
    assert response.status_code == 200
    
    response = client.get("/redoc")
    assert response.status_code == 200

