from __future__ import annotations

import asyncio
from typing import Dict, Optional, TYPE_CHECKING

import discord
import feedparser
from discord import app_commands
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


class RSSCog(commands.Cog):
    """Live RSS updates pushed into Discord."""

    def __init__(self, coordinator: "RelayCoordinator"):
        self.coordinator = coordinator
        self._seen_entries: Dict[str, set[str]] = {}
        self.poll_feeds.start()

    def cog_unload(self) -> None:
        if self.poll_feeds.is_running():
            self.poll_feeds.cancel()

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

    async def _announce_entry(self, feed_title: str, entry) -> None:
        channel = await self._get_channel()
        if channel is None:
            return
        title = getattr(entry, "title", "New article")
        link = getattr(entry, "link", None)
        summary = getattr(entry, "summary", None)

        embed = discord.Embed(
            title=title,
            description=(summary[:200] + "…") if summary and len(summary) > 200 else summary,
            colour=discord.Colour.blue(),
        )
        embed.set_author(name=feed_title)
        if link:
            embed.url = link
        await channel.send(embed=embed)

    @tasks.loop(minutes=5)
    async def poll_feeds(self) -> None:
        feeds = await self.coordinator.config_store.list_rss_feeds()
        if not feeds:
            return

        for feed_url in feeds:
            parsed = await asyncio.to_thread(feedparser.parse, feed_url)
            if parsed.bozo:
                continue
            feed_title = parsed.feed.get("title", feed_url)
            seen = self._seen_entries.setdefault(feed_url, set())
            for entry in parsed.entries[:5]:
                entry_id = getattr(entry, "id", "") or getattr(entry, "link", "")
                if not entry_id or entry_id in seen:
                    continue
                seen.add(entry_id)
                await self._announce_entry(feed_title, entry)

    @poll_feeds.before_loop
    async def before_poll(self) -> None:
        await self.coordinator.discord_bot.wait_until_ready()
        interval = self.coordinator.settings.rss_poll_interval_seconds
        self.poll_feeds.change_interval(seconds=interval)

    @app_commands.command(name="rsslist", description="List configured RSS feeds.")
    async def rss_list(self, interaction: discord.Interaction) -> None:
        feeds = await self.coordinator.config_store.list_rss_feeds()
        if not feeds:
            await interaction.response.send_message("No RSS feeds configured.", ephemeral=True)
            return
        lines = "\n".join(f"- {url}" for url in feeds)
        await interaction.response.send_message(f"**Configured RSS Feeds**\n{lines}", ephemeral=True)

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        message = "Unable to display RSS information right now."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


