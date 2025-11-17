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
        irc_connected = self.coordinator.irc_client.connected
        webhook_configured = bool(self.coordinator.settings.discord_webhook_url)

        parts = [
            "**Relay Status**",
            f"- Discord channel: #{discord_channel.name} ({discord_channel.id})",
            f"- IRC connected: {'yes' if irc_connected else 'no'}",
            f"- Webhook configured: {'yes' if webhook_configured else 'no'}",
        ]

        await interaction.response.send_message("\n".join(parts))

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


