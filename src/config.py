import base64
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _get_decryption_key() -> Optional[bytes]:
    """Get the decryption key from environment or key file.
    
    Fernet keys are base64-encoded 32-byte keys. Returns bytes suitable for Fernet.
    """
    # First try environment variable
    key_str = os.getenv("ENCRYPTION_KEY")
    if key_str:
        try:
            # Fernet keys are already base64-encoded strings, decode them
            return key_str.encode()
        except Exception:
            logger.warning("Invalid ENCRYPTION_KEY format in environment")
            return None
    
    # Then try key file (more secure, not in process env)
    key_file = os.getenv("ENCRYPTION_KEY_FILE", ".encryption_key")
    if os.path.exists(key_file):
        try:
            with open(key_file, "rb") as f:
                key_bytes = f.read().strip()
            # Key file should contain base64-encoded string
            return key_bytes
        except Exception as e:
            logger.warning("Failed to read encryption key file: %s", e)
            return None
    
    return None


def _load_encrypted_env_if_needed() -> None:
    """Check for encrypted .env file and decrypt it before loading.
    
    Supports:
    - ENV_FILE environment variable pointing to encrypted file
    - .env.encrypted file (if .env doesn't exist)
    """
    env_file = os.getenv("ENV_FILE", ".env")
    
    # Check if the specified file is encrypted
    env_path = Path(env_file)
    if env_path.exists():
        # Try to detect if file is encrypted by attempting to decrypt it
        key = _get_decryption_key()
        if key is not None:
            try:
                with open(env_path, "rb") as f:
                    encrypted_data = f.read()
                
                # Try to decrypt - if it works, the file is encrypted
                fernet = Fernet(key)
                try:
                    decrypted = fernet.decrypt(encrypted_data)
                    # File is encrypted, create temp file with decrypted content
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as tmp:
                        tmp.write(decrypted.decode())
                        tmp_path = tmp.name
                    
                    # Load from temp file
                    load_dotenv(tmp_path, override=True)
                    logger.info(f"Loaded encrypted environment from {env_file}")
                    
                    # Clean up temp file after a short delay
                    # (Note: This is best-effort cleanup)
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass  # Cleanup failure is non-critical
                    return
                except Exception:
                    # Not encrypted or wrong key, fall through to normal loading
                    pass
            except Exception as e:
                logger.debug(f"Error checking for encrypted file: {e}")
    
    # Check for .env.encrypted if .env doesn't exist
    if not Path(".env").exists() and Path(".env.encrypted").exists():
        key = _get_decryption_key()
        if key is not None:
            try:
                with open(".env.encrypted", "rb") as f:
                    encrypted_data = f.read()
                
                fernet = Fernet(key)
                decrypted = fernet.decrypt(encrypted_data)
                
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.env') as tmp:
                    tmp.write(decrypted.decode())
                    tmp_path = tmp.name
                
                load_dotenv(tmp_path, override=True)
                logger.info("Loaded encrypted environment from .env.encrypted")
                
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                return
            except Exception as e:
                logger.warning(f"Found .env.encrypted but failed to decrypt: {e}")
                logger.warning("Falling back to normal .env loading")
    
    # Normal dotenv loading
    load_dotenv()


# Load environment (with encrypted file support)
_load_encrypted_env_if_needed()


def _decrypt_value(encrypted_value: str) -> Optional[str]:
    """Decrypt an encrypted environment variable value."""
    if not encrypted_value.startswith("encrypted:"):
        return encrypted_value
    
    # Remove "encrypted:" prefix
    encrypted_data = encrypted_value[10:]
    
    key = _get_decryption_key()
    if key is None:
        logger.warning("Encrypted value detected but no decryption key available")
        return None
    
    try:
        # Decode base64 encrypted value
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception as e:
        logger.error("Failed to decrypt value: %s", e)
        return None


def _get_env(name: str, *, required: bool = True, default: Optional[str] = None) -> Optional[str]:
    """Read an environment variable and optionally enforce its presence.
    
    Automatically decrypts values prefixed with "encrypted:" if ENCRYPTION_KEY or
    ENCRYPTION_KEY_FILE is configured.
    """
    value = os.getenv(name, default)
    if value is None and required:
        raise RuntimeError(f"Missing required environment variable: {name}")
    
    if value and value.startswith("encrypted:"):
        decrypted = _decrypt_value(value)
        if decrypted is None:
            raise RuntimeError(f"Failed to decrypt encrypted environment variable: {name}")
        return decrypted
    
    return value


