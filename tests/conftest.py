"""Pytest configuration and shared fixtures."""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from src.config import Settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def minimal_settings():
    """Create minimal settings for testing."""
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
        dashboard_username=None,
        dashboard_password=None,
        dashboard_secret_key="test_secret_key",
        bluesky_handle=None,
        bluesky_app_password=None,
        router_snmp_host=None,
        router_snmp_community=None,
        router_stats_interval_seconds=3600,
        weather_api_key=None,
    )

