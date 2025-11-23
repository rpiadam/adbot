from __future__ import annotations

import asyncio
import platform
import subprocess
import tempfile
import textwrap
from pathlib import Path
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
        coordinator = self.coordinator
        health = coordinator.get_health_stats()
        process_latency_ms = bot.latency * 1000 if bot.latency else 0.0
        
        embed = discord.Embed(title="Bot Status", colour=discord.Colour.green() if health["health_status"] == "healthy" else discord.Colour.orange())
        embed.add_field(name="Guilds", value=str(len(bot.guilds)), inline=True)
        embed.add_field(name="Users Visible", value=str(sum(g.member_count or 0 for g in bot.guilds)), inline=True)
        embed.add_field(name="Latency", value=f"{process_latency_ms:.0f} ms", inline=True)
        embed.add_field(name="Uptime", value=health["uptime_formatted"], inline=True)
        embed.add_field(name="Messages Relayed", value=str(health["message_count"]), inline=True)
        embed.add_field(name="Message Rate", value=f"{health['message_rate_per_hour']:.1f}/hour", inline=True)
        embed.add_field(name="Discord Status", value="✅ Connected" if health["discord_connected"] else "❌ Disconnected", inline=True)
        embed.add_field(name="IRC Status", value="✅ Connected" if health["irc_connected"] else "❌ Disconnected", inline=True)
        embed.add_field(name="IRC Networks", value=str(len(health["irc_networks"])), inline=True)
        embed.add_field(name="Errors", value=str(health["error_count"]), inline=True)
        embed.add_field(name="Discord Reconnects", value=str(health["discord_reconnect_count"]), inline=True)
        embed.add_field(name="IRC Reconnects", value=str(health["irc_reconnect_count"]), inline=True)
        embed.add_field(name="Python", value=platform.python_version(), inline=True)
        embed.add_field(name="discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="Monitor Targets", value=str(len(coordinator.settings.monitor_urls)), inline=True)
        embed.add_field(name="RSS Feeds", value=str(len(coordinator.settings.rss_feeds)), inline=True)
        embed.set_footer(text=f"Health: {health['health_status'].upper()}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="relaydebug", description="Display configuration context for troubleshooting.")
    @app_commands.default_permissions(administrator=True)
    async def relay_debug(self, interaction: discord.Interaction) -> None:
        settings = self.coordinator.settings
        redacted_token = settings.discord_token[:6] + "…" if settings.discord_token else "n/a"
        
        # Format IRC networks
        irc_info = []
        for i, network in enumerate(settings.irc_networks, 1):
            irc_info.append(f"{i}. {network.nick}@{network.server}:{network.port} → {network.channel} ({'TLS' if network.tls else 'PLAIN'})")
        irc_str = "\n            ".join(irc_info) if irc_info else "none"
        
        summary = textwrap.dedent(
            f"""
            Discord Channel: {settings.discord_channel_id}
            Discord Token: {redacted_token}
            IRC Networks:
            {irc_str}
            Monitor URLs: {', '.join(settings.monitor_urls) or 'none'}
            RSS Feeds: {', '.join(settings.rss_feeds) or 'none'}
            Webhook configured: {'yes' if settings.discord_webhook_url else 'no'}
            Announcements channel: {settings.announcements_channel_id or 'defaulting to relay channel'}
            """
        ).strip()
        await interaction.response.send_message(f"```ini\n{summary}\n```", ephemeral=True)

    @app_commands.command(name="downloadbot", description="Download the bot code as a zip file (Python or Ruby version).")
    @app_commands.describe(version="Which version to download: python or ruby")
    async def download_bot(self, interaction: discord.Interaction, version: str = "python") -> None:
        """Download the bot code as a zip file."""
        version_lower = version.lower()
        if version_lower not in ("python", "ruby"):
            await interaction.response.send_message(
                "❌ Invalid version. Please choose 'python' or 'ruby'.",
                ephemeral=True,
            )
            return
        
        await interaction.response.defer(thinking=True, ephemeral=True)
        await interaction.followup.send(f"⏳ Creating {version_lower.capitalize()} bot zip file...", ephemeral=True)
        
        try:
            # Import the zip creation function directly
            import sys
            import importlib.util
            root_path = Path(__file__).parent.parent.parent
            scripts_path = root_path / "scripts"
            script_file = scripts_path / "create_bot_zip.py"
            
            # Try to import the module dynamically
            create_bot_zip = None
            if script_file.exists():
                try:
                    spec = importlib.util.spec_from_file_location("create_bot_zip", script_file)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        create_bot_zip = module.create_bot_zip
                except Exception:
                    pass
            
            if create_bot_zip is None:
                # Fallback: use subprocess
                script_path = scripts_path / "create_bot_zip.py"
                temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=f"-uplove-{version}.zip")
                temp_zip.close()
                
                result = await asyncio.to_thread(
                    subprocess.run,
                    [
                        "python3",
                        str(script_path),
                        version.lower(),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(root_path),
                )
                
                if result.returncode != 0:
                    raise RuntimeError(f"Script failed: {result.stderr}")
                
                # Find the created zip file from output
                import re
                match = re.search(r"Created zip file: (.+)", result.stdout)
                if match:
                    zip_path = Path(match.group(1).strip())
                else:
                    zip_path = Path(temp_zip.name)
                    if not zip_path.exists():
                        raise RuntimeError("Could not find created zip file")
            else:
                # Create zip directly using the function
                temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=f"-uplove-{version}.zip")
                temp_zip.close()
                zip_path = await asyncio.to_thread(create_bot_zip, version.lower(), temp_zip.name)
            
            if not zip_path.exists():
                raise FileNotFoundError(f"Zip file not found: {zip_path}")
            
            # Check file size (Discord has a 25MB limit for files)
            file_size = zip_path.stat().st_size
            if file_size > 25 * 1024 * 1024:
                zip_path.unlink()
                await interaction.followup.send(
                    f"❌ Zip file is too large ({file_size / 1024 / 1024:.2f} MB). "
                    "Discord has a 25MB file size limit.",
                    ephemeral=True,
                )
                return
            
            # Send the file
            file = discord.File(str(zip_path), filename=f"uplove-bot-{version_lower}.zip")
            embed = discord.Embed(
                title=f"📦 UpLove Bot - {version_lower.capitalize()} Version",
                description=f"Here's the complete bot code!\n\n**File size:** {file_size / 1024 / 1024:.2f} MB",
                colour=discord.Colour.green(),
            )
            embed.add_field(
                name="📋 Next Steps",
                value="1. Extract the zip file\n2. Copy `example.env` to `.env`\n3. Configure your settings\n4. Install dependencies\n5. Run the bot!",
                inline=False,
            )
            embed.add_field(
                name="📚 Documentation",
                value="See README.md in the zip for full setup instructions.",
                inline=False,
            )
            embed.set_footer(text="The zip file will be automatically cleaned up after 60 seconds.")
            # Delete the "creating" message and send the file
            await interaction.delete_original_response()
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
            # Clean up after a delay
            async def cleanup():
                await asyncio.sleep(60)  # Wait 60 seconds before cleanup
                try:
                    if zip_path.exists():
                        zip_path.unlink()
                except Exception:
                    pass  # Ignore cleanup errors
            
            asyncio.create_task(cleanup())
            
        except subprocess.TimeoutError:
            await interaction.edit_original_response(
                content="❌ Zip creation timed out. Please try again later.",
            )
        except FileNotFoundError as e:
            await interaction.edit_original_response(
                content=f"❌ Required files not found: {str(e)}\nPlease ensure the bot files are present.",
            )
        except Exception as e:
            error_details = str(e)
            await interaction.edit_original_response(
                content=f"❌ Failed to create zip file: {error_details}\n\nIf this persists, please contact an administrator.",
            )

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


