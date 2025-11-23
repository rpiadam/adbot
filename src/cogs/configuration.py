from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class ConfigurationCog(commands.Cog):
    """Slash commands for managing dynamic monitor and RSS configuration."""

    monitor = app_commands.Group(name="monitor", description="Manage monitored website URLs")
    rss = app_commands.Group(name="rss", description="Manage RSS feeds")
    bluesky = app_commands.Group(name="bluesky", description="Manage Bluesky configuration")
    router = app_commands.Group(name="router", description="Manage router stats configuration")

    def __init__(self, coordinator: "RelayCoordinator"):
        self.coordinator = coordinator

    # ------------------------------------------------------------------
    # Monitor commands
    # ------------------------------------------------------------------
    @monitor.command(name="list", description="Show all monitored URLs.")
    async def monitor_list(self, interaction: discord.Interaction) -> None:
        targets = await self.coordinator.config_store.list_monitor_targets()
        if not targets:
            await interaction.response.send_message("No monitoring targets configured.", ephemeral=True)
            return
        lines = []
        for target in targets:
            extras = []
            if target.get("keyword"):
                extras.append(f"keyword='{target['keyword']}'")
            if target.get("expected_status"):
                extras.append(f"expect={target['expected_status']}")
            lines.append(f"- {target['url']} {' '.join(extras) if extras else ''}".rstrip())
        await interaction.response.send_message(f"**Monitoring Targets**\n" + "\n".join(lines), ephemeral=True)

    @monitor.command(name="add", description="Add a new URL to the monitoring list.")
    @app_commands.describe(
        url="URL to monitor for uptime",
        keyword="Optional substring that must exist in the response body",
        expected_status="Optional exact HTTP status that must be returned",
    )
    async def monitor_add(
        self,
        interaction: discord.Interaction,
        url: str,
        keyword: Optional[str] = None,
        expected_status: Optional[int] = None,
    ) -> None:
        if not _is_valid_url(url):
            await interaction.response.send_message("Please provide a valid http(s) URL.", ephemeral=True)
            return
        added = await self.coordinator.config_store.add_monitor_url(url)
        if not added:
            await interaction.response.send_message("That URL is already being monitored.", ephemeral=True)
            return
        try:
            await self.coordinator.config_store.update_monitor_metadata(
                url,
                keyword=keyword,
                expected_status=expected_status,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        await interaction.response.send_message(f"Added `{url}` to monitoring targets.", ephemeral=True)

    @monitor.command(name="remove", description="Remove a URL from the monitoring list.")
    @app_commands.describe(url="URL to stop monitoring")
    async def monitor_remove(self, interaction: discord.Interaction, url: str) -> None:
        removed = await self.coordinator.config_store.remove_monitor_url(url)
        if not removed:
            await interaction.response.send_message("That URL is not currently monitored.", ephemeral=True)
            return
        await interaction.response.send_message(f"Removed `{url}` from monitoring targets.", ephemeral=True)

    @monitor.command(name="configure", description="Update keyword/status expectations for a monitor.")
    @app_commands.describe(
        url="URL already being monitored",
        keyword="Substring that must be present (leave blank to keep unchanged)",
        expected_status="Exact HTTP status that must be returned",
        clear_keyword="Remove keyword requirement",
        clear_expected_status="Remove expected status requirement",
    )
    async def monitor_configure(
        self,
        interaction: discord.Interaction,
        url: str,
        keyword: Optional[str] = None,
        expected_status: Optional[int] = None,
        clear_keyword: bool = False,
        clear_expected_status: bool = False,
    ) -> None:
        try:
            metadata = await self.coordinator.config_store.update_monitor_metadata(
                url,
                keyword=keyword,
                clear_keyword=clear_keyword,
                expected_status=expected_status,
                clear_expected_status=clear_expected_status,
            )
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        if metadata is None:
            await interaction.response.send_message("That URL is not currently monitored.", ephemeral=True)
            return
        keyword_value = metadata.get("keyword", "not set")
        status_value = metadata.get("expected_status", "not set")
        await interaction.response.send_message(
            f"Updated `{url}` — keyword: {keyword_value}, expected_status: {status_value}",
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # RSS commands
    # ------------------------------------------------------------------
    @rss.command(name="list", description="Show all configured RSS feeds.")
    async def rss_list(self, interaction: discord.Interaction) -> None:
        feeds = await self.coordinator.config_store.list_rss_feeds()
        if not feeds:
            await interaction.response.send_message("No RSS feeds configured.", ephemeral=True)
            return
        lines = "\n".join(f"- {url}" for url in feeds)
        await interaction.response.send_message(f"**Configured RSS Feeds**\n{lines}", ephemeral=True)

    @rss.command(name="add", description="Add an RSS/Atom feed to monitor.")
    @app_commands.describe(url="Feed URL to add")
    async def rss_add(self, interaction: discord.Interaction, url: str) -> None:
        if not _is_valid_url(url):
            await interaction.response.send_message("Please provide a valid http(s) URL.", ephemeral=True)
            return
        added = await self.coordinator.config_store.add_rss_feed(url)
        if not added:
            await interaction.response.send_message("That feed is already configured.", ephemeral=True)
            return
        await interaction.response.send_message(f"Added `{url}` to RSS feeds.", ephemeral=True)

    @rss.command(name="remove", description="Remove an RSS/Atom feed.")
    @app_commands.describe(url="Feed URL to remove")
    async def rss_remove(self, interaction: discord.Interaction, url: str) -> None:
        removed = await self.coordinator.config_store.remove_rss_feed(url)
        if not removed:
            await interaction.response.send_message("That feed is not currently configured.", ephemeral=True)
            return
        await interaction.response.send_message(f"Removed `{url}` from RSS feeds.", ephemeral=True)

    # ------------------------------------------------------------------
    # Bluesky configuration commands
    # ------------------------------------------------------------------
    @bluesky.command(name="config", description="Show or update Bluesky configuration.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        handle="Bluesky handle (e.g., username.bsky.social or email)",
        app_password="Bluesky app password (get from https://bsky.app/settings/app-passwords)",
    )
    async def bluesky_config(
        self,
        interaction: discord.Interaction,
        handle: "Optional[str]" = None,
        app_password: "Optional[str]" = None,
    ) -> None:
        """Configure Bluesky credentials for posting router stats."""
        if handle is None and app_password is None:
            # Show current config
            config = await self.coordinator.config_store.get_bluesky_config()
            env_handle = self.coordinator.settings.bluesky_handle
            env_password = self.coordinator.settings.bluesky_app_password
            
            embed = discord.Embed(
                title="Bluesky Configuration",
                colour=discord.Colour.blurple(),
            )
            
            current_handle = config.get("handle") or env_handle or "Not set"
            current_password = "***" if (config.get("app_password") or env_password) else "Not set"
            
            embed.add_field(name="Handle", value=current_handle, inline=False)
            embed.add_field(name="App Password", value=current_password, inline=False)
            embed.add_field(
                name="Source",
                value="Config Store" if config.get("handle") else "Environment (.env)",
                inline=False
            )
            embed.set_footer(text="Config store values override .env values")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Update config
        updated = await self.coordinator.config_store.update_bluesky_config(
            handle=handle,
            app_password=app_password,
        )
        
        embed = discord.Embed(
            title="Bluesky Configuration Updated",
            colour=discord.Colour.green(),
        )
        if updated.get("handle"):
            embed.add_field(name="Handle", value=updated["handle"], inline=False)
        if updated.get("app_password"):
            embed.add_field(name="App Password", value="***", inline=False)
        
        await interaction.response.send_message(
            "✅ Bluesky configuration updated. Router stats posting will use these credentials.",
            embed=embed,
            ephemeral=True,
        )

    @bluesky.command(name="clear", description="Clear stored Bluesky configuration.")
    @app_commands.default_permissions(administrator=True)
    async def bluesky_clear(self, interaction: discord.Interaction) -> None:
        """Clear Bluesky configuration from config store (will use .env if present)."""
        await self.coordinator.config_store.clear_bluesky_config()
        await interaction.response.send_message(
            "✅ Bluesky configuration cleared. Will use .env values if present.",
            ephemeral=True,
        )

    # ------------------------------------------------------------------
    # Router stats configuration commands
    # ------------------------------------------------------------------
    @router.command(name="config", description="Show or update router stats configuration.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        interval_seconds="Interval in seconds between stat posts (default: 3600)",
    )
    async def router_config(
        self,
        interaction: discord.Interaction,
        interval_seconds: "Optional[int]" = None,
    ) -> None:
        """Configure router stats posting interval."""
        if interval_seconds is None:
            # Show current config
            config = await self.coordinator.config_store.get_router_config()
            env_interval = self.coordinator.settings.router_stats_interval_seconds
            
            embed = discord.Embed(
                title="Router Stats Configuration",
                colour=discord.Colour.blurple(),
            )
            
            current_interval = config.get("stats_interval_seconds") or str(env_interval)
            
            embed.add_field(name="Post Interval", value=f"{current_interval} seconds", inline=False)
            embed.add_field(
                name="Source",
                value="Config Store" if config.get("stats_interval_seconds") else "Environment (.env)",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Update config
        updated = await self.coordinator.config_store.update_router_config(
            stats_interval_seconds=interval_seconds,
        )
        
        embed = discord.Embed(
            title="Router Stats Configuration Updated",
            colour=discord.Colour.green(),
        )
        if updated.get("stats_interval_seconds"):
            embed.add_field(
                name="Post Interval",
                value=f"{updated['stats_interval_seconds']} seconds",
                inline=False
            )
        
        await interaction.response.send_message(
            "✅ Router stats configuration updated.",
            embed=embed,
            ephemeral=True,
        )

    @router.command(name="clear", description="Clear stored router configuration.")
    @app_commands.default_permissions(administrator=True)
    async def router_clear(self, interaction: discord.Interaction) -> None:
        """Clear router configuration from config store (will use .env if present)."""
        await self.coordinator.config_store.clear_router_config()
        await interaction.response.send_message(
            "✅ Router configuration cleared. Will use .env values if present.",
            ephemeral=True,
        )
