import asyncio
import logging
import os
import sys
import time
from typing import Optional, Union

import discord
import httpx
import pydle
from discord.ext import commands
from telegram import Update
from telegram.ext import AIORateLimiter, Application, ContextTypes, MessageHandler, filters

from .config import Settings
from .cogs import (
    AdminCog,
    ChocolateCog,
    FeaturesCog,
    FloodCog,
    FootballCog,
    GamesCog,
    HelpCog,
    ModerationCog,
    MonitoringCog,
    MusicCog,
    POTACog,
    RSSCog,
    WelcomeCog,
    ZNCCog,
)
from .cogs.configuration import ConfigurationCog
from .storage import ConfigStore


logger = logging.getLogger(__name__)


class IRCRelayClient(pydle.Client):
    """IRC client that forwards events back to the relay coordinator."""

    def __init__(self, coordinator: "RelayCoordinator"):
        loop = asyncio.get_running_loop()
        super().__init__(
            nickname=coordinator.settings.irc_nick,
            realname=coordinator.settings.irc_nick,
            eventloop=loop,
        )
        self.coordinator = coordinator
        self.target_channel = coordinator.settings.irc_channel
        self._is_first_connect = True

    async def on_connect(self):
        await super().on_connect()
        await self.join(self.target_channel)
        # Only count as reconnect if not the first connection
        if not self._is_first_connect:
            self.coordinator.record_irc_reconnect()
        self._is_first_connect = False
        logger.info("Connected to IRC %s:%s as %s", self.coordinator.settings.irc_server, self.coordinator.settings.irc_port, self.nickname)

    async def on_message(self, target, source, message):
        await super().on_message(target, source, message)
        if target.casefold() != self.target_channel.casefold():
            return
        if source == self.nickname:
            # Ignore echoes of our own messages.
            return
        await self.coordinator.handle_irc_message(source, message)

    async def on_quit(self, user, message=None):
        await super().on_quit(user, message)
        if user == self.nickname:
            return
        await self.coordinator.handle_irc_quit(user, message or "")

    async def on_disconnect(self, expected):
        await super().on_disconnect(expected)
        logger.warning("Disconnected from IRC (expected=%s)", expected)
        if not expected:
            # Unexpected disconnect - attempt to reconnect
            logger.info("Attempting to reconnect to IRC...")
            try:
                await asyncio.sleep(5)  # Wait before reconnecting
                await self.connect(
                    self.coordinator.settings.irc_server,
                    self.coordinator.settings.irc_port,
                    tls=self.coordinator.settings.irc_tls,
                )
            except Exception as e:
                logger.error("Failed to reconnect to IRC: %s", e)
                self.coordinator.record_error()


class DiscordRelayBot(commands.Bot):
    """Discord bot that bridges messages to IRC."""

    def __init__(self, coordinator: "RelayCoordinator"):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        intents.guilds = True
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            help_command=None,
        )
        self.coordinator = coordinator

    async def setup_hook(self) -> None:
        await self.coordinator.on_discord_setup()
        await self.add_cog(HelpCog(self))
        await self.add_cog(FeaturesCog(self, self.coordinator))
        await self.add_cog(GamesCog(self.coordinator))
        await self.add_cog(ModerationCog(self.coordinator))
        await self.add_cog(AdminCog(self, self.coordinator))
        await self.add_cog(WelcomeCog(self.coordinator))
        await self.add_cog(ConfigurationCog(self.coordinator))
        await self.add_cog(FootballCog(self.coordinator))
        await self.add_cog(MonitoringCog(self.coordinator))
        await self.add_cog(RSSCog(self.coordinator))
        await self.add_cog(POTACog(self.coordinator))
        await self.add_cog(ChocolateCog(self.coordinator))
        await self.add_cog(MusicCog(self, self.coordinator))
        await self.add_cog(ZNCCog(self.coordinator))
        await self.add_cog(FloodCog(self.coordinator))
        # Commands will be synced in on_discord_ready to avoid duplicates

    async def on_ready(self) -> None:
        # Check if this is a reconnection
        if self.coordinator._discord_channel is not None:
            self.coordinator.record_discord_reconnect()
            logger.info("Discord bot reconnected as %s", self.user)
        await self.coordinator.on_discord_ready()
        logger.info("Discord bot connected as %s", self.user)

    async def on_resume(self) -> None:
        """Called when the bot resumes a session."""
        self.coordinator.record_discord_reconnect()
        logger.info("Discord bot session resumed")

    async def on_disconnect(self) -> None:
        """Called when the bot disconnects."""
        logger.warning("Discord bot disconnected")
        self.coordinator.record_error()

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.channel.id != self.coordinator.settings.discord_channel_id:
            return
        await self.coordinator.handle_discord_message(message)
        await self.process_commands(message)


