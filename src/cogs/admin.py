from __future__ import annotations

import platform
import textwrap
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


class AdminCog(commands.Cog):
    """Administrative utilities for server managers."""

    def __init__(self, bot: commands.Bot, coordinator: "RelayCoordinator"):
        self.bot = bot
        self.coordinator = coordinator

    def _resolve_announcement_channel_id(self) -> Optional[int]:
        settings = self.coordinator.settings
        return settings.announcements_channel_id or settings.discord_channel_id

    async def _get_text_channel(
        self,
        guild: discord.Guild,
        channel_id: Optional[int],
    ) -> Optional[discord.TextChannel]:
        if channel_id is None:
            return None
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        try:
            fetched = await guild.fetch_channel(channel_id)
        except discord.HTTPException:
            return None
        return fetched if isinstance(fetched, discord.TextChannel) else None

    @app_commands.command(name="relayannounce", description="Post an announcement to the configured channel.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(message="Announcement text to broadcast.")
    async def relay_announce(self, interaction: discord.Interaction, message: str) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return

        channel = await self._get_text_channel(guild, self._resolve_announcement_channel_id())
        if channel is None:
            await interaction.response.send_message("No announcements channel configured.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Server Announcement",
            description=message,
            colour=discord.Colour.blurple(),
        )
        embed.set_footer(text=f"Posted by {interaction.user.display_name}")
        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"Announcement posted in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="relayreload", description="Reload dynamic configuration and resync slash commands.")
    @app_commands.default_permissions(administrator=True)
    async def relay_reload(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.coordinator.reload_runtime()
        await interaction.followup.send("🔁 Configuration reloaded and commands refreshed.", ephemeral=True)

    @app_commands.command(name="relayrestart", description="Restart the relay process.")
    @app_commands.default_permissions(administrator=True)
    async def relay_restart(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "♻️ Restarting relay… the bot will disconnect briefly while it comes back online.",
            ephemeral=True,
        )
        await self.coordinator.request_restart()

    @app_commands.command(name="relaystats", description="Display runtime statistics for the bot.")
    @app_commands.default_permissions(administrator=True)
    async def relay_stats(self, interaction: discord.Interaction) -> None:
        bot = self.bot
        process_latency_ms = bot.latency * 1000 if bot.latency else 0.0
        embed = discord.Embed(title="Bot Status", colour=discord.Colour.green())
        embed.add_field(name="Guilds", value=str(len(bot.guilds)))
        embed.add_field(name="Users Visible", value=str(sum(g.member_count or 0 for g in bot.guilds)))
        embed.add_field(name="Latency", value=f"{process_latency_ms:.0f} ms")
        embed.add_field(name="Python", value=platform.python_version())
        embed.add_field(name="discord.py", value=discord.__version__)
        embed.add_field(name="Monitor Targets", value=str(len(self.coordinator.settings.monitor_urls)))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="relaydebug", description="Display configuration context for troubleshooting.")
    @app_commands.default_permissions(administrator=True)
    async def relay_debug(self, interaction: discord.Interaction) -> None:
        settings = self.coordinator.settings
        redacted_token = settings.discord_token[:6] + "…" if settings.discord_token else "n/a"
        summary = textwrap.dedent(
            f"""
            Discord Channel: {settings.discord_channel_id}
            Discord Token: {redacted_token}
            IRC: {settings.irc_nick}@{settings.irc_server}:{settings.irc_port} ({'TLS' if settings.irc_tls else 'PLAIN'})
            Monitor URLs: {', '.join(settings.monitor_urls) or 'none'}
            RSS Feeds: {', '.join(settings.rss_feeds) or 'none'}
            Webhook configured: {'yes' if settings.discord_webhook_url else 'no'}
            Announcements channel: {settings.announcements_channel_id or 'defaulting to relay channel'}
            """
        ).strip()
        await interaction.response.send_message(f"```ini\n{summary}\n```", ephemeral=True)

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "Administrator permission required."
        else:
            message = f"Operation failed: {error}"

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


