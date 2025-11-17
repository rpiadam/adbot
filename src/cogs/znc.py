"""ZNC configuration management commands."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ..relay import RelayCoordinator

logger = logging.getLogger(__name__)


class ZNCCog(commands.Cog):
    """Commands for managing ZNC bouncer configuration."""

    znc = app_commands.Group(name="znc", description="Manage ZNC bouncer configuration")

    def __init__(self, coordinator: "RelayCoordinator"):
        self.coordinator = coordinator

    async def _resolve_znc_config(self) -> dict[str, Optional[str]]:
        """Resolve ZNC configuration from storage or settings."""
        stored = await self.coordinator.config_store.get_znc_config()
        settings = self.coordinator.settings
        
        return {
            "base_url": stored.get("base_url") or settings.znc_base_url,
            "admin_username": stored.get("admin_username") or settings.znc_admin_username,
            "admin_password": stored.get("admin_password") or settings.znc_admin_password,
        }

    @znc.command(name="config", description="Configure ZNC server settings.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        base_url="ZNC webadmin base URL (e.g., https://znc.example.com)",
        admin_username="ZNC admin username",
        admin_password="ZNC admin password",
    )
    async def znc_config(
        self,
        interaction: discord.Interaction,
        base_url: Optional[str] = None,
        admin_username: Optional[str] = None,
        admin_password: Optional[str] = None,
    ) -> None:
        """Configure ZNC server settings."""
        if base_url is None and admin_username is None and admin_password is None:
            # Show current configuration
            config = await self._resolve_znc_config()
            embed = discord.Embed(
                title="ZNC Configuration",
                colour=discord.Colour.blurple(),
            )
            embed.add_field(
                name="Base URL",
                value=config.get("base_url") or "Not set",
                inline=False,
            )
            embed.add_field(
                name="Admin Username",
                value=config.get("admin_username") or "Not set",
                inline=True,
            )
            embed.add_field(
                name="Admin Password",
                value="***" if config.get("admin_password") else "Not set",
                inline=True,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Validate URL if provided
        if base_url:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                await interaction.response.send_message(
                    "❌ Invalid URL. Please provide a valid http(s) URL.",
                    ephemeral=True,
                )
                return

        updated = await self.coordinator.config_store.update_znc_config(
            base_url=base_url,
            admin_username=admin_username,
            admin_password=admin_password,
        )
        embed = discord.Embed(
            title="✅ ZNC Configuration Updated",
            colour=discord.Colour.green(),
        )
        embed.add_field(
            name="Base URL",
            value=updated.get("base_url") or "Not set",
            inline=False,
        )
        embed.add_field(
            name="Admin Username",
            value=updated.get("admin_username") or "Not set",
            inline=True,
        )
        embed.add_field(
            name="Admin Password",
            value="***" if updated.get("admin_password") else "Not set",
            inline=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

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