class RelayCoordinator:
    """Coordinates state between Discord, IRC, and webhook announcers."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.config_store = ConfigStore(settings)
        self.discord_bot = DiscordRelayBot(self)
        self.irc_client = IRCRelayClient(self)
        self._discord_channel: Optional[discord.TextChannel] = None
        self._discord_webhook: Optional[discord.Webhook] = None
        self._lock = asyncio.Lock()
        self._restart_task: Optional[asyncio.Task] = None
        self._guild_id: Optional[int] = settings.discord_guild_id
        self._slash_synced = False
        # Health tracking
        self._start_time = time.time()
        self._error_count = 0
        self._last_error_time: Optional[float] = None
        self._discord_reconnect_count = 0
        self._irc_reconnect_count = 0
        self._message_count = 0
        self._last_message_time: Optional[float] = None

    def get_uptime(self) -> float:
        """Get bot uptime in seconds."""
        return time.time() - self._start_time

    def record_error(self) -> None:
        """Record an error occurrence."""
        self._error_count += 1
        self._last_error_time = time.time()

    def record_message(self) -> None:
        """Record a message being relayed."""
        self._message_count += 1
        self._last_message_time = time.time()

    def record_discord_reconnect(self) -> None:
        """Record a Discord reconnection."""
        self._discord_reconnect_count += 1

    def record_irc_reconnect(self) -> None:
        """Record an IRC reconnection."""
        self._irc_reconnect_count += 1

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in seconds to human-readable string."""
        if seconds < 0:
            return "0s"
        
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        
        return " ".join(parts) if parts else "0s"

    def get_health_stats(self) -> dict:
        """Get system health statistics."""
        uptime_seconds = self.get_uptime()
        uptime_hours = uptime_seconds / 3600
        uptime_days = uptime_seconds / 86400
        
        discord_ready = self.discord_bot.is_ready() if self.discord_bot else False
        irc_connected = self.irc_client.connected if self.irc_client else False
        
        # Calculate message rate (messages per hour)
        message_rate = 0.0
        if uptime_seconds > 0:
            message_rate = (self._message_count / uptime_seconds) * 3600
        
        # Calculate time since last message
        time_since_last_message = None
        if self._last_message_time:
            time_since_last_message = time.time() - self._last_message_time
        
        # Determine overall health status
        health_status = "healthy"
        if not discord_ready or not irc_connected:
            health_status = "degraded"
        if self._error_count > 100 or (self._last_error_time and (time.time() - self._last_error_time) < 60):
            health_status = "unhealthy"
        
        return {
            "uptime_seconds": uptime_seconds,
            "uptime_hours": round(uptime_hours, 2),
            "uptime_days": round(uptime_days, 2),
            "uptime_formatted": self._format_uptime(uptime_seconds),
            "error_count": self._error_count,
            "last_error_time": self._last_error_time,
            "discord_connected": discord_ready,
            "irc_connected": irc_connected,
            "discord_reconnect_count": self._discord_reconnect_count,
            "irc_reconnect_count": self._irc_reconnect_count,
            "message_count": self._message_count,
            "message_rate_per_hour": round(message_rate, 2),
            "time_since_last_message": round(time_since_last_message, 2) if time_since_last_message else None,
            "health_status": health_status,
        }

    async def on_discord_setup(self) -> None:
        logger.debug("Discord setup hook invoked")

    async def on_discord_ready(self) -> None:
        if self._discord_channel is None:
            channel = self.discord_bot.get_channel(self.settings.discord_channel_id)
            if channel is None:
                channel = await self.discord_bot.fetch_channel(self.settings.discord_channel_id)
            if not isinstance(channel, discord.TextChannel):
                raise RuntimeError("Configured channel ID is not a text channel")
            self._discord_channel = channel
            logger.info("Bridging Discord channel #%s (%s)", channel.name, channel.id)
            await channel.send("🔗 IRC relay is online.")
        if not self._slash_synced:
            guild = self._discord_channel.guild
            try:
                # Only sync guild-specific commands to avoid duplicates with global commands
                if guild:
                    await self.discord_bot.tree.sync(guild=guild)
                else:
                    # No guild available, sync global commands
                    await self.discord_bot.tree.sync()
            except discord.HTTPException:
                logger.exception("Failed to sync application commands for guild %s", guild.id if guild else "global")
            else:
                logger.info("Slash commands synced for guild %s", guild.id if guild else "global")
                self._slash_synced = True

    async def handle_discord_message(self, message: discord.Message) -> None:
        self.record_message()
        content_parts = []
        if message.clean_content:
            content_parts.append(message.clean_content)
        if message.attachments:
            attachment_urls = " ".join(attachment.url for attachment in message.attachments)
            content_parts.append(f"[attachments] {attachment_urls}")
        content = "\n".join(part for part in content_parts if part).strip()
        if not content:
            return
        prefix = f"<{message.author.display_name}>"
        await self.send_to_irc(f"{prefix} {content}")

    async def handle_irc_message(self, author: str, content: str) -> None:
        self.record_message()
        channel = await self._ensure_discord_channel()
        author_label = author.strip()
        allowed_mentions = discord.AllowedMentions.none()
        webhook = await self._ensure_discord_webhook(channel)
        if webhook is not None:
            await webhook.send(
                content,
                username=author_label or "IRC",
                allowed_mentions=allowed_mentions,
            )
        else:
            formatted = f"**<{author_label}>** {content}"
            await channel.send(formatted, allowed_mentions=allowed_mentions)

    async def handle_irc_quit(self, author: str, reason: str) -> None:
        channel = await self._ensure_discord_channel()
        allowed_mentions = discord.AllowedMentions.none()
        author_label = author.strip() or "IRC user"
        parts = [f"🔌 **{author_label}** left IRC"]
        reason = reason.strip()
        if reason:
            parts.append(f"— {reason}")
        await channel.send(" ".join(parts), allowed_mentions=allowed_mentions)

    async def announce_football_event(self, summary: str) -> None:
        channel = await self._ensure_discord_channel()
        await channel.send(summary)
        await self.send_to_irc(summary)
        await self.send_to_discord_webhook(summary)

    async def _ensure_discord_channel(self) -> discord.TextChannel:
        if self._discord_channel is not None:
            return self._discord_channel
        async with self._lock:
            if self._discord_channel is None:
                channel = self.discord_bot.get_channel(self.settings.discord_channel_id)
                if channel is None:
                    channel = await self.discord_bot.fetch_channel(self.settings.discord_channel_id)
                if not isinstance(channel, discord.TextChannel):
                    raise RuntimeError("Configured channel ID is not a text channel")
                self._discord_channel = channel
                self._guild_id = channel.guild.id
        return self._discord_channel

    async def _ensure_discord_webhook(
        self,
        channel: Optional[discord.TextChannel] = None,
    ) -> Optional[discord.Webhook]:
        if self._discord_webhook is not None:
            return self._discord_webhook
        if channel is None:
            channel = await self._ensure_discord_channel()
        # Prefer user-provided webhook URL if available.
        if self.settings.discord_webhook_url:
            try:
                session = self.discord_bot.http._HTTPClient__session  # type: ignore[attr-defined]
            except AttributeError:
                session = None
            if session is None:
                return None
            self._discord_webhook = discord.Webhook.from_url(
                self.settings.discord_webhook_url,
                session=session,
            )
            return self._discord_webhook

        try:
            existing = await channel.webhooks()
        except discord.Forbidden:
            logger.warning("Unable to list webhooks for channel %s; lacking permissions.", channel.id)
            return None
        except discord.HTTPException:
            logger.exception("Failed to fetch webhooks for channel %s", channel.id)
            return None

        for webhook in existing:
            if webhook.user == self.discord_bot.user and webhook.name == "UpLove IRC Relay":
                self._discord_webhook = webhook
                break

        if self._discord_webhook is None:
            try:
                self._discord_webhook = await channel.create_webhook(name="UpLove IRC Relay")
            except discord.Forbidden:
                logger.warning("Missing Manage Webhooks permission; falling back to bot messages.")
            except discord.HTTPException:
                logger.exception("Failed to create webhook for channel %s", channel.id)

        return self._discord_webhook

    async def ensure_guild_id(self) -> Optional[int]:
        if self._guild_id is not None:
            return self._guild_id
        channel = await self._ensure_discord_channel()
        self._guild_id = channel.guild.id
        return self._guild_id

    async def send_to_irc(self, message: str) -> None:
        if not self.irc_client.connected:
            logger.warning("Dropping message; IRC client not connected: %s", message)
            self.record_error()
            return
        try:
            await self.irc_client.message(self.settings.irc_channel, message)
        except Exception as e:
            logger.error("Failed to send message to IRC: %s", e)
            self.record_error()
            raise

    async def stop_irc(self) -> bool:
        if not self.irc_client.connected:
            return False
        try:
            await self.irc_client.quit(message="IRC relay disconnected via command")
        except Exception:  # pragma: no cover - operational logging
            logger.exception("Failed to disconnect from IRC on command.")
            raise
        return True

    async def send_to_discord_webhook(
        self,
        message: str,
        *,
        username: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> None:
        if not self.settings.discord_webhook_url:
            return
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.settings.discord_webhook_url,
                    json={
                        "content": message,
                        "username": username,
                        "avatar_url": avatar_url,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("Failed to deliver message to Discord webhook.")

    async def reload_runtime(self) -> None:
        await self.config_store.reload_from_disk()
        guild_id = self.settings.discord_guild_id
        try:
            if guild_id:
                guild = discord.Object(id=guild_id)
                # Only sync guild-specific commands to avoid duplicates
                await self.discord_bot.tree.sync(guild=guild)
            else:
                # Sync global commands if no guild specified
                await self.discord_bot.tree.sync()
        except discord.HTTPException:
            logger.exception("Failed to sync commands during reload")
        logger.info("Runtime configuration reloaded and commands synced.")

    async def request_restart(self) -> None:
        if self._restart_task and not self._restart_task.done():
            return

        async def _perform_restart() -> None:
            try:
                await self.shutdown()
            finally:
                os.execv(sys.executable, [sys.executable, "-m", "src.main"])

        self._restart_task = asyncio.create_task(_perform_restart())

    async def start_discord(self) -> None:
        await self.discord_bot.start(self.settings.discord_token)

    async def _recreate_irc_client(self) -> None:
        """Recreate the IRC client instance if needed."""
        try:
            if self.irc_client.connected:
                await self.irc_client.disconnect(expected=False)
        except Exception:
            pass
        # Create a new client instance to avoid state issues
        self.irc_client = IRCRelayClient(self)

    async def start_irc(self) -> None:
        """Start the IRC client with proper error handling."""
        while True:
            try:
                if not self.irc_client.connected:
                    await self.irc_client.connect(
                        self.settings.irc_server,
                        self.settings.irc_port,
                        tls=self.settings.irc_tls,
                    )
                await self.irc_client.handle_forever()
            except asyncio.CancelledError:
                logger.info("IRC client task cancelled")
                break
            except (ConnectionResetError, OSError) as e:
                logger.warning("IRC connection lost (%s), reconnecting...", type(e).__name__)
                await self._recreate_irc_client()
                await asyncio.sleep(5)
                continue
            except RuntimeError as e:
                if "readuntil() called while another coroutine is already waiting" in str(e):
                    logger.warning("IRC connection read conflict detected, recreating client...")
                    await self._recreate_irc_client()
                    await asyncio.sleep(2)
                    continue
                else:
                    logger.exception("Unexpected RuntimeError in IRC client")
                    await self._recreate_irc_client()
                    await asyncio.sleep(5)
                    continue
            except Exception as e:
                logger.exception("Error in IRC client, attempting to reconnect: %s", e)
                await self._recreate_irc_client()
                await asyncio.sleep(5)
                continue

    async def shutdown(self) -> None:
        if self.discord_bot.is_closed():
            logger.debug("Discord bot already closed")
        else:
            await self.discord_bot.close()
        if self.irc_client.connected:
            await self.irc_client.quit(message="Relay shutting down")


