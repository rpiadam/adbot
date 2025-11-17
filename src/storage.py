# Dynamic configuration store for runtime-managed settings
from __future__ import annotations

import asyncio
import datetime
import json
from pathlib import Path
from typing import Iterable, Optional

from .config import Settings


class ConfigStore:
    """Persist dynamic configuration such as monitor URLs and RSS feeds."""

    def __init__(self, settings: Settings, path: Path | None = None) -> None:
        self._lock = asyncio.Lock()
        self._path = path or Path("data/config_state.json")
        self._path.parent.mkdir(parents=True, exist_ok=True)

        self._monitor_urls: list[str] = list(settings.monitor_urls)
        self._rss_feeds: list[str] = list(settings.rss_feeds)
        self._credits: dict[str, int] = {}
        self._football_defaults: dict[str, str] = {}
        self._znc_config: dict[str, str] = {}
        self._bluesky_config: dict[str, str] = {}
        self._router_config: dict[str, str] = {}
        self._feature_flags: dict[str, bool] = {
            "games": True,
            "music": True,
            "monitoring": True,
            "rss": True,
            "welcome": True,
            "moderation": True,
            "football": True,
            "znc": True,
        }
        # Store moderation logs (max 1000 entries)
        self._moderation_logs: list[dict] = []
        # Store user warnings/strikes: {guild_id: {user_id: [warnings]}}
        self._user_warnings: dict[str, dict[str, list[dict]]] = {}

        self._load()

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text())
        except (OSError, json.JSONDecodeError):
            return

        monitor_urls = payload.get("monitor_urls")
        if isinstance(monitor_urls, list):
            self._monitor_urls = [str(item).strip() for item in monitor_urls if str(item).strip()]

        rss_feeds = payload.get("rss_feeds")
        if isinstance(rss_feeds, list):
            self._rss_feeds = [str(item).strip() for item in rss_feeds if str(item).strip()]

        credits = payload.get("credits")
        if isinstance(credits, dict):
            normalized: dict[str, int] = {}
            for key, value in credits.items():
                try:
                    normalized[str(int(key))] = int(value)
                except (ValueError, TypeError):
                    continue
            self._credits = normalized

        football_defaults = payload.get("football_defaults")
        if isinstance(football_defaults, dict):
            self._football_defaults = {
                str(key): str(value)
                for key, value in football_defaults.items()
                if isinstance(key, (str, int)) and isinstance(value, (str, int))
            }

        feature_flags = payload.get("feature_flags")
        if isinstance(feature_flags, dict):
            self._feature_flags.update({
                str(key): bool(value)
                for key, value in feature_flags.items()
                if isinstance(key, str)
            })

        znc_config = payload.get("znc_config")
        if isinstance(znc_config, dict):
            self._znc_config = {
                str(key): str(value)
                for key, value in znc_config.items()
                if isinstance(key, str) and isinstance(value, (str, int))
            }

        bluesky_config = payload.get("bluesky_config")
        if isinstance(bluesky_config, dict):
            self._bluesky_config = {
                str(key): str(value)
                for key, value in bluesky_config.items()
                if isinstance(key, str) and isinstance(value, (str, int))
            }

        router_config = payload.get("router_config")
        if isinstance(router_config, dict):
            self._router_config = {
                str(key): str(value)
                for key, value in router_config.items()
                if isinstance(key, str) and isinstance(value, (str, int))
            }

        moderation_logs = payload.get("moderation_logs")
        if isinstance(moderation_logs, list):
            # Keep only last 1000 entries
            self._moderation_logs = moderation_logs[-1000:]

        user_warnings = payload.get("user_warnings")
        if isinstance(user_warnings, dict):
            self._user_warnings = {
                str(guild_id): {
                    str(user_id): list(warnings) if isinstance(warnings, list) else []
                    for user_id, warnings in users.items()
                }
                for guild_id, users in user_warnings.items()
            }

    async def _persist(self) -> None:
        state = {
            "monitor_urls": self._monitor_urls,
            "rss_feeds": self._rss_feeds,
            "credits": self._credits,
            "football_defaults": self._football_defaults,
            "feature_flags": self._feature_flags,
            "znc_config": self._znc_config,
            "bluesky_config": self._bluesky_config,
            "router_config": self._router_config,
            "moderation_logs": self._moderation_logs[-1000:],  # Keep only last 1000
            "user_warnings": self._user_warnings,
        }
        data = json.dumps(state, indent=2, sort_keys=True)
        await asyncio.to_thread(self._path.write_text, data)

    @staticmethod
    def _normalize(items: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        for item in items:
            value = item.strip()
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    # ---------------------------------------------------------------------
    # Monitor URLs management
    # ---------------------------------------------------------------------
    async def list_monitor_urls(self) -> list[str]:
        async with self._lock:
            return list(self._monitor_urls)

    async def add_monitor_url(self, url: str) -> bool:
        from src.utils import validate_url
        
        url = url.strip()
        if not url:
            return False
        
        # Validate URL format
        if not validate_url(url):
            return False
        
        async with self._lock:
            if url in self._monitor_urls:
                return False
            self._monitor_urls.append(url)
            await self._persist()
            return True

    async def remove_monitor_url(self, url: str) -> bool:
        url = url.strip()
        async with self._lock:
            if url not in self._monitor_urls:
                return False
            self._monitor_urls.remove(url)
            await self._persist()
            return True

    # ---------------------------------------------------------------------
    # RSS feeds management
    # ---------------------------------------------------------------------
    async def list_rss_feeds(self) -> list[str]:
        async with self._lock:
            return list(self._rss_feeds)

    async def add_rss_feed(self, url: str) -> bool:
        from src.utils import validate_url
        
        url = url.strip()
        if not url:
            return False
        
        # Validate URL format
        if not validate_url(url):
            return False
        
        async with self._lock:
            if url in self._rss_feeds:
                return False
            self._rss_feeds.append(url)
            await self._persist()
            return True

    async def remove_rss_feed(self, url: str) -> bool:
        url = url.strip()
        async with self._lock:
            if url not in self._rss_feeds:
                return False
            self._rss_feeds.remove(url)
            await self._persist()
            return True

    # ---------------------------------------------------------------------
    # Reload management
    # ---------------------------------------------------------------------
    async def reload_from_disk(self) -> None:
        async with self._lock:
            self._load()

    # ---------------------------------------------------------------------
    # Gamble credits management
    # ---------------------------------------------------------------------
    async def get_credits(self, user_id: int) -> int:
        async with self._lock:
            return self._credits.get(str(user_id), 0)

    async def add_credits(self, user_id: int, amount: int) -> int:
        if amount == 0:
            return await self.get_credits(user_id)
        async with self._lock:
            key = str(user_id)
            balance = self._credits.get(key, 0) + amount
            if balance < 0:
                balance = 0
            self._credits[key] = balance
            await self._persist()
            return balance

    async def set_credits(self, user_id: int, balance: int) -> int:
        if balance < 0:
            balance = 0
        async with self._lock:
            self._credits[str(user_id)] = balance
            await self._persist()
            return balance

    # ---------------------------------------------------------------------
    # Football defaults management
    # ---------------------------------------------------------------------
    async def get_football_defaults(self) -> dict[str, str]:
        async with self._lock:
            return dict(self._football_defaults)

    async def update_football_defaults(
        self,
        *,
        competition: str | None = None,
        team: str | None = None,
        opponent: str | None = None,
        webhook_summary_prefix: str | None = None,
    ) -> dict[str, str]:
        async with self._lock:
            if competition is not None:
                if competition:
                    self._football_defaults["competition"] = competition
                else:
                    self._football_defaults.pop("competition", None)
            if team is not None:
                if team:
                    self._football_defaults["team"] = team
                else:
                    self._football_defaults.pop("team", None)
            if opponent is not None:
                if opponent:
                    self._football_defaults["opponent"] = opponent
                else:
                    self._football_defaults.pop("opponent", None)
            if webhook_summary_prefix is not None:
                if webhook_summary_prefix:
                    self._football_defaults["webhook_summary_prefix"] = webhook_summary_prefix
                else:
                    self._football_defaults.pop("webhook_summary_prefix", None)
            await self._persist()
            return dict(self._football_defaults)

    async def clear_football_defaults(self) -> None:
        async with self._lock:
            self._football_defaults.clear()
            await self._persist()

    # ---------------------------------------------------------------------
    # Feature flags management
    # ---------------------------------------------------------------------
    async def get_feature_flags(self) -> dict[str, bool]:
        async with self._lock:
            return dict(self._feature_flags)

    async def set_feature_flag(self, feature: str, enabled: bool) -> bool:
        async with self._lock:
            if feature not in self._feature_flags:
                return False
            self._feature_flags[feature] = enabled
            await self._persist()
            return True

    async def is_feature_enabled(self, feature: str) -> bool:
        async with self._lock:
            return self._feature_flags.get(feature, False)

    # ---------------------------------------------------------------------
    # ZNC configuration management
    # ---------------------------------------------------------------------
    async def get_znc_config(self) -> dict[str, str]:
        async with self._lock:
            return dict(self._znc_config)

    async def update_znc_config(
        self,
        *,
        base_url: Optional[str] = None,
        admin_username: Optional[str] = None,
        admin_password: Optional[str] = None,
    ) -> dict[str, str]:
        async with self._lock:
            if base_url is not None:
                if base_url:
                    self._znc_config["base_url"] = base_url
                else:
                    self._znc_config.pop("base_url", None)
            if admin_username is not None:
                if admin_username:
                    self._znc_config["admin_username"] = admin_username
                else:
                    self._znc_config.pop("admin_username", None)
            if admin_password is not None:
                if admin_password:
                    self._znc_config["admin_password"] = admin_password
                else:
                    self._znc_config.pop("admin_password", None)
            await self._persist()
            return dict(self._znc_config)

    async def clear_znc_config(self) -> None:
        async with self._lock:
            self._znc_config.clear()
            await self._persist()

    # ---------------------------------------------------------------------
    # Bluesky configuration management
    # ---------------------------------------------------------------------
    async def get_bluesky_config(self) -> dict[str, str]:
        async with self._lock:
            return dict(self._bluesky_config)

    async def update_bluesky_config(
        self,
        *,
        handle: Optional[str] = None,
        app_password: Optional[str] = None,
    ) -> dict[str, str]:
        async with self._lock:
            if handle is not None:
                if handle:
                    self._bluesky_config["handle"] = handle
                else:
                    self._bluesky_config.pop("handle", None)
            if app_password is not None:
                if app_password:
                    self._bluesky_config["app_password"] = app_password
                else:
                    self._bluesky_config.pop("app_password", None)
            await self._persist()
            return dict(self._bluesky_config)

    async def clear_bluesky_config(self) -> None:
        async with self._lock:
            self._bluesky_config.clear()
            await self._persist()

    # ---------------------------------------------------------------------
    # Router configuration management
    # ---------------------------------------------------------------------
    async def get_router_config(self) -> dict[str, str]:
        async with self._lock:
            return dict(self._router_config)

    async def update_router_config(
        self,
        *,
        snmp_host: Optional[str] = None,
        snmp_community: Optional[str] = None,
        stats_interval_seconds: Optional[int] = None,
    ) -> dict[str, str]:
        async with self._lock:
            if snmp_host is not None:
                if snmp_host:
                    self._router_config["snmp_host"] = snmp_host
                else:
                    self._router_config.pop("snmp_host", None)
            if snmp_community is not None:
                if snmp_community:
                    self._router_config["snmp_community"] = snmp_community
                else:
                    self._router_config.pop("snmp_community", None)
            if stats_interval_seconds is not None:
                if stats_interval_seconds > 0:
                    self._router_config["stats_interval_seconds"] = str(stats_interval_seconds)
                else:
                    self._router_config.pop("stats_interval_seconds", None)
            await self._persist()
            return dict(self._router_config)

    async def clear_router_config(self) -> None:
        async with self._lock:
            self._router_config.clear()
            await self._persist()

    # ---------------------------------------------------------------------
    # Moderation logs management
    # ---------------------------------------------------------------------
    async def add_moderation_log(self, log_entry: dict) -> None:
        """Add a moderation log entry."""
        async with self._lock:
            self._moderation_logs.append(log_entry)
            # Keep only last 1000 entries
            if len(self._moderation_logs) > 1000:
                self._moderation_logs = self._moderation_logs[-1000:]
            await self._persist()

    async def get_moderation_logs(self, limit: int = 100) -> list[dict]:
        """Get recent moderation logs."""
        async with self._lock:
            return list(self._moderation_logs[-limit:])

    # ---------------------------------------------------------------------
    # User warnings/strikes management
    # ---------------------------------------------------------------------
    async def add_warning(self, guild_id: int, user_id: int, reason: str, moderator_id: int) -> int:
        """Add a warning to a user. Returns total warning count."""
        async with self._lock:
            guild_key = str(guild_id)
            user_key = str(user_id)
            
            if guild_key not in self._user_warnings:
                self._user_warnings[guild_key] = {}
            if user_key not in self._user_warnings[guild_key]:
                self._user_warnings[guild_key][user_key] = []
            
            warning = {
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "reason": reason,
                "moderator_id": str(moderator_id),
            }
            self._user_warnings[guild_key][user_key].append(warning)
            await self._persist()
            return len(self._user_warnings[guild_key][user_key])

    async def get_warnings(self, guild_id: int, user_id: int) -> list[dict]:
        """Get all warnings for a user."""
        async with self._lock:
            guild_key = str(guild_id)
            user_key = str(user_id)
            return list(self._user_warnings.get(guild_key, {}).get(user_key, []))

    async def clear_warnings(self, guild_id: int, user_id: int) -> bool:
        """Clear all warnings for a user. Returns True if warnings were cleared."""
        async with self._lock:
            guild_key = str(guild_id)
            user_key = str(user_id)
            if guild_key in self._user_warnings and user_key in self._user_warnings[guild_key]:
                del self._user_warnings[guild_key][user_key]
                await self._persist()
                return True
            return False

    async def remove_warning(self, guild_id: int, user_id: int, index: int) -> bool:
        """Remove a specific warning by index. Returns True if removed."""
        async with self._lock:
            guild_key = str(guild_id)
            user_key = str(user_id)
            if guild_key in self._user_warnings and user_key in self._user_warnings[guild_key]:
                warnings = self._user_warnings[guild_key][user_key]
                if 0 <= index < len(warnings):
                    warnings.pop(index)
                    await self._persist()
                    return True
            return False
