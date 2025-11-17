# slash-command moderation toolkit
from __future__ import annotations

import asyncio
import datetime
import time
from collections import deque
from typing import Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


class ModerationCog(commands.Cog):
    """Moderation toolkit with logging and lightweight automation."""

    PROFANITY_LIST = {
        "damn",
        "shit",
        "fuck",
        "bastard",
    }

    def __init__(self, coordinator: "RelayCoordinator"):
        self.coordinator = coordinator
        self._log_channels: dict[int, discord.TextChannel] = {}
        self._muted_role_id = coordinator.settings.moderation_muted_role_id
        self._active_mutes: dict[int, asyncio.Task] = {}
        self._temp_roles: dict[tuple[int, int, int], asyncio.Task] = {}
        # Track recent joins for rate limiting: {guild_id: deque of timestamps}
        self._recent_joins: dict[int, deque] = {}

    def _resolve_log_channel_id(self) -> Optional[int]:
        settings = self.coordinator.settings
        return (
            settings.moderation_log_channel_id
            or settings.announcements_channel_id
            or settings.discord_channel_id
        )

    async def _get_muted_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        if self._muted_role_id is None:
            return None
        role = guild.get_role(self._muted_role_id)
        if role is not None:
            return role
        try:
            role = await guild.fetch_role(self._muted_role_id)
        except discord.HTTPException:
            return None
        return role

    async def _get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        if guild.id in self._log_channels:
            return self._log_channels[guild.id]

        channel_id = self._resolve_log_channel_id()
        if channel_id is None:
            return None

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            try:
                channel = await guild.fetch_channel(channel_id)
            except discord.HTTPException:
                return None
        if isinstance(channel, discord.TextChannel):
            self._log_channels[guild.id] = channel
            return channel
        return None

    async def log_action(self, guild: discord.Guild, message: str) -> None:
        channel = await self._get_log_channel(guild)
        timestamp = discord.utils.utcnow()
        
        # Store log entry for dashboard
        log_entry = {
            "timestamp": timestamp.isoformat(),
            "guild_id": str(guild.id),
            "guild_name": guild.name,
            "message": message,
        }
        await self.coordinator.config_store.add_moderation_log(log_entry)
        
        # Send to Discord channel
        if channel is None:
            return
        embed = discord.Embed(description=message, colour=discord.Colour.orange())
        embed.timestamp = timestamp
        await channel.send(embed=embed)

    async def _schedule_role_removal(
        self,
        guild: discord.Guild,
        member: discord.Member,
        role: discord.Role,
        minutes: int,
    ) -> None:
        key = (guild.id, member.id, role.id)

        async def _remove_task() -> None:
            try:
                await asyncio.sleep(minutes * 60)
                if role in member.roles:
                    try:
                        await member.remove_roles(role, reason="Temporary role expired")
                    except discord.HTTPException:
                        return
                    await self.log_action(guild, f"Temporary role {role.mention} expired for {member.mention}.")
            finally:
                self._temp_roles.pop(key, None)

        if task := self._temp_roles.get(key):
            task.cancel()
        self._temp_roles[key] = asyncio.create_task(_remove_task())

    async def _schedule_unmute(self, guild: discord.Guild, member: discord.Member, seconds: int) -> None:
        async def _unmute_task() -> None:
            try:
                await asyncio.sleep(seconds)
                role = await self._get_muted_role(guild)
                if role and role in member.roles:
                    await member.remove_roles(role, reason="Timed mute expired")
                    await self.log_action(guild, f"Timed mute expired automatically for {member.mention}.")
            finally:
                self._active_mutes.pop(member.id, None)

        # Cancel existing schedule if any and replace
        if task := self._active_mutes.get(member.id):
            task.cancel()
        self._active_mutes[member.id] = asyncio.create_task(_unmute_task())

    @app_commands.command(name="purge", description="Delete a number of recent messages.")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(count="Number of recent messages to delete (max 100).")
    async def purge(self, interaction: discord.Interaction, count: app_commands.Range[int, 1, 100]) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("This command can only be used in text channels.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        deleted = await channel.purge(limit=count, reason=f"Requested by {interaction.user.display_name}")
        await interaction.followup.send(f"🧹 Removed {len(deleted)} messages.", ephemeral=True)
        await self.log_action(channel.guild, f"{interaction.user.mention} purged {len(deleted)} messages in {channel.mention}.")

    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.describe(member="Member to kick.", reason="Optional moderation reason.")
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        reason = reason or f"Actioned by {interaction.user.display_name}"
        await member.kick(reason=reason)
        await interaction.followup.send(f"👢 Kicked {member.mention}.", ephemeral=True)
        await self.log_action(interaction.guild, f"{interaction.user.mention} kicked {member.mention}. Reason: {reason}")

    @app_commands.command(name="ban", description="Ban a member from the server.")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(member="Member to ban.", reason="Optional moderation reason.")
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        reason = reason or f"Actioned by {interaction.user.display_name}"
        await member.ban(reason=reason, delete_message_seconds=86400)
        await interaction.followup.send(f"🔨 Banned {member.mention}.", ephemeral=True)
        await self.log_action(interaction.guild, f"{interaction.user.mention} banned {member.mention}. Reason: {reason}")

    @app_commands.command(name="timeout", description="Temporarily timeout a member.")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="Member to timeout.", minutes="Duration in minutes (1-4320).", reason="Optional moderation reason.")
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, 4320],
        reason: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
        await member.timeout(until, reason=reason or f"Actioned by {interaction.user.display_name}")
        await interaction.followup.send(f"⏳ Timed out {member.mention} for {minutes} minutes.", ephemeral=True)
        await self.log_action(
            interaction.guild,
            f"{interaction.user.mention} timed out {member.mention} for {minutes} minutes. Reason: {reason or 'n/a'}",
        )

    @app_commands.command(name="slowmode", description="Set slowmode for the current channel.")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(seconds="Slowmode delay in seconds (0 disables).")
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: app_commands.Range[int, 0, 21600],
    ) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Slowmode can only be set on text channels.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await channel.edit(slowmode_delay=seconds)
        if seconds:
            message = f"🐢 Slowmode enabled: {seconds} seconds."
            await self.log_action(channel.guild, f"{interaction.user.mention} set slowmode in {channel.mention} to {seconds}s.")
        else:
            message = "🚀 Slowmode disabled."
            await self.log_action(channel.guild, f"{interaction.user.mention} disabled slowmode in {channel.mention}.")
        await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(name="roleadd", description="Grant a role to the specified member.")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(member="Member to receive the role.", role="Role to grant.", reason="Optional reason for the assignment.")
    async def role_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        reason: Optional[str] = None,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return
        actor = interaction.user
        if not isinstance(actor, discord.Member):
            await interaction.response.send_message("This command requires guild context.", ephemeral=True)
            return
        guild_me = guild.me
        if guild_me is None or guild_me.top_role <= role:
            await interaction.response.send_message("I cannot grant that role due to hierarchy.", ephemeral=True)
            return
        if actor.top_role <= role and actor != guild.owner:
            await interaction.response.send_message("You cannot assign a role higher or equal to your top role.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await member.add_roles(role, reason=reason or f"Role added by {actor.display_name}")
        await self.log_action(guild, f"{actor.mention} granted {role.mention} to {member.mention}. Reason: {reason or 'n/a'}")
        await interaction.followup.send(f"✅ Granted {role.mention} to {member.mention}.", ephemeral=True)

    @app_commands.command(name="roleremove", description="Remove a role from the specified member.")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(member="Member to remove the role from.", role="Role to remove.", reason="Optional reason for the removal.")
    async def role_remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        reason: Optional[str] = None,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return
        actor = interaction.user
        if not isinstance(actor, discord.Member):
            await interaction.response.send_message("This command requires guild context.", ephemeral=True)
            return
        guild_me = guild.me
        if guild_me is None or guild_me.top_role <= role:
            await interaction.response.send_message("I cannot remove that role due to hierarchy.", ephemeral=True)
            return
        if actor.top_role <= role and actor != guild.owner:
            await interaction.response.send_message("You cannot remove a role higher or equal to your top role.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        if role not in member.roles:
            await interaction.followup.send("The member does not have that role.", ephemeral=True)
            return
        await member.remove_roles(role, reason=reason or f"Role removed by {actor.display_name}")
        await self.log_action(guild, f"{actor.mention} removed {role.mention} from {member.mention}. Reason: {reason or 'n/a'}")
        await interaction.followup.send(f"❎ Removed {role.mention} from {member.mention}.", ephemeral=True)

    @app_commands.command(name="temprole", description="Assign a role for a limited time.")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(
        member="Member to receive the temporary role.",
        role="Role to grant temporarily.",
        minutes="Duration in minutes (5-2880).",
        reason="Optional reason for the assignment.",
    )
    async def temp_role(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        minutes: app_commands.Range[int, 5, 2880],
        reason: Optional[str] = None,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return
        actor = interaction.user
        if not isinstance(actor, discord.Member):
            await interaction.response.send_message("This command requires guild context.", ephemeral=True)
            return

        guild_me = guild.me
        if guild_me is None or guild_me.top_role <= role:
            await interaction.response.send_message("I cannot grant that role due to hierarchy.", ephemeral=True)
            return
        if actor.top_role <= role and actor != guild.owner:
            await interaction.response.send_message("You cannot assign a role higher or equal to your top role.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await member.add_roles(role, reason=reason or f"Temporary role by {actor.display_name}")
        await self._schedule_role_removal(guild, member, role, minutes)
        await self.log_action(
            guild,
            f"{actor.mention} granted {role.mention} to {member.mention} for {minutes} minutes. Reason: {reason or 'n/a'}",
        )
        await interaction.followup.send(
            f"⏱️ Granted {role.mention} to {member.mention} for {minutes} minutes.",
            ephemeral=True,
        )

    @app_commands.command(name="mute", description="Place a member in the muted role for a duration.")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="Member to mute.", minutes="Duration in minutes (1-4320).", reason="Optional reason.")
    async def mute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, 4320],
        reason: Optional[str] = None,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return

        role = await self._get_muted_role(guild)
        if role is None:
            await interaction.response.send_message("Muted role is not configured.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await member.add_roles(role, reason=reason or f"Muted by {interaction.user.display_name}")
        await self._schedule_unmute(guild, member, minutes * 60)
        await self.log_action(guild, f"{interaction.user.mention} muted {member.mention} for {minutes} minutes. Reason: {reason or 'n/a'}")
        await interaction.followup.send(f"🔇 Muted {member.mention} for {minutes} minutes.", ephemeral=True)

    @app_commands.command(name="unmute", description="Remove the muted role from a member.")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="Member to unmute.", reason="Optional reason for logging.")
    async def unmute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return

        role = await self._get_muted_role(guild)
        if role is None:
            await interaction.response.send_message("Muted role is not configured.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        if role in member.roles:
            await member.remove_roles(role, reason=reason or f"Unmuted by {interaction.user.display_name}")
        if task := self._active_mutes.pop(member.id, None):
            task.cancel()
        await self.log_action(guild, f"{interaction.user.mention} unmuted {member.mention}. Reason: {reason or 'n/a'}")
        await interaction.followup.send(f"🔊 Unmuted {member.mention}.", ephemeral=True)

    @app_commands.command(name="warn", description="Send a warning to a member via DM and log the action.")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(member="Member to warn.", reason="Reason for the warning.")
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: Optional[str] = None,
    ) -> None:
        reason = reason or "Please follow the server guidelines."
        await interaction.response.defer(ephemeral=True)
        
        # Add warning to storage
        total_warnings = await self.coordinator.config_store.add_warning(
            interaction.guild.id,
            member.id,
            reason,
            interaction.user.id
        )
        
        dm_success = True
        try:
            await member.send(f"⚠️ You have received a warning ({total_warnings} total): {reason}")
        except discord.HTTPException:
            dm_success = False
        
        if dm_success:
            await interaction.followup.send(
                f"⚠️ Warned {member.mention} (Warning #{total_warnings}).",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"⚠️ Warned {member.mention} (Warning #{total_warnings}). User could not be DM'd, but the warning has been logged.",
                ephemeral=True,
            )
        await self.log_action(
            interaction.guild,
            f"{interaction.user.mention} warned {member.mention} (Warning #{total_warnings}). Reason: {reason}"
        )

    @app_commands.command(name="warnings", description="View warnings for a member.")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(member="Member to check warnings for.")
    async def view_warnings(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        warnings = await self.coordinator.config_store.get_warnings(interaction.guild.id, member.id)
        
        if not warnings:
            await interaction.response.send_message(
                f"{member.mention} has no warnings.",
                ephemeral=True,
            )
            return
        
        embed = discord.Embed(
            title=f"Warnings for {member.display_name}",
            description=f"Total: {len(warnings)} warning(s)",
            colour=discord.Colour.orange(),
        )
        
        for i, warning in enumerate(warnings, 1):
            timestamp = warning.get("timestamp", "Unknown")
            reason = warning.get("reason", "No reason provided")
            moderator_id = warning.get("moderator_id")
            
            try:
                moderator = await interaction.guild.fetch_member(int(moderator_id))
                moderator_name = moderator.display_name
            except:
                moderator_name = f"User {moderator_id}"
            
            embed.add_field(
                name=f"Warning #{i}",
                value=f"**Reason:** {reason}\n**Moderator:** {moderator_name}\n**Date:** {timestamp}",
                inline=False,
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member.")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(member="Member to clear warnings for.")
    async def clear_warnings(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ) -> None:
        cleared = await self.coordinator.config_store.clear_warnings(interaction.guild.id, member.id)
        
        if cleared:
            await interaction.response.send_message(
                f"✅ Cleared all warnings for {member.mention}.",
                ephemeral=True,
            )
            await self.log_action(
                interaction.guild,
                f"{interaction.user.mention} cleared all warnings for {member.mention}."
            )
        else:
            await interaction.response.send_message(
                f"{member.mention} has no warnings to clear.",
                ephemeral=True,
            )

    @app_commands.command(name="unban", description="Unban a user from the server.")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(user="User ID or username to unban.", reason="Optional reason for the unban.")
    async def unban(
        self,
        interaction: discord.Interaction,
        user: str,
        reason: Optional[str] = None,
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Try to parse as user ID first
        try:
            user_id = int(user)
            banned_user = await guild.fetch_ban(discord.Object(id=user_id))
            user_obj = banned_user.user
        except (ValueError, discord.NotFound):
            # Try to find by username
            bans = [entry async for entry in guild.bans()]
            user_obj = None
            for ban_entry in bans:
                if user.lower() in ban_entry.user.name.lower() or (ban_entry.user.discriminator and user in f"{ban_entry.user.name}#{ban_entry.user.discriminator}"):
                    user_obj = ban_entry.user
                    break

            if user_obj is None:
                await interaction.followup.send("User not found in ban list.", ephemeral=True)
                return
        except discord.HTTPException:
            await interaction.followup.send("Failed to fetch ban information.", ephemeral=True)
            return

        try:
            await guild.unban(user_obj, reason=reason or f"Unbanned by {interaction.user.display_name}")
            await interaction.followup.send(f"✅ Unbanned {user_obj.mention}.", ephemeral=True)
            await self.log_action(guild, f"{interaction.user.mention} unbanned {user_obj.mention}. Reason: {reason or 'n/a'}")
        except discord.HTTPException as e:
            await interaction.followup.send(f"Failed to unban user: {str(e)}", ephemeral=True)

    @app_commands.command(name="spamping", description="Spam ping a user a specified number of times.")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(member="Member to spam ping.", count="Number of times to ping (1-10000).")
    async def spam_ping(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        count: app_commands.Range[int, 1, 10000],
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("This command can only be used in text channels.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        # Send the pings with a small delay to avoid rate limits
        for i in range(count):
            try:
                await channel.send(f"{member.mention}")
                # Small delay between pings (0.5 seconds) to avoid rate limits
                if i < count - 1:  # Don't delay after the last ping
                    await asyncio.sleep(0.5)
            except discord.HTTPException as e:
                await interaction.followup.send(
                    f"Failed to send ping {i + 1}/{count}: {str(e)}",
                    ephemeral=True,
                )
                await self.log_action(
                    guild,
                    f"{interaction.user.mention} attempted to spam ping {member.mention} {count} times but encountered an error.",
                )
                return

        await interaction.followup.send(f"🔔 Spam pinged {member.mention} {count} times.", ephemeral=True)
        await self.log_action(
            guild,
            f"{interaction.user.mention} spam pinged {member.mention} {count} times in {channel.mention}.",
        )

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = "You do not have permission to use that command."
        elif isinstance(error, app_commands.BadArgument):
            message = "Invalid arguments. Please check your command usage."
        elif isinstance(error, app_commands.CommandInvokeError):
            message = f"Action failed: {error.original}"
        else:
            message = "An error occurred while running that command."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def _check_account_age(self, member: discord.Member) -> bool:
        """Check if account is too new. Returns True if account should be banned."""
        min_age_days = self.coordinator.settings.moderation_min_account_age_days
        if min_age_days is None:
            return False
        
        account_age = (discord.utils.utcnow() - member.created_at).days
        return account_age < min_age_days

    async def _check_rate_limit(self, guild: discord.Guild) -> bool:
        """Check if join rate limit is exceeded. Returns True if rate limit exceeded."""
        rate_limit_count = self.coordinator.settings.moderation_join_rate_limit_count
        rate_limit_seconds = self.coordinator.settings.moderation_join_rate_limit_seconds
        
        if rate_limit_count is None or rate_limit_seconds is None:
            return False
        
        guild_id = guild.id
        now = time.time()
        
        # Initialize deque for this guild if needed
        if guild_id not in self._recent_joins:
            self._recent_joins[guild_id] = deque()
        
        # Remove timestamps older than the rate limit window
        cutoff = now - rate_limit_seconds
        while self._recent_joins[guild_id] and self._recent_joins[guild_id][0] < cutoff:
            self._recent_joins[guild_id].popleft()
        
        # Add current join timestamp
        self._recent_joins[guild_id].append(now)
        
        # Check if we've exceeded the limit
        return len(self._recent_joins[guild_id]) > rate_limit_count

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        # Skip bots
        if member.bot:
            return
        
        guild = member.guild
        account_age_days = (discord.utils.utcnow() - member.created_at).days
        
        # Check account age
        if await self._check_account_age(member):
            try:
                reason = f"Account too new ({account_age_days} days old, minimum {self.coordinator.settings.moderation_min_account_age_days} days required)"
                await member.ban(reason=reason, delete_message_seconds=86400)
                await self.log_action(
                    guild,
                    f"🚫 Auto-banned {member.mention} (ID: {member.id}) - Account too new ({account_age_days} days old)."
                )
                return
            except discord.Forbidden:
                await self.log_action(
                    guild,
                    f"⚠️ Failed to auto-ban {member.mention} - insufficient permissions."
                )
            except discord.HTTPException as e:
                await self.log_action(
                    guild,
                    f"⚠️ Failed to auto-ban {member.mention} - {str(e)}"
                )
        
        # Check rate limit
        if await self._check_rate_limit(guild):
            try:
                reason = "Join rate limit exceeded (possible raid)"
                await member.ban(reason=reason, delete_message_seconds=86400)
                await self.log_action(
                    guild,
                    f"🚫 Auto-banned {member.mention} (ID: {member.id}) - Join rate limit exceeded (possible raid)."
                )
                return
            except discord.Forbidden:
                await self.log_action(
                    guild,
                    f"⚠️ Failed to auto-ban {member.mention} - insufficient permissions."
                )
            except discord.HTTPException as e:
                await self.log_action(
                    guild,
                    f"⚠️ Failed to auto-ban {member.mention} - {str(e)}"
                )
        
        # Log normal join
        await self.log_action(
            guild,
            f"✅ {member.mention} joined the server. Account created {discord.utils.format_dt(member.created_at, 'R')} ({account_age_days} days old)."
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await self.log_action(member.guild, f"⬅️ {member.mention} left the server.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        if message.author.guild_permissions.manage_messages:
            return
        content = message.content.lower()
        if any(bad_word in content for bad_word in self.PROFANITY_LIST):
            try:
                await message.delete()
            except discord.HTTPException:
                return
            await self.log_action(
                message.guild,
                f"🚫 Message from {message.author.mention} removed in {message.channel.mention} for profanity.",
            )
            try:
                await message.author.send("Please avoid using inappropriate language in the server.")
            except discord.HTTPException:
                pass


