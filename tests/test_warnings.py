"""Tests for warning/strike tracking system."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.storage import ConfigStore
from src.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings."""
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
        irc_server="test",
        irc_port=6667,
        irc_tls=False,
        irc_channel="#test",
        irc_nick="test",
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
async def test_add_warning(mock_settings):
    """Test adding a warning."""
    store = ConfigStore(mock_settings)
    
    count = await store.add_warning(123, 456, "Test warning", 789)
    assert count == 1
    
    warnings = await store.get_warnings(123, 456)
    assert len(warnings) == 1
    assert warnings[0]["reason"] == "Test warning"
    assert warnings[0]["moderator_id"] == "789"
    assert "timestamp" in warnings[0]


@pytest.mark.asyncio
async def test_multiple_warnings(mock_settings):
    """Test adding multiple warnings."""
    store = ConfigStore(mock_settings)
    
    count1 = await store.add_warning(123, 456, "First warning", 789)
    assert count1 == 1
    
    count2 = await store.add_warning(123, 456, "Second warning", 789)
    assert count2 == 2
    
    count3 = await store.add_warning(123, 456, "Third warning", 789)
    assert count3 == 3
    
    warnings = await store.get_warnings(123, 456)
    assert len(warnings) == 3


@pytest.mark.asyncio
async def test_get_warnings_empty(mock_settings):
    """Test getting warnings for user with no warnings."""
    store = ConfigStore(mock_settings)
    
    warnings = await store.get_warnings(123, 456)
    assert len(warnings) == 0


@pytest.mark.asyncio
async def test_clear_warnings(mock_settings):
    """Test clearing all warnings."""
    store = ConfigStore(mock_settings)
    
    # Add warnings
    await store.add_warning(123, 456, "Warning 1", 789)
    await store.add_warning(123, 456, "Warning 2", 789)
    
    # Clear
    cleared = await store.clear_warnings(123, 456)
    assert cleared is True
    
    # Verify cleared
    warnings = await store.get_warnings(123, 456)
    assert len(warnings) == 0


@pytest.mark.asyncio
async def test_clear_warnings_nonexistent(mock_settings):
    """Test clearing warnings for user with no warnings."""
    store = ConfigStore(mock_settings)
    
    cleared = await store.clear_warnings(123, 456)
    assert cleared is False


@pytest.mark.asyncio
async def test_remove_warning_by_index(mock_settings):
    """Test removing a specific warning by index."""
    store = ConfigStore(mock_settings)
    
    # Add warnings
    await store.add_warning(123, 456, "Warning 1", 789)
    await store.add_warning(123, 456, "Warning 2", 789)
    await store.add_warning(123, 456, "Warning 3", 789)
    
    # Remove middle warning (index 1)
    removed = await store.remove_warning(123, 456, 1)
    assert removed is True
    
    # Verify
    warnings = await store.get_warnings(123, 456)
    assert len(warnings) == 2
    assert warnings[0]["reason"] == "Warning 1"
    assert warnings[1]["reason"] == "Warning 3"


@pytest.mark.asyncio
async def test_remove_warning_invalid_index(mock_settings):
    """Test removing warning with invalid index."""
    store = ConfigStore(mock_settings)
    
    await store.add_warning(123, 456, "Warning 1", 789)
    
    # Try invalid index
    removed = await store.remove_warning(123, 456, 10)
    assert removed is False
    
    # Verify warning still exists
    warnings = await store.get_warnings(123, 456)
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_warnings_per_guild(mock_settings):
    """Test that warnings are isolated per guild."""
    store = ConfigStore(mock_settings)
    
    # Add warnings to different guilds
    await store.add_warning(123, 456, "Guild 1 warning", 789)
    await store.add_warning(999, 456, "Guild 2 warning", 789)
    
    # Verify isolation
    warnings1 = await store.get_warnings(123, 456)
    warnings2 = await store.get_warnings(999, 456)
    
    assert len(warnings1) == 1
    assert len(warnings2) == 1
    assert warnings1[0]["reason"] == "Guild 1 warning"
    assert warnings2[0]["reason"] == "Guild 2 warning"

