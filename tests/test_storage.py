"""Tests for storage and configuration management."""

import pytest
import asyncio
from pathlib import Path
import json
import tempfile

from src.storage import ConfigStore
from src.config import Settings, IRCNetworkConfig


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = Path(f.name)
    yield temp_path
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        discord_token="test",
        discord_channel_id=123,
        discord_guild_id=None,
        discord_webhook_url=None,
        telegram_bot_token=None,
        telegram_chat_id=None,
        welcome_channel_id=None,
        welcome_message=None,
        announcements_channel_id=None,
        irc_networks=[
            IRCNetworkConfig(
                server="irc.test",
                port=6667,
                tls=False,
                channel="#test",
                nick="testbot",
            )
        ],
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
        dashboard_username=None,
        dashboard_password=None,
        dashboard_secret_key="test",
        bluesky_handle=None,
        bluesky_app_password=None,
        router_snmp_host=None,
        router_snmp_community=None,
        router_stats_interval_seconds=3600,
        weather_api_key=None,
    )


@pytest.mark.asyncio
async def test_monitor_urls(temp_config_file, test_settings):
    """Test monitor URL management."""
    store = ConfigStore(test_settings, path=temp_config_file)
    
    # Add URLs
    assert await store.add_monitor_url("https://example.com") is True
    assert await store.add_monitor_url("https://test.com") is True
    
    # Duplicate should fail
    assert await store.add_monitor_url("https://example.com") is False
    
    # List URLs
    urls = await store.list_monitor_urls()
    assert "https://example.com" in urls
    assert "https://test.com" in urls
    
    # Remove URL
    assert await store.remove_monitor_url("https://example.com") is True
    urls = await store.list_monitor_urls()
    assert "https://example.com" not in urls
    assert "https://test.com" in urls
    
    # Remove non-existent should fail
    assert await store.remove_monitor_url("https://nonexistent.com") is False


@pytest.mark.asyncio
async def test_monitor_metadata_and_history(temp_config_file, test_settings):
    """Ensure monitor metadata and history are persisted."""
    store = ConfigStore(test_settings, path=temp_config_file)

    url = "https://history.test"
    assert await store.add_monitor_url(url) is True

    metadata = await store.update_monitor_metadata(
        url,
        keyword="ok",
        expected_status=200,
    )
    assert metadata == {"keyword": "ok", "expected_status": 200}

    sample = {
        "timestamp": "2025-01-01T00:00:00Z",
        "status_code": 200,
        "latency_ms": 123.4,
        "is_up": True,
        "reason": None,
    }
    await store.record_monitor_sample(url, sample, max_entries=5)

    history = await store.get_monitor_history(url, limit=5)
    assert len(history) == 1
    assert history[0]["latency_ms"] == 123.4

    snapshot = await store.get_monitor_snapshot(url)
    assert snapshot["is_up"] is True


@pytest.mark.asyncio
async def test_rss_feeds(temp_config_file, test_settings):
    """Test RSS feed management."""
    store = ConfigStore(test_settings, path=temp_config_file)
    
    # Add feeds
    assert await store.add_rss_feed("https://example.com/feed.xml") is True
    assert await store.add_rss_feed("https://test.com/rss") is True
    
    # List feeds
    feeds = await store.list_rss_feeds()
    assert "https://example.com/feed.xml" in feeds
    assert "https://test.com/rss" in feeds
    
    # Remove feed
    assert await store.remove_rss_feed("https://example.com/feed.xml") is True
    feeds = await store.list_rss_feeds()
    assert "https://example.com/feed.xml" not in feeds


@pytest.mark.asyncio
async def test_feature_flags(temp_config_file, test_settings):
    """Test feature flag management."""
    store = ConfigStore(test_settings, path=temp_config_file)
    
    # Get all flags
    flags = await store.get_feature_flags()
    assert isinstance(flags, dict)
    assert "games" in flags
    
    # Check if feature is enabled
    assert await store.is_feature_enabled("games") is True
    
    # Toggle feature
    assert await store.set_feature_flag("games", False) is True
    assert await store.is_feature_enabled("games") is False
    
    # Toggle non-existent feature should fail
    assert await store.set_feature_flag("nonexistent", True) is False


@pytest.mark.asyncio
async def test_moderation_logs(temp_config_file, test_settings):
    """Test moderation log storage."""
    store = ConfigStore(test_settings, path=temp_config_file)
    
    # Add log entries
    log1 = {"timestamp": "2024-01-01T00:00:00", "message": "Test log 1"}
    log2 = {"timestamp": "2024-01-01T00:01:00", "message": "Test log 2"}
    
    await store.add_moderation_log(log1)
    await store.add_moderation_log(log2)
    
    # Get logs
    logs = await store.get_moderation_logs(limit=10)
    assert len(logs) == 2
    assert logs[-1]["message"] == "Test log 2"  # Most recent last
    
    # Test limit
    logs = await store.get_moderation_logs(limit=1)
    assert len(logs) == 1

