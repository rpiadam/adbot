"""Tests for moderation features."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from src.cogs.moderation import ModerationCog
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


@pytest.fixture
def mock_coordinator(mock_settings):
    """Create mock coordinator."""
    coordinator = MagicMock()
    coordinator.settings = mock_settings
    coordinator.config_store = AsyncMock()
    coordinator.config_store.add_moderation_log = AsyncMock()
    return coordinator


@pytest.fixture
def moderation_cog(mock_coordinator):
    """Create moderation cog instance."""
    return ModerationCog(mock_coordinator)


@pytest.mark.asyncio
async def test_check_account_age_new_account(moderation_cog):
    """Test account age check for new account."""
    member = MagicMock(spec=discord.Member)
    member.created_at = datetime.utcnow() - timedelta(days=3)
    
    result = await moderation_cog._check_account_age(member)
    assert result is True  # Should be banned (less than 7 days)


@pytest.mark.asyncio
async def test_check_account_age_old_account(moderation_cog):
    """Test account age check for old account."""
    member = MagicMock(spec=discord.Member)
    member.created_at = datetime.utcnow() - timedelta(days=30)
    
    result = await moderation_cog._check_account_age(member)
    assert result is False  # Should not be banned (older than 7 days)


@pytest.mark.asyncio
async def test_check_account_age_disabled(moderation_cog):
    """Test account age check when disabled."""
    moderation_cog.coordinator.settings.moderation_min_account_age_days = None
    
    member = MagicMock(spec=discord.Member)
    member.created_at = datetime.utcnow() - timedelta(days=1)
    
    result = await moderation_cog._check_account_age(member)
    assert result is False  # Should not be banned (feature disabled)


@pytest.mark.asyncio
async def test_rate_limit_exceeded(moderation_cog):
    """Test rate limit check when exceeded."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 123
    
    # Simulate multiple joins
    for i in range(6):
        result = await moderation_cog._check_rate_limit(guild)
    
    # 6th join should exceed limit of 5
    assert result is True


@pytest.mark.asyncio
async def test_rate_limit_not_exceeded(moderation_cog):
    """Test rate limit check when not exceeded."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 456
    
    # Simulate few joins
    for i in range(3):
        result = await moderation_cog._check_rate_limit(guild)
    
    # Should not exceed limit
    assert result is False


@pytest.mark.asyncio
async def test_rate_limit_disabled(moderation_cog):
    """Test rate limit check when disabled."""
    moderation_cog.coordinator.settings.moderation_join_rate_limit_count = None
    
    guild = MagicMock(spec=discord.Guild)
    guild.id = 789
    
    result = await moderation_cog._check_rate_limit(guild)
    assert result is False  # Should not trigger (feature disabled)


@pytest.mark.asyncio
async def test_log_action_stores_log(moderation_cog):
    """Test that log_action stores log entry."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 123
    guild.name = "Test Guild"
    
    channel = MagicMock(spec=discord.TextChannel)
    moderation_cog._log_channels = {123: channel}
    
    await moderation_cog.log_action(guild, "Test log message")
    
    # Verify log was stored
    moderation_cog.coordinator.config_store.add_moderation_log.assert_called_once()
    call_args = moderation_cog.coordinator.config_store.add_moderation_log.call_args[0][0]
    assert call_args["message"] == "Test log message"
    assert call_args["guild_id"] == "123"
    assert call_args["guild_name"] == "Test Guild"

