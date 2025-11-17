"""Integration tests for bot functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import discord

from src.relay import RelayCoordinator
from src.config import Settings
from src.storage import ConfigStore


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
        moderation_log_channel_id=456,
        moderation_muted_role_id=789,
        moderation_min_account_age_days=7,
        moderation_join_rate_limit_count=5,
        moderation_join_rate_limit_seconds=60,
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


@pytest.mark.asyncio
async def test_warning_system_integration(mock_settings):
    """Test warning system integration with storage."""
    coordinator = MagicMock(spec=RelayCoordinator)
    coordinator.settings = mock_settings
    coordinator.config_store = ConfigStore(mock_settings)
    
    guild_id = 123
    user_id = 456
    moderator_id = 789
    
    # Add warnings
    count1 = await coordinator.config_store.add_warning(guild_id, user_id, "First warning", moderator_id)
    assert count1 == 1
    
    count2 = await coordinator.config_store.add_warning(guild_id, user_id, "Second warning", moderator_id)
    assert count2 == 2
    
    # Retrieve warnings
    warnings = await coordinator.config_store.get_warnings(guild_id, user_id)
    assert len(warnings) == 2
    assert warnings[0]["reason"] == "First warning"
    assert warnings[1]["reason"] == "Second warning"
    
    # Clear warnings
    cleared = await coordinator.config_store.clear_warnings(guild_id, user_id)
    assert cleared is True
    
    # Verify cleared
    warnings = await coordinator.config_store.get_warnings(guild_id, user_id)
    assert len(warnings) == 0


@pytest.mark.asyncio
async def test_moderation_log_storage(mock_settings):
    """Test moderation log storage and retrieval."""
    coordinator = MagicMock(spec=RelayCoordinator)
    coordinator.settings = mock_settings
    coordinator.config_store = ConfigStore(mock_settings)
    
    # Add log entries
    log1 = {
        "timestamp": datetime.utcnow().isoformat(),
        "guild_id": "123",
        "guild_name": "Test Guild",
        "message": "Test log entry 1"
    }
    await coordinator.config_store.add_moderation_log(log1)
    
    log2 = {
        "timestamp": datetime.utcnow().isoformat(),
        "guild_id": "123",
        "guild_name": "Test Guild",
        "message": "Test log entry 2"
    }
    await coordinator.config_store.add_moderation_log(log2)
    
    # Retrieve logs
    logs = await coordinator.config_store.get_moderation_logs(limit=10)
    assert len(logs) >= 2
    assert logs[-1]["message"] == "Test log entry 1"
    assert logs[-2]["message"] == "Test log entry 2"


@pytest.mark.asyncio
async def test_feature_flags_storage(mock_settings):
    """Test feature flag storage and retrieval."""
    coordinator = MagicMock(spec=RelayCoordinator)
    coordinator.settings = mock_settings
    coordinator.config_store = ConfigStore(mock_settings)
    
    # Set feature flags
    await coordinator.config_store.set_feature_flag("games", False)
    await coordinator.config_store.set_feature_flag("moderation", True)
    
    # Retrieve flags
    flags = await coordinator.config_store.get_feature_flags()
    assert flags["games"] is False
    assert flags["moderation"] is True


@pytest.mark.asyncio
async def test_monitor_urls_management(mock_settings):
    """Test monitor URL management."""
    coordinator = MagicMock(spec=RelayCoordinator)
    coordinator.settings = mock_settings
    coordinator.config_store = ConfigStore(mock_settings)
    
    # Add URLs
    added1 = await coordinator.config_store.add_monitor_url("https://example.com")
    assert added1 is True
    
    added2 = await coordinator.config_store.add_monitor_url("https://test.com")
    assert added2 is True
    
    # List URLs
    urls = await coordinator.config_store.list_monitor_urls()
    assert "https://example.com" in urls
    assert "https://test.com" in urls
    
    # Remove URL
    removed = await coordinator.config_store.remove_monitor_url("https://example.com")
    assert removed is True
    
    # Verify removed
    urls = await coordinator.config_store.list_monitor_urls()
    assert "https://example.com" not in urls
    assert "https://test.com" in urls


@pytest.mark.asyncio
async def test_rss_feeds_management(mock_settings):
    """Test RSS feed management."""
    coordinator = MagicMock(spec=RelayCoordinator)
    coordinator.settings = mock_settings
    coordinator.config_store = ConfigStore(mock_settings)
    
    # Add feeds
    added1 = await coordinator.config_store.add_rss_feed("https://example.com/feed.xml")
    assert added1 is True
    
    added2 = await coordinator.config_store.add_rss_feed("https://test.com/rss")
    assert added2 is True
    
    # List feeds
    feeds = await coordinator.config_store.list_rss_feeds()
    assert "https://example.com/feed.xml" in feeds
    assert "https://test.com/rss" in feeds
    
    # Remove feed
    removed = await coordinator.config_store.remove_rss_feed("https://example.com/feed.xml")
    assert removed is True
    
    # Verify removed
    feeds = await coordinator.config_store.list_rss_feeds()
    assert "https://example.com/feed.xml" not in feeds
    assert "https://test.com/rss" in feeds

