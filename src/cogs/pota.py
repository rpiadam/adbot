from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, Optional, TYPE_CHECKING

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


class POTACog(commands.Cog):
    """POTA (Parks on the Air) spots relay that checks for new activations every 30 seconds."""

    def __init__(self, coordinator: "RelayCoordinator"):
        self.coordinator = coordinator
        self._session: Optional[aiohttp.ClientSession] = None
        self._seen_spots: set[str] = set()
        self._weather_api_key: Optional[str] = getattr(coordinator.settings, "weather_api_key", None)
        self.poll_pota_spots.start()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def cog_unload(self) -> None:
        if self.poll_pota_spots.is_running():
            self.poll_pota_spots.cancel()
        if self._session is not None:
            asyncio.create_task(self._session.close())

    def _resolve_channel_id(self) -> Optional[int]:
        """Get the POTA channel ID from settings, or fall back to announcements channel."""
        settings = self.coordinator.settings
        # Check if there's a POTA-specific channel setting
        pota_channel_id = getattr(settings, "pota_channel_id", None)
        if pota_channel_id:
            return pota_channel_id
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

    async def _fetch_pota_spots(self) -> list[Dict]:
        """Fetch POTA spots from the API."""
        session = await self._get_session()
        # POTA API endpoint - returns recent spots
        # The API typically returns spots in reverse chronological order (newest first)
        api_url = "https://api.pota.app/spot/activator"
        
        try:
            async with session.get(api_url, headers={"User-Agent": "Discord-Bot/1.0"}) as response:
                if response.status == 200:
                    data = await response.json()
                    # Handle different response formats
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        # Some APIs return {"spots": [...]} or {"data": [...]}
                        spots = data.get("spots", data.get("data", data.get("activators", [])))
                        if isinstance(spots, list):
                            return spots
                    return []
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        except Exception:
            pass
        
        return []

    async def _fetch_weather(self, location_name: str, lat: Optional[float] = None, lon: Optional[float] = None) -> Optional[Dict]:
        """Fetch weather data for a location using OpenWeatherMap API."""
        if not self._weather_api_key:
            return None
        
        session = await self._get_session()
        try:
            # Try to use coordinates if available, otherwise use location name
            if lat and lon:
                url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={self._weather_api_key}&units=metric"
            else:
                # Use location name (park name or reference)
                url = f"https://api.openweathermap.org/data/2.5/weather?q={location_name}&appid={self._weather_api_key}&units=metric"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, Exception):
            pass
        
        return None

    def _format_weather_info(self, weather_data: Dict) -> str:
        """Format weather data into a readable string."""
        try:
            temp = weather_data.get("main", {}).get("temp", "N/A")
            feels_like = weather_data.get("main", {}).get("feels_like", "N/A")
            humidity = weather_data.get("main", {}).get("humidity", "N/A")
            description = weather_data.get("weather", [{}])[0].get("description", "N/A")
            wind_speed = weather_data.get("wind", {}).get("speed", "N/A")
            
            # Get weather emoji based on condition
            weather_icon = weather_data.get("weather", [{}])[0].get("icon", "")
            emoji = "🌤️"  # default
            if weather_icon:
                if "01" in weather_icon:  # clear sky
                    emoji = "☀️"
                elif "02" in weather_icon:  # few clouds
                    emoji = "⛅"
                elif "03" in weather_icon or "04" in weather_icon:  # clouds
                    emoji = "☁️"
                elif "09" in weather_icon or "10" in weather_icon:  # rain
                    emoji = "🌧️"
                elif "11" in weather_icon:  # thunderstorm
                    emoji = "⛈️"
                elif "13" in weather_icon:  # snow
                    emoji = "❄️"
                elif "50" in weather_icon:  # mist
                    emoji = "🌫️"
            
            return f"{emoji} {description.title()} | 🌡️ {temp}°C (feels like {feels_like}°C) | 💧 {humidity}% | 💨 {wind_speed} m/s"
        except Exception:
            return "Weather data unavailable"

    def _get_spot_id(self, spot: Dict) -> str:
        """Generate a unique ID for a spot to track if we've seen it."""
        # Use a combination of fields to create a unique ID
        activator = spot.get("activator", spot.get("actCallsign", ""))
        reference = spot.get("reference", spot.get("parkId", spot.get("park", "")))
        frequency = spot.get("frequency", spot.get("freq", ""))
        timestamp = spot.get("timestamp", spot.get("time", spot.get("spotTime", "")))
        mode = spot.get("mode", "")
        
        # Create unique ID from these fields
        return f"{activator}_{reference}_{frequency}_{mode}_{timestamp}"

    async def _format_spot_embed(self, spot: Dict) -> discord.Embed:
        """Format a POTA spot into a Discord embed matching the image format."""
        activator = spot.get("activator", spot.get("actCallsign", ""))
        frequency = spot.get("frequency", spot.get("freq", ""))
        mode = spot.get("mode", "")
        reference = spot.get("reference", spot.get("parkId", spot.get("park", "")))
        name = spot.get("name", spot.get("parkName", ""))
        spotter = spot.get("spotter", spot.get("spotterCallsign", ""))
        comment = spot.get("comment", spot.get("notes", ""))
        source = spot.get("source", "Web")
        timestamp = spot.get("timestamp", spot.get("time", spot.get("spotTime", "")))
        
        # Build description as plain text lines (matching the image format)
        description_lines = []
        
        if activator:
            description_lines.append(f"**Activator:** {activator}")
        if frequency:
            description_lines.append(f"**Frequency:** {frequency}")
        if mode:
            description_lines.append(f"**Mode:** {mode}")
        if reference:
            description_lines.append(f"**Reference:** {reference}")
        if name:
            description_lines.append(f"**Name:** {name}")
        if spotter:
            description_lines.append(f"**Spotter:** {spotter}")
        if comment:
            description_lines.append(f"**Comment:** {comment}")
        if source:
            description_lines.append(f"**Source:** {source}")
        if timestamp:
            description_lines.append(f"**Timestamp:** {timestamp}")
        
        # Add weather if available
        if self._weather_api_key:
            location = name or reference
            lat = spot.get("latitude", spot.get("lat"))
            lon = spot.get("longitude", spot.get("lon", spot.get("lng")))
            
            if location:
                weather_data = await self._fetch_weather(location, lat, lon)
                if weather_data:
                    weather_info = self._format_weather_info(weather_data)
                    description_lines.append(f"**Weather:** {weather_info}")
        
        embed = discord.Embed(
            title="POTA Spots",
            description="\n".join(description_lines) if description_lines else "No spot data available",
            colour=discord.Colour.green(),
        )
        
        # Add POTA logo/thumbnail
        embed.set_thumbnail(url="https://static.pota.app/pota-logo-38x38.png")
        
        return embed

    async def _announce_spots(self, spots: list[Dict]) -> None:
        """Announce new POTA spots to Discord in a single message."""
        channel = await self._get_channel()
        if channel is None:
            return
        
        # Send each spot as a separate embed in one message (Discord allows multiple embeds)
        embeds = []
        for spot in spots:
            embed = await self._format_spot_embed(spot)
            embeds.append(embed)
        
        try:
            # Send all embeds in one message (up to 10 embeds per message)
            for i in range(0, len(embeds), 10):
                batch = embeds[i:i+10]
                await channel.send(embeds=batch)
        except discord.HTTPException:
            pass  # Silently fail if we can't send

    @tasks.loop(seconds=60)
    async def poll_pota_spots(self) -> None:
        """Poll POTA API for new spots every 60 seconds."""
        try:
            spots = await self._fetch_pota_spots()
            if not spots:
                return
            
            new_spots = []
            for spot in spots:
                spot_id = self._get_spot_id(spot)
                if spot_id not in self._seen_spots:
                    self._seen_spots.add(spot_id)
                    new_spots.append(spot)
            
            # Send only 1 message with all new spots combined
            if new_spots:
                await self._announce_spots(new_spots)
            
            # Limit the size of seen_spots to prevent memory issues
            # Keep only the last 1000 spot IDs
            if len(self._seen_spots) > 1000:
                # Convert to list, keep last 1000
                spots_list = list(self._seen_spots)
                self._seen_spots = set(spots_list[-1000:])
                
        except Exception:
            # Silently handle errors to keep the task running
            pass

    @poll_pota_spots.before_loop
    async def before_poll(self) -> None:
        """Wait for bot to be ready before starting the poll loop."""
        await self.coordinator.discord_bot.wait_until_ready()

    @app_commands.command(name="potastatus", description="Show POTA spots relay status.")
    async def pota_status(self, interaction: discord.Interaction) -> None:
        channel = await self._get_channel()
        is_running = self.poll_pota_spots.is_running()
        seen_count = len(self._seen_spots)
        
        status_lines = [
            f"**POTA Spots Relay Status**",
            f"- Running: {'Yes' if is_running else 'No'}",
            f"- Channel: {channel.mention if channel else 'Not configured'}",
            f"- Spots tracked: {seen_count}",
            f"- Poll interval: 60 seconds",
        ]
        
        await interaction.response.send_message("\n".join(status_lines), ephemeral=True)

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        message = "Unable to process that POTA request."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

