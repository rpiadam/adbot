# slash-enabled features cog
from __future__ import annotations

import asyncio
from typing import Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


class FeaturesCog(commands.Cog):
    """General relay-related features and administrative helpers."""

    def __init__(self, bot: commands.Bot, coordinator: RelayCoordinator):
        self.bot = bot
        self.coordinator = coordinator

    async def _assert_relay_channel(self, interaction: discord.Interaction) -> bool:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Please run this command from a guild text channel.",
                ephemeral=True,
            )
            return False
        return True

    @app_commands.command(name="relaystatus", description="Show Discord ↔ IRC bridge status.")
    async def relay_status(self, interaction: discord.Interaction) -> None:
        if not await self._assert_relay_channel(interaction):
            return

        discord_channel: Optional[discord.TextChannel] = await self.coordinator._ensure_discord_channel()
        webhook_configured = bool(self.coordinator.settings.discord_webhook_url)
        guild = discord_channel.guild if discord_channel else None

        embed = discord.Embed(
            title="🔗 Relay Status",
            colour=discord.Colour.green(),
        )
        
        if guild:
            embed.add_field(
                name="Discord Server",
                value=f"{guild.name}\nID: {guild.id}",
                inline=True,
            )
        
        embed.add_field(
            name="Discord Channel",
            value=f"#{discord_channel.name}\nID: {discord_channel.id}",
            inline=True,
        )
        
        embed.add_field(
            name="Webhook",
            value="✅ Configured" if webhook_configured else "❌ Not configured",
            inline=True,
        )
        
        irc_status_parts = []
        for i, client in enumerate(self.coordinator.irc_clients, 1):
            status_icon = "✅" if client.connected else "❌"
            status_text = "connected" if client.connected else "disconnected"
            irc_status_parts.append(
                f"{status_icon} **{i}. {client.network_config.server}:{client.network_config.port}**\n"
                f"   → {client.network_config.channel} ({status_text})"
            )
        
        embed.add_field(
            name=f"IRC Networks ({len(self.coordinator.irc_clients)})",
            value="\n".join(irc_status_parts) if irc_status_parts else "No IRC networks configured",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Show information about the current Discord server.")
    async def server_info(self, interaction: discord.Interaction) -> None:
        """Show information about the current Discord server."""
        if not await self._assert_relay_channel(interaction):
            return
        
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command can only be used in a guild.",
                ephemeral=True,
            )
            return
        
        # Get bot member in this guild
        bot_member = guild.get_member(self.bot.user.id) if self.bot.user else None
        
        embed = discord.Embed(
            title=f"📊 {guild.name}",
            colour=discord.Colour.blurple(),
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(
            name="Server ID",
            value=str(guild.id),
            inline=True,
        )
        
        embed.add_field(
            name="Owner",
            value=guild.owner.mention if guild.owner else "Unknown",
            inline=True,
        )
        
        embed.add_field(
            name="Members",
            value=f"{guild.member_count or 'N/A'}",
            inline=True,
        )
        
        embed.add_field(
            name="Channels",
            value=f"Text: {len(guild.text_channels)}\nVoice: {len(guild.voice_channels)}\nCategories: {len(guild.categories)}",
            inline=True,
        )
        
        embed.add_field(
            name="Roles",
            value=str(len(guild.roles)),
            inline=True,
        )
        
        embed.add_field(
            name="Created",
            value=f"<t:{int(guild.created_at.timestamp())}:R>",
            inline=True,
        )
        
        if bot_member:
            embed.add_field(
                name="Bot Permissions",
                value=f"Administrator: {'✅' if guild.me.guild_permissions.administrator else '❌'}\n"
                      f"Manage Messages: {'✅' if guild.me.guild_permissions.manage_messages else '❌'}\n"
                      f"Send Messages: {'✅' if guild.me.guild_permissions.send_messages else '❌'}",
                inline=True,
            )
        
        # Check if this is the configured relay server
        relay_channel = await self.coordinator._ensure_discord_channel()
        if relay_channel and relay_channel.guild.id == guild.id:
            embed.add_field(
                name="Relay Status",
                value=f"✅ Active\nChannel: {relay_channel.mention}",
                inline=True,
            )
        
        embed.set_footer(text=f"Server ID: {guild.id}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="relayping", description="Measure the relay's Discord latency.")
    async def relay_ping(self, interaction: discord.Interaction) -> None:
        if not await self._assert_relay_channel(interaction):
            return

        before = discord.utils.utcnow()
        await interaction.response.defer(thinking=True)
        after = discord.utils.utcnow()
        round_trip = (after - before).total_seconds() * 1000
        await interaction.followup.send(f"Relay pong! {round_trip:.0f} ms")

    @app_commands.command(name="ping", description="Run a network ping from the relay host.")
    @app_commands.describe(target="Host or IP address to ping (e.g. 8.8.8.8)")
    async def ping_host(self, interaction: discord.Interaction, target: str) -> None:
        if not await self._assert_relay_channel(interaction):
            return

        if not target or len(target) > 255:
            await interaction.response.send_message(
                "Please provide a valid host or IP address.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            process = await asyncio.create_subprocess_exec(
                "ping",
                "-c",
                "4",
                "-W",
                "3",
                target,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15.0)
        except (asyncio.SubprocessError, OSError):
            await interaction.followup.send("Unable to execute ping command.")
            return
        except asyncio.TimeoutError:
            await interaction.followup.send("Ping command timed out.")
            return

        if process.returncode != 0:
            error_message = (
                stderr.decode("utf-8", errors="ignore").strip()
                or "Ping failed with a non-zero exit code."
            )
            await interaction.followup.send(error_message[:1800])
            return

        output = stdout.decode("utf-8", errors="ignore").strip()
        await interaction.followup.send(output[:1800])

    @app_commands.command(name="relayircstop", description="Disconnect the IRC relay connection.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def relay_irc_stop(self, interaction: discord.Interaction) -> None:
        if not await self._assert_relay_channel(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            disconnected = await self.coordinator.stop_irc()
        except Exception:
            await interaction.followup.send("Failed to disconnect from IRC. Check logs for details.")
            return

        if disconnected:
            await interaction.followup.send("IRC relay connection closed.")
        else:
            await interaction.followup.send("IRC relay was not connected.")

    @app_commands.command(name="relayshutdown", description="Shut down the relay bot gracefully.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def relay_shutdown(self, interaction: discord.Interaction) -> None:
        if not await self._assert_relay_channel(interaction):
            return

        await interaction.response.send_message("Shutting down relay…", ephemeral=True)
        await self.bot.close()

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if interaction.response.is_done():
            send = interaction.followup.send
        else:
            send = interaction.response.send_message

        if isinstance(error, app_commands.MissingPermissions):
            await send("You need the `Manage Server` permission to do that.", ephemeral=True)
        elif isinstance(error, app_commands.CheckFailure):
            await send("Unable to run that outside a guild text channel.", ephemeral=True)
        else:
            await send("Unable to process that request right now.", ephemeral=True)


