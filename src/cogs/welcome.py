from __future__ import annotations

import contextlib
from typing import Optional, TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


class WelcomeCog(commands.Cog):
    """Welcomes new members and provides onboarding context."""

    def __init__(self, coordinator: RelayCoordinator):
        self.coordinator = coordinator

    def _resolve_channel_id(self) -> Optional[int]:
        settings = self.coordinator.settings
        return settings.welcome_channel_id or settings.announcements_channel_id or settings.discord_channel_id

    async def _resolve_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        channel_id = self._resolve_channel_id()
        if channel_id is None:
            return None

        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel

        try:
            fetched = await guild.fetch_channel(channel_id)
        except discord.HTTPException:
            return None
        if isinstance(fetched, discord.TextChannel):
            return fetched
        return None

    def _render_message(self, member: discord.Member) -> str:
        settings = self.coordinator.settings
        template = settings.welcome_message or "Welcome to {guild}, {mention}! Please read the rules and enjoy your stay."
        return template.format(
            mention=member.mention,
            name=member.name,
            display_name=member.display_name,
            guild=member.guild.name,
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        channel = await self._resolve_channel(member.guild)
        if channel is None:
            return

        message = self._render_message(member)
        await channel.send(message)

        with contextlib.suppress(discord.Forbidden, discord.HTTPException):
            await member.send(
                "👋 Thanks for joining! If you need any help, reach out to the moderation team."
            )