def _parse_optional_int(raw: Optional[str]) -> Optional[int]:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid integer value: {raw}") from exc


def _parse_csv(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class IRCNetworkConfig:
    """Configuration for a single IRC network."""
    server: str
    port: int
    tls: bool
    channel: str
    nick: str
    # Optional NickServ/server password for this network.
    password: Optional[str] = None


@dataclass(frozen=True)
class Settings:
    discord_token: str
    discord_channel_id: int
    discord_guild_id: Optional[int]
    discord_webhook_url: Optional[str]
    telegram_bot_token: Optional[str]
    telegram_chat_id: Optional[str]
    welcome_channel_id: Optional[int]
    welcome_message: Optional[str]
    announcements_channel_id: Optional[int]
    irc_networks: list[IRCNetworkConfig]
    moderation_log_channel_id: Optional[int]
    moderation_muted_role_id: Optional[int]
    moderation_min_account_age_days: Optional[int]
    moderation_join_rate_limit_count: Optional[int]
    moderation_join_rate_limit_seconds: Optional[int]
    monitor_urls: list[str]
    monitor_interval_seconds: int
    rss_feeds: list[str]
    rss_poll_interval_seconds: int
    music_voice_channel_id: Optional[int]
    music_text_channel_id: Optional[int]
    football_webhook_secret: Optional[str]
    football_default_competition: Optional[str]
    football_default_team: Optional[str]
    chocolate_notify_user_id: Optional[int]
    api_host: str
    api_port: int
    znc_base_url: Optional[str]
    znc_admin_username: Optional[str]
    znc_admin_password: Optional[str]
    dashboard_username: Optional[str]
    dashboard_password: Optional[str]
    dashboard_secret_key: Optional[str]
    bluesky_handle: Optional[str]
    bluesky_app_password: Optional[str]
    router_snmp_host: Optional[str]
    router_snmp_community: Optional[str]
    router_stats_interval_seconds: int
    weather_api_key: Optional[str]
    idlerpg_username: Optional[str]
    idlerpg_password: Optional[str]

    @classmethod
    def from_env(cls) -> "Settings":
        discord_channel_id = int(_get_env("DISCORD_CHANNEL_ID"))
        guild_raw = _get_env("DISCORD_GUILD_ID", required=False)
        discord_guild_id = int(guild_raw) if guild_raw else None

        # Parse IRC networks - support both single network (backward compatible) and multiple networks
        irc_networks = []
        
        # Check for new multi-network format
        irc_servers_raw = _get_env("IRC_SERVERS", required=False)
        if irc_servers_raw:
            # Multi-network format: comma-separated lists
            irc_servers = _parse_csv(irc_servers_raw)
            irc_ports_raw = _get_env("IRC_PORTS", required=False, default="")
            irc_ports_list = [int(p.strip()) if p.strip() else 6667 for p in irc_ports_raw.split(",")] if irc_ports_raw else []
            irc_tls_raw = _get_env("IRC_TLS", required=False, default="")
            irc_tls_list = [t.lower() in {"1", "true", "yes"} for t in irc_tls_raw.split(",")] if irc_tls_raw else []
            irc_channels_raw = _get_env("IRC_CHANNELS", required=False, default="")
            irc_channels = _parse_csv(irc_channels_raw) if irc_channels_raw else []
            irc_nicks_raw = _get_env("IRC_NICKS", required=False, default="")
            irc_nicks = _parse_csv(irc_nicks_raw) if irc_nicks_raw else []
            irc_passwords_raw = _get_env("IRC_PASSWORDS", required=False, default="")
            irc_passwords = _parse_csv(irc_passwords_raw) if irc_passwords_raw else []
            
            # Default values
            default_port = int(_get_env("IRC_PORT", required=False, default="6667"))
            default_tls = _get_env("IRC_TLS", required=False, default="false").lower() in {"1", "true", "yes"}
            default_nick = _get_env("IRC_NICK", required=False, default="UpLove")
            
            for i, server in enumerate(irc_servers):
                port = irc_ports_list[i] if i < len(irc_ports_list) else default_port
                tls = irc_tls_list[i] if i < len(irc_tls_list) else default_tls
                channel = irc_channels[i] if i < len(irc_channels) else ""
                nick = irc_nicks[i] if i < len(irc_nicks) else default_nick
                password = irc_passwords[i] if i < len(irc_passwords) else None
                
                if not channel:
                    raise RuntimeError(f"IRC_CHANNELS must have an entry for each server (missing for server {i+1})")
                
                irc_networks.append(IRCNetworkConfig(
                    server=server,
                    port=port,
                    tls=tls,
                    channel=channel,
                    nick=nick,
                    password=password,
                ))
        else:
            # Single network format (backward compatible)
            irc_port = int(_get_env("IRC_PORT", required=False, default="6667"))
            irc_tls = _get_env("IRC_TLS", required=False, default="false").lower() in {"1", "true", "yes"}
            irc_password = _get_env("IRC_PASSWORD", required=False)
            irc_networks.append(IRCNetworkConfig(
                server=_get_env("IRC_SERVER"),
                port=irc_port,
                tls=irc_tls,
                channel=_get_env("IRC_CHANNEL"),
                nick=_get_env("IRC_NICK"),
                password=irc_password,
            ))

        settings = cls(
            discord_token=_get_env("DISCORD_TOKEN"),
            discord_channel_id=discord_channel_id,
            discord_guild_id=discord_guild_id,
            discord_webhook_url=_get_env("DISCORD_WEBHOOK_URL", required=False),
            telegram_bot_token=_get_env("TELEGRAM_BOT_TOKEN", required=False),
            telegram_chat_id=_get_env("TELEGRAM_CHAT_ID", required=False),
            welcome_channel_id=_parse_optional_int(_get_env("WELCOME_CHANNEL_ID", required=False)),
            welcome_message=_get_env("WELCOME_MESSAGE", required=False),
            announcements_channel_id=_parse_optional_int(_get_env("ANNOUNCEMENTS_CHANNEL_ID", required=False)),
            irc_networks=irc_networks,
            moderation_log_channel_id=_parse_optional_int(_get_env("MODERATION_LOG_CHANNEL_ID", required=False)),
            moderation_muted_role_id=_parse_optional_int(_get_env("MODERATION_MUTED_ROLE_ID", required=False)),
            moderation_min_account_age_days=_parse_optional_int(_get_env("MODERATION_MIN_ACCOUNT_AGE_DAYS", required=False)),
            moderation_join_rate_limit_count=_parse_optional_int(_get_env("MODERATION_JOIN_RATE_LIMIT_COUNT", required=False)),
            moderation_join_rate_limit_seconds=_parse_optional_int(_get_env("MODERATION_JOIN_RATE_LIMIT_SECONDS", required=False)),
            monitor_urls=_parse_csv(_get_env("MONITOR_URLS", required=False)),
            monitor_interval_seconds=int(_get_env("MONITOR_INTERVAL_SECONDS", required=False, default="300")),
            rss_feeds=_parse_csv(_get_env("RSS_FEEDS", required=False)),
            rss_poll_interval_seconds=int(_get_env("RSS_POLL_INTERVAL_SECONDS", required=False, default="600")),
            music_voice_channel_id=_parse_optional_int(_get_env("MUSIC_VOICE_CHANNEL_ID", required=False)),
            music_text_channel_id=_parse_optional_int(_get_env("MUSIC_TEXT_CHANNEL_ID", required=False)),
            football_webhook_secret=_get_env("FOOTBALL_WEBHOOK_SECRET", required=False),
            football_default_competition=_get_env("FOOTBALL_DEFAULT_COMPETITION", required=False),
            football_default_team=_get_env("FOOTBALL_DEFAULT_TEAM", required=False),
            chocolate_notify_user_id=_parse_optional_int(_get_env("CHOCOLATE_NOTIFY_USER_ID", required=False)),
            api_host=_get_env("API_HOST", required=False, default="0.0.0.0"),
            api_port=int(_get_env("API_PORT", required=False, default="8000")),
            znc_base_url=_get_env("ZNC_BASE_URL", required=False),
            znc_admin_username=_get_env("ZNC_ADMIN_USERNAME", required=False),
            znc_admin_password=_get_env("ZNC_ADMIN_PASSWORD", required=False),
            dashboard_username=_get_env("DASHBOARD_USERNAME", required=False),
            dashboard_password=_get_env("DASHBOARD_PASSWORD", required=False),
            dashboard_secret_key=_get_env("DASHBOARD_SECRET_KEY", required=False, default="change-me-in-production"),
            bluesky_handle=_get_env("BLUESKY_HANDLE", required=False),
            bluesky_app_password=_get_env("BLUESKY_APP_PASSWORD", required=False),
            router_snmp_host=_get_env("ROUTER_SNMP_HOST", required=False),
            router_snmp_community=_get_env("ROUTER_SNMP_COMMUNITY", required=False),
            router_stats_interval_seconds=int(_get_env("ROUTER_STATS_INTERVAL_SECONDS", required=False, default="3600")),
            weather_api_key=_get_env("WEATHER_API_KEY", required=False),
            idlerpg_username=_get_env("IDLERPG_USERNAME", required=False),
            idlerpg_password=_get_env("IDLERPG_PASSWORD", required=False),
        )

        logger.debug("Loaded settings: %s", settings)
        return settings

    def validate(self) -> list[str]:
        """Validate settings and return list of errors (empty if valid)."""
        errors = []
        
        # Required fields
        if not self.discord_token or self.discord_token == "replace-me":
            errors.append("DISCORD_TOKEN is required and must not be 'replace-me'")
        
        if not self.discord_channel_id:
            errors.append("DISCORD_CHANNEL_ID is required")
        
        # Validate IRC networks
        if not self.irc_networks:
            errors.append("At least one IRC network must be configured (IRC_SERVER or IRC_SERVERS)")
        
        for i, network in enumerate(self.irc_networks):
            if not network.server:
                errors.append(f"IRC network {i+1}: server is required")
            if not network.channel:
                errors.append(f"IRC network {i+1}: channel is required")
            if not network.nick:
                errors.append(f"IRC network {i+1}: nick is required")
            if not (1 <= network.port <= 65535):
                errors.append(f"IRC network {i+1}: port must be between 1 and 65535 (got {network.port})")
        
        if not (1 <= self.api_port <= 65535):
            errors.append(f"API_PORT must be between 1 and 65535 (got {self.api_port})")
        
        # Validate moderation settings
        if self.moderation_min_account_age_days is not None and self.moderation_min_account_age_days < 0:
            errors.append("MODERATION_MIN_ACCOUNT_AGE_DAYS must be >= 0")
        
        if self.moderation_join_rate_limit_count is not None:
            if self.moderation_join_rate_limit_count < 1:
                errors.append("MODERATION_JOIN_RATE_LIMIT_COUNT must be >= 1")
            if self.moderation_join_rate_limit_seconds is None:
                errors.append("MODERATION_JOIN_RATE_LIMIT_SECONDS is required when MODERATION_JOIN_RATE_LIMIT_COUNT is set")
        
        if self.moderation_join_rate_limit_seconds is not None:
            if self.moderation_join_rate_limit_seconds < 1:
                errors.append("MODERATION_JOIN_RATE_LIMIT_SECONDS must be >= 1")
            if self.moderation_join_rate_limit_count is None:
                errors.append("MODERATION_JOIN_RATE_LIMIT_COUNT is required when MODERATION_JOIN_RATE_LIMIT_SECONDS is set")
        
        # Validate dashboard settings
        if self.dashboard_username and not self.dashboard_password:
            errors.append("DASHBOARD_PASSWORD is required when DASHBOARD_USERNAME is set")
        
        if self.dashboard_password and not self.dashboard_username:
            errors.append("DASHBOARD_USERNAME is required when DASHBOARD_PASSWORD is set")
        
        if self.dashboard_secret_key == "change-me-in-production":
            errors.append("DASHBOARD_SECRET_KEY should be changed from default value for production")
        
        # Validate interval settings
        if self.monitor_interval_seconds < 60:
            errors.append("MONITOR_INTERVAL_SECONDS should be at least 60 seconds")
        
        if self.rss_poll_interval_seconds < 60:
            errors.append("RSS_POLL_INTERVAL_SECONDS should be at least 60 seconds")
        
        return errors


def validate_settings(settings: Settings) -> None:
    """Validate settings and raise RuntimeError if invalid."""
    errors = settings.validate()
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
        logger.error(error_msg)
        raise RuntimeError(error_msg)


settings = Settings.from_env()

