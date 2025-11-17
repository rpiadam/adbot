from __future__ import annotations

import asyncio
from typing import Optional, TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


class MonitoringCog(commands.Cog):
    """Website uptime monitoring with alerting into Discord."""

    def __init__(self, coordinator: "RelayCoordinator"):
        self.coordinator = coordinator
        self._session: Optional[aiohttp.ClientSession] = None
        self._status_cache: dict[str, bool] = {}
        self.monitor_websites.start()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def cog_unload(self) -> None:
        if self.monitor_websites.is_running():
            self.monitor_websites.cancel()
        if self._session is not None:
            asyncio.create_task(self._session.close())

    def _resolve_channel_id(self) -> Optional[int]:
        settings = self.coordinator.settings
        return settings.announcements_channel_id or settings.discord_channel_id

    async def _get_channel(self) -> Optional[discord.TextChannel]:
        bot = self.coordinator.discord_bot
        channel_id = self._resolve_channel_id()
        if channel_id is None or not bot.guilds:
            return None
        for guild in bot.guilds:
            channel = guild.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                return channel
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException:
            return None
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _announce(self, message: str) -> None:
        channel = await self._get_channel()
        if channel:
            await channel.send(message)

    @tasks.loop(seconds=60)
    async def monitor_websites(self) -> None:
        urls = await self.coordinator.config_store.list_monitor_urls()
        if not urls:
            return
        session = await self._get_session()
        for url in urls:
            try:
                async with session.get(url, allow_redirects=True) as response:
                    is_up = 200 <= response.status < 400
            except aiohttp.ClientError:
                is_up = False
            prev = self._status_cache.get(url)
            self._status_cache[url] = is_up
            if prev is None:
                continue
            if prev and not is_up:
                await self._announce(f"🔻 {url} appears to be **down**.")
            elif not prev and is_up:
                await self._announce(f"✅ {url} has recovered and is back online.")

    @monitor_websites.before_loop
    async def before_monitor(self) -> None:
        await self.coordinator.discord_bot.wait_until_ready()
        interval = self.coordinator.settings.monitor_interval_seconds
        self.monitor_websites.change_interval(seconds=interval)

    @app_commands.command(name="monitorlist", description="List the URLs currently being monitored.")
    async def monitor_list(self, interaction: discord.Interaction) -> None:
        urls = await self.coordinator.config_store.list_monitor_urls()
        if not urls:
            await interaction.response.send_message("No monitoring targets configured.", ephemeral=True)
            return
        lines = "\n".join(f"- {url}" for url in urls)
        await interaction.response.send_message(f"**Monitoring Targets**\n{lines}", ephemeral=True)

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        message = "Unable to process that monitoring request."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


