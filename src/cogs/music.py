# slash-first music cog
from __future__ import annotations

import asyncio
import functools
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "default_search": "ytsearch",
}

FFMPEG_OPTIONS = {
    "options": "-vn",
}


@dataclass
class Track:
    title: str
    url: str
    webpage_url: str
    requested_by: discord.Member
    duration: Optional[int]
    thumbnail: Optional[str]


class MusicCog(commands.Cog):
    """Music playback powered by yt-dlp and FFmpeg."""

    music = app_commands.Group(name="music", description="Music playback controls")

    def __init__(self, bot: commands.Bot, coordinator: RelayCoordinator):
        self.bot = bot
        self.coordinator = coordinator
        self._ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        self._queues: Dict[int, Deque[Track]] = {}
        self._now_playing: Dict[int, Track] = {}

    async def _assert_music_text_channel(self, interaction: discord.Interaction) -> bool:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Music commands are only available in text channels.",
                ephemeral=True,
            )
            return False
        allowed_id = self.coordinator.settings.music_text_channel_id
        if allowed_id and channel.id != allowed_id:
            await interaction.response.send_message(
                "Please use the configured music text channel for music commands.",
                ephemeral=True,
            )
            return False
        return True

    def _get_queue(self, guild: discord.Guild) -> Deque[Track]:
        return self._queues.setdefault(guild.id, deque())

    async def _extract_tracks(self, query: str, requester: discord.Member) -> list[Track]:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, functools.partial(self._ytdl.extract_info, query, download=False))
        entries = data.get("entries") if isinstance(data, dict) else None
        raw_items = entries if entries else [data]
        tracks: list[Track] = []
        for item in raw_items:
            if not item:
                continue
            tracks.append(
                Track(
                    title=item.get("title", "Unknown title"),
                    url=item.get("url"),
                    webpage_url=item.get("webpage_url") or item.get("original_url") or query,
                    requested_by=requester,
                    duration=item.get("duration"),
                    thumbnail=item.get("thumbnail"),
                )
            )
        return tracks

    def _format_duration(self, duration: Optional[int]) -> str:
        if duration is None:
            return "Live"
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    async def _send_now_playing(self, channel: discord.TextChannel, track: Track) -> None:
        embed = discord.Embed(title=track.title, url=track.webpage_url, colour=discord.Colour.blue())
        embed.add_field(name="Requested by", value=track.requested_by.mention)
        embed.add_field(name="Duration", value=self._format_duration(track.duration))
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        await channel.send(embed=embed)

    async def _ensure_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return None
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("You must be in a guild to use music commands.", ephemeral=True)
            return None
        if not member.voice or not member.voice.channel:
            await interaction.response.send_message("Join a voice channel before using music commands.", ephemeral=True)
            return None

        allowed_channel_id = self.coordinator.settings.music_voice_channel_id
        user_channel = member.voice.channel
        if allowed_channel_id and user_channel.id != allowed_channel_id:
            await interaction.response.send_message("Please join the configured music voice channel first.", ephemeral=True)
            return None

        voice = guild.voice_client
        if voice is None:
            voice = await user_channel.connect()
        elif voice.channel != user_channel:
            await voice.move_to(user_channel)
        return voice

    async def _start_playback(self, guild: discord.Guild, voice: discord.VoiceClient, text_channel: discord.abc.MessageableChannel) -> None:
        queue = self._get_queue(guild)
        if voice.is_playing() or not queue:
            return
        track = queue.popleft()
        self._now_playing[guild.id] = track

        def after_callback(error: Optional[BaseException]) -> None:
            if error:
                print(f"Playback error: {error}")
            asyncio.run_coroutine_threadsafe(self._play_next_in_queue(guild.id), self.bot.loop)

        source = discord.FFmpegPCMAudio(track.url, **FFMPEG_OPTIONS)
        voice.play(source, after=after_callback)
        if isinstance(text_channel, discord.TextChannel):
            await self._send_now_playing(text_channel, track)

    async def _play_next_in_queue(self, guild_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return
        voice = guild.voice_client
        if voice is None:
            return

        queue = self._queues.get(guild_id)
        if queue and voice.is_connected():
            track = queue.popleft()
            self._now_playing[guild_id] = track

            def after_callback(error: Optional[BaseException]) -> None:
                if error:
                    print(f"Playback error: {error}")
                asyncio.run_coroutine_threadsafe(self._play_next_in_queue(guild_id), self.bot.loop)

            source = discord.FFmpegPCMAudio(track.url, **FFMPEG_OPTIONS)
            voice.play(source, after=after_callback)
            text_channel = self._resolve_music_text_channel(guild)
            if text_channel:
                await self._send_now_playing(text_channel, track)
        else:
            self._now_playing.pop(guild_id, None)

    def _resolve_music_text_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        channel_id = self.coordinator.settings.music_text_channel_id
        if channel_id:
            channel = guild.get_channel(channel_id)
            if isinstance(channel, discord.TextChannel):
                return channel
        relay_channel = guild.get_channel(self.coordinator.settings.discord_channel_id)
        return relay_channel if isinstance(relay_channel, discord.TextChannel) else None

    @music.command(name="join", description="Summon the bot to your voice channel.")
    async def join(self, interaction: discord.Interaction) -> None:
        if not await self._assert_music_text_channel(interaction):
            return
        voice = await self._ensure_voice(interaction)
        if voice is None:
            return
        await interaction.response.send_message("🎶 Ready to play music!")

    @music.command(name="leave", description="Disconnect the bot from voice and clear the queue.")
    async def leave(self, interaction: discord.Interaction) -> None:
        if not await self._assert_music_text_channel(interaction):
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return
        voice = guild.voice_client
        if voice:
            await voice.disconnect()
        self._queues.pop(guild.id, None)
        self._now_playing.pop(guild.id, None)
        await interaction.response.send_message("👋 Disconnected from voice.")

    @music.command(name="play", description="Queue a track by URL or search terms.")
    @app_commands.describe(query="URL or search terms for the track or playlist.")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        if not await self._assert_music_text_channel(interaction):
            return
        voice = await self._ensure_voice(interaction)
        if voice is None:
            return

        await interaction.response.defer()
        assert interaction.guild is not None
        assert isinstance(interaction.user, discord.Member)
        tracks = await self._extract_tracks(query, interaction.user)
        if not tracks:
            await interaction.followup.send("No results found for that query.")
            return
        queue = self._get_queue(interaction.guild)
        queue.extend(tracks)
        if len(tracks) == 1:
            await interaction.followup.send(f"➕ Queued **{tracks[0].title}**.")
        else:
            await interaction.followup.send(f"➕ Queued {len(tracks)} tracks from playlist/search result.")
        await self._start_playback(interaction.guild, voice, interaction.channel)

    @music.command(name="skip", description="Skip the current track.")
    async def skip(self, interaction: discord.Interaction) -> None:
        if not await self._assert_music_text_channel(interaction):
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return
        voice = guild.voice_client
        if not voice or not voice.is_playing():
            await interaction.response.send_message("Nothing is currently playing.", ephemeral=True)
            return
        voice.stop()
        await interaction.response.send_message("⏭️ Skipped the current track.")

    @music.command(name="stop", description="Stop playback and clear the queue.")
    async def stop(self, interaction: discord.Interaction) -> None:
        if not await self._assert_music_text_channel(interaction):
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return
        voice = guild.voice_client
        if voice and voice.is_playing():
            voice.stop()
        self._queues.pop(guild.id, None)
        self._now_playing.pop(guild.id, None)
        await interaction.response.send_message("🛑 Stopped playback and cleared the queue.")

    @music.command(name="queue", description="Display the current music queue.")
    async def queue_command(self, interaction: discord.Interaction) -> None:
        if not await self._assert_music_text_channel(interaction):
            return
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command can only be used in a guild.", ephemeral=True)
            return

        queue = list(self._get_queue(guild))
        embed = discord.Embed(title="Music Queue", colour=discord.Colour.purple())
        now_playing = self._now_playing.get(guild.id)
        if now_playing:
            embed.add_field(
                name="Now Playing",
                value=f"[{now_playing.title}]({now_playing.webpage_url}) • {self._format_duration(now_playing.duration)}",
                inline=False,
            )
        if queue:
            lines = [
                f"{idx}. [{track.title}]({track.webpage_url}) • {self._format_duration(track.duration)}"
                for idx, track in enumerate(queue, start=1)
            ]
            embed.add_field(name="Up Next", value="\n".join(lines[:10]), inline=False)
            if len(lines) > 10:
                embed.set_footer(text=f"… and {len(lines) - 10} more")
        else:
            embed.add_field(name="Up Next", value="Queue is empty", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(f"Music command failed: {error}", ephemeral=True)
        else:
            await interaction.response.send_message(f"Music command failed: {error}", ephemeral=True)


