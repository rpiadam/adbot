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

    def __init__(self, coordinator: "RelayCoordinator", network_config):
        loop = asyncio.get_running_loop()
        fallback_nicks = [f"{network_config.nick}_{i}" for i in range(1, 4)]
        super().__init__(
            nickname=network_config.nick,
            fallback_nicknames=fallback_nicks,
            realname=network_config.nick,
            eventloop=loop,
        )
        self.coordinator = coordinator
        self.network_config = network_config
        self.target_channel = network_config.channel
        self._is_first_connect = True

    async def _register(self):
        """Ensure nickname list is initialized before registering."""
        if not getattr(self, "_attempt_nicknames", None):
            # pydle can leave this empty if a previous registration attempt failed early.
            self._attempt_nicknames = self._nicknames[:] or [self.network_config.nick]
            logger.debug(
                "Reinitialized IRC nickname attempts for %s to %s",
                self.network_config.server,
                self._attempt_nicknames,
            )
        await super()._register()

    async def on_connect(self):
        await super().on_connect()
        # Optionally identify with NickServ (or similar) if a password is configured
        password = getattr(self.network_config, "password", None)
        if password:
            try:
                await self.message("NickServ", f"IDENTIFY {password}")
            except Exception as e:  # pragma: no cover - operational logging
                logger.warning(
                    "Failed to identify with NickServ on %s:%s: %s",
                    self.network_config.server,
                    self.network_config.port,
                    e,
                )

        await self.join(self.target_channel)

        # Optional Idlerpg LOGIN (global, but only when we're on the #idlerpg channel)
        settings = getattr(self.coordinator, "settings", None)
        if settings and self.target_channel.lower() == "#idlerpg":
            idlerpg_user = getattr(settings, "idlerpg_username", None)
            idlerpg_pass = getattr(settings, "idlerpg_password", None)
            if idlerpg_user and idlerpg_pass:
                try:
                    await self.message("Idlerpg", f"LOGIN {idlerpg_user} {idlerpg_pass}")
                except Exception as e:  # pragma: no cover - operational logging
                    logger.warning(
                        "Failed to send Idlerpg LOGIN on %s:%s: %s",
                        self.network_config.server,
                        self.network_config.port,
                        e,
                    )
        # Only count as reconnect if not the first connection
        if not self._is_first_connect:
            self.coordinator.record_irc_reconnect()
        self._is_first_connect = False

    async def on_message(self, target, source, message):
        await super().on_message(target, source, message)
        if target.casefold() != self.target_channel.casefold():
            return
        if source == self.nickname:
            # Ignore echoes of our own messages.
            return
        # Pass network identifier so messages can be distinguished
        network_name = self.network_config.server
        await self.coordinator.handle_irc_message(source, message, network_name=network_name)

    async def on_quit(self, user, message=None):
        await super().on_quit(user, message)
        if user == self.nickname:
            return
        await self.coordinator.handle_irc_quit(user, message or "")

    async def on_disconnect(self, expected):
        # Don't call super().on_disconnect() because it tries to auto-reconnect,
        # which can cause issues when the connection writer is None.
        # The reconnection is handled by the _start_irc_client loop instead.
        logger.warning("Disconnected from IRC (expected=%s)", expected)
        # The parent's on_disconnect would try to reconnect automatically,
        # but we handle reconnection in the _start_irc_client loop to avoid
        # race conditions with the connection writer being None.

    async def on_raw(self, message):
        """Override to handle malformed IRC messages gracefully."""
        try:
            await super().on_raw(message)
        except ValueError as e:
            # Handle cases where IRC server sends malformed messages
            # (e.g., JOIN messages with unexpected format)
            error_str = str(e)
            if "too many values to unpack" in error_str or "not enough values to unpack" in error_str:
                logger.debug("Ignoring malformed IRC message: %s (error: %s)", message, e)
                return  # Don't re-raise, just ignore
            else:
                raise
        except Exception as e:
            # Log other unexpected errors but don't crash
            logger.warning("Error processing IRC message %s: %s", message, e)
            self.coordinator.record_error()
            # Don't re-raise to prevent task crashes
    
    async def on_raw_join(self, message):
        """Override to handle malformed JOIN messages specifically."""
        try:
            await super().on_raw_join(message)
        except (ValueError, TypeError) as e:
            # Handle malformed JOIN messages (e.g., wrong number of parameters)
            error_str = str(e)
            if "too many values to unpack" in error_str or "not enough values to unpack" in error_str or "unpack" in error_str.lower():
                logger.debug("Ignoring malformed JOIN message: %s (error: %s)", message, e)
                return  # Silently ignore malformed JOIN messages
            raise


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
        self.irc_clients: list[IRCRelayClient] = [IRCRelayClient(self, network) for network in settings.irc_networks]
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
        irc_connected = any(client.connected for client in self.irc_clients) if self.irc_clients else False
        irc_networks_status = [
            {
                "server": client.network_config.server,
                "port": client.network_config.port,
                "channel": client.network_config.channel,
                "connected": client.connected,
            }
            for client in self.irc_clients
        ]
        
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
            "irc_networks": irc_networks_status,
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
            # Check if channel ID is placeholder - if so, skip silently
            if self.settings.discord_channel_id == 123456789012345678:
                logger.debug("Discord channel ID not configured (using placeholder). IRC relay will be disabled.")
                return
            
            channel = self.discord_bot.get_channel(self.settings.discord_channel_id)
            if channel is None:
                try:
                    channel = await self.discord_bot.fetch_channel(self.settings.discord_channel_id)
                except discord.NotFound:
                    logger.warning(
                        "Discord channel ID %s not found. IRC relay disabled. "
                        "Set DISCORD_CHANNEL_ID in .env to enable IRC relay.",
                        self.settings.discord_channel_id
                    )
                    # Don't raise - allow bot to continue running, but IRC relay won't work
                    return
                except discord.Forbidden:
                    logger.warning(
                        "Bot does not have permission to access channel %s. IRC relay disabled. "
                        "Ensure the bot has 'View Channels' and 'Send Messages' permissions.",
                        self.settings.discord_channel_id
                    )
                    return
            if not isinstance(channel, discord.TextChannel):
                logger.warning(
                    "Configured channel ID %s is not a text channel. IRC relay disabled.",
                    self.settings.discord_channel_id
                )
                return
            self._discord_channel = channel
            guild = channel.guild
            guild_name = guild.name if guild else "Unknown"
            logger.info("Bridging Discord server '%s' (%s) channel #%s (%s)", guild_name, guild.id if guild else "N/A", channel.name, channel.id)
            try:
                await channel.send("🔗 IRC relay is online.")
            except discord.Forbidden:
                logger.warning("Bot cannot send messages to channel #%s. Check permissions.", channel.name)
        if not self._slash_synced:
            # Only sync if we have a valid channel
            if self._discord_channel is not None:
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
                    guild_name = guild.name if guild else "Unknown"
                    logger.info("Slash commands synced for guild '%s' (%s)", guild_name, guild.id if guild else "global")
                    self._slash_synced = True
            else:
                # No channel available, sync global commands as fallback
                try:
                    await self.discord_bot.tree.sync()
                    logger.info("Slash commands synced globally (no channel configured)")
                    self._slash_synced = True
                except discord.HTTPException:
                    logger.exception("Failed to sync application commands globally")

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

    async def handle_irc_message(self, author: str, content: str, network_name: Optional[str] = None) -> None:
        self.record_message()
        channel = await self._ensure_discord_channel()
        author_label = author.strip()
        allowed_mentions = discord.AllowedMentions.none()
        
        # If multiple IRC networks, include network identifier in username
        # Only show network if there are multiple networks configured
        has_multiple_networks = len(self.irc_clients) > 1
        if has_multiple_networks and network_name:
            # Format username to include network: "User [Network]"
            username = f"{author_label} [{network_name}]" if author_label else f"IRC [{network_name}]"
        else:
            username = author_label or "IRC"
        
        webhook = await self._ensure_discord_webhook(channel)
        if webhook is not None:
            await webhook.send(
                content,
                username=username,
                allowed_mentions=allowed_mentions,
            )
        else:
            formatted = f"**<{username}>** {content}"
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
                # Check if channel ID is placeholder - if so, raise a clear error
                if self.settings.discord_channel_id == 123456789012345678:
                    raise RuntimeError(
                        "Discord channel ID not configured. Set DISCORD_CHANNEL_ID in .env to enable IRC relay."
                    )
                
                channel = self.discord_bot.get_channel(self.settings.discord_channel_id)
                if channel is None:
                    try:
                        channel = await self.discord_bot.fetch_channel(self.settings.discord_channel_id)
                    except discord.NotFound:
                        raise RuntimeError(
                            f"Discord channel ID {self.settings.discord_channel_id} not found. "
                            "Set DISCORD_CHANNEL_ID in .env to enable IRC relay."
                        )
                    except discord.Forbidden:
                        raise RuntimeError(
                            f"Bot does not have permission to access channel {self.settings.discord_channel_id}. "
                            "Ensure the bot has 'View Channels' and 'Send Messages' permissions."
                        )
                if not isinstance(channel, discord.TextChannel):
                    raise RuntimeError(
                        f"Configured channel ID {self.settings.discord_channel_id} is not a text channel."
                    )
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
        """Send message to all connected IRC networks."""
        sent_to_any = False
        for client in self.irc_clients:
            if client.connected:
                try:
                    await client.message(client.target_channel, message)
                    sent_to_any = True
                except Exception as e:
                    logger.error("Failed to send message to IRC %s:%s: %s", client.network_config.server, client.network_config.port, e)
                    self.record_error()
        
        if not sent_to_any:
            logger.warning("Dropping message; no IRC clients connected: %s", message)
            self.record_error()

    async def stop_irc(self) -> bool:
        """Stop all IRC clients."""
        stopped_any = False
        for client in self.irc_clients:
            if client.connected:
                try:
                    await client.quit(message="IRC relay disconnected via command")
                    stopped_any = True
                except Exception:  # pragma: no cover - operational logging
                    logger.exception("Failed to disconnect from IRC %s:%s on command.", client.network_config.server, client.network_config.port)
        return stopped_any

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

    async def _recreate_irc_client(self, client_index: int) -> None:
        """Recreate a specific IRC client instance if needed."""
        if client_index >= len(self.irc_clients):
            return
        client = self.irc_clients[client_index]
        try:
            if client.connected:
                await client.disconnect(expected=False)
        except Exception:
            pass
        # Create a new client instance to avoid state issues
        network_config = self.settings.irc_networks[client_index]
        self.irc_clients[client_index] = IRCRelayClient(self, network_config)

    async def start_irc(self) -> None:
        """Start all IRC clients with proper error handling."""
        # Start each IRC client in its own task
        tasks = []
        for i, client in enumerate(self.irc_clients):
            task = asyncio.create_task(self._start_irc_client(i))
            tasks.append(task)
        
        # Wait for all tasks (they run forever until cancelled)
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _start_irc_client(self, client_index: int) -> None:
        """Start a single IRC client with proper error handling."""
        client = self.irc_clients[client_index]
        network_config = self.settings.irc_networks[client_index]
        
        try:
            while True:
                try:
                    if not client.connected:
                        await client.connect(
                            network_config.server,
                            network_config.port,
                            tls=network_config.tls,
                            password=getattr(network_config, "password", None),
                        )
                    await client.handle_forever()
                except asyncio.CancelledError:
                    logger.info("IRC client task %s:%s cancelled", network_config.server, network_config.port)
                    # Ensure client is disconnected before exiting
                    try:
                        if client.connected:
                            await client.disconnect(expected=True)
                    except Exception:
                        pass
                    raise  # Re-raise to properly propagate cancellation
                except (ConnectionResetError, OSError) as e:
                    logger.warning("IRC connection lost %s:%s (%s), reconnecting...", network_config.server, network_config.port, type(e).__name__)
                    await self._recreate_irc_client(client_index)
                    client = self.irc_clients[client_index]
                    await asyncio.sleep(5)
                    continue
                except RuntimeError as e:
                    error_str = str(e)
                    if "readuntil() called while another coroutine is already waiting" in error_str:
                        # This is a known pydle concurrency issue with multiple IRC clients - suppress it
                        logger.debug("IRC read conflict detected %s:%s, recreating client...", network_config.server, network_config.port)
                        await self._recreate_irc_client(client_index)
                        client = self.irc_clients[client_index]
                        await asyncio.sleep(2)
                        continue
                    else:
                        logger.warning("RuntimeError in IRC client %s:%s: %s", network_config.server, network_config.port, error_str)
                        await self._recreate_irc_client(client_index)
                        client = self.irc_clients[client_index]
                        await asyncio.sleep(5)
                        continue
                except Exception as e:
                    error_str = str(e)
                    # Also check for readuntil errors that might be caught as generic Exception
                    if "readuntil() called while another coroutine is already waiting" in error_str:
                        logger.debug("IRC read conflict (generic Exception) %s:%s, recreating client...", network_config.server, network_config.port)
                        await self._recreate_irc_client(client_index)
                        client = self.irc_clients[client_index]
                        await asyncio.sleep(2)
                        continue
                    logger.warning("Error in IRC client %s:%s: %s", network_config.server, network_config.port, error_str)
                    await self._recreate_irc_client(client_index)
                    client = self.irc_clients[client_index]
                    await asyncio.sleep(5)
                    continue
        except asyncio.CancelledError:
            # Ensure cleanup on cancellation
            try:
                if client.connected:
                    await client.disconnect(expected=True)
            except Exception:
                pass
            raise

    async def shutdown(self) -> None:
        """Shutdown all services cleanly."""
        # Close Discord bot first (this should close all aiohttp sessions)
        if not self.discord_bot.is_closed():
            try:
                # Close the bot and wait for it to complete
                await asyncio.wait_for(self.discord_bot.close(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Discord bot close timeout")
            except Exception as e:
                logger.warning("Error closing Discord bot: %s", e)
        
        # Close all IRC clients
        disconnect_tasks = []
        for client in self.irc_clients:
            if client.connected:
                try:
                    # Disconnect the client
                    task = asyncio.create_task(client.quit(message="Relay shutting down"))
                    disconnect_tasks.append(task)
                except Exception as e:
                    logger.warning("Error disconnecting IRC client %s:%s: %s", 
                                 client.network_config.server, client.network_config.port, e)
        
        # Wait for all IRC disconnections to complete (with timeout)
        if disconnect_tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*disconnect_tasks, return_exceptions=True), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("IRC disconnection timeout, forcing disconnect")
                # Force disconnect remaining clients
                for client in self.irc_clients:
                    if client.connected:
                        try:
                            await client.disconnect(expected=True)
                        except Exception:
                            pass
        
        # Ensure aiohttp sessions are closed (discord.py should handle this, but be explicit)
        try:
            if hasattr(self.discord_bot, 'http'):
                http_client = self.discord_bot.http
                # Try to get the session - discord.py uses different internal structures
                if hasattr(http_client, '_HTTPClient__session'):
                    session = http_client._HTTPClient__session
                    if session and not session.closed:
                        await session.close()
                # Also try to close connector if it exists
                if hasattr(http_client, '_HTTPClient__connector'):
                    connector = http_client._HTTPClient__connector
                    if connector and not connector.closed:
                        await connector.close()
        except Exception as e:
            logger.debug("Error closing aiohttp session: %s", e)


