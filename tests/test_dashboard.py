"""Tests for dashboard authentication and utilities."""

import pytest
from datetime import timedelta

from src.dashboard import (
    get_password_hash,
    verify_password,
    create_access_token,
    verify_token,
    authenticate_user,
)
from src.config import Settings


def test_password_hashing():
    """Test password hashing and verification."""
    password = "test_password_123"
    hashed = get_password_hash(password)
    
    # Hash should be different from plain password
    assert hashed != password
    # Hash should start with bcrypt identifier
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    
    # Verification should work
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_jwt_token():
    """Test JWT token creation and verification."""
    secret_key = "test_secret_key"
    data = {"sub": "test_user"}
    
    token = create_access_token(data, secret_key, expires_delta=timedelta(hours=1))
    
    # Token should be a string
    assert isinstance(token, str)
    assert len(token) > 0
    
    # Verification should work
    payload = verify_token(token, secret_key)
    assert payload is not None
    assert payload["sub"] == "test_user"
    
    # Wrong secret should fail
    wrong_payload = verify_token(token, "wrong_secret")
    assert wrong_payload is None


def test_authenticate_user_plain_text():
    """Test authentication with plain text password."""
    settings = Settings(
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
        dashboard_username="admin",
        dashboard_password="plaintext123",
        dashboard_secret_key="test_secret",
        bluesky_handle=None,
        bluesky_app_password=None,
        router_snmp_host=None,
        router_snmp_community=None,
        router_stats_interval_seconds=3600,
        weather_api_key=None,
    )
    
    # Correct credentials
    assert authenticate_user("admin", "plaintext123", settings) is True
    
    # Wrong username
    assert authenticate_user("wrong_user", "plaintext123", settings) is False
    
    # Wrong password
    assert authenticate_user("admin", "wrong_password", settings) is False


def test_authenticate_user_hashed():
    """Test authentication with hashed password."""
    password = "hashed_password_123"
    hashed = get_password_hash(password)
    
    settings = Settings(
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
        dashboard_username="admin",
        dashboard_password=hashed,
        dashboard_secret_key="test_secret",
        bluesky_handle=None,
        bluesky_app_password=None,
        router_snmp_host=None,
        router_snmp_community=None,
        router_stats_interval_seconds=3600,
        weather_api_key=None,
    )
    
    # Correct credentials
    assert authenticate_user("admin", password, settings) is True
    
    # Wrong password
    assert authenticate_user("admin", "wrong_password", settings) is False

