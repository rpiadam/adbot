from __future__ import annotations

import asyncio
import re
from typing import Optional, TYPE_CHECKING
from urllib.parse import urljoin

import aiohttp
import discord
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


STARFREEBIES_URL = "https://starfreebies.co.uk/cadbury-secret-santa-2025-free-chocolate/"


class ChocolateCog(commands.Cog):
    """Monitors Cadbury Secret Santa links for free chocolate availability."""

    def __init__(self, coordinator: "RelayCoordinator"):
        self.coordinator = coordinator
        self._session: Optional[aiohttp.ClientSession] = None
        self._availability_cache: dict[str, bool] = {}
        self._cadbury_links: list[str] = []
        self._link_refresh_counter: int = 0
        self.monitor_chocolate.start()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=15)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            self._session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        return self._session

    def cog_unload(self) -> None:
        if self.monitor_chocolate.is_running():
            self.monitor_chocolate.cancel()
        if self._session is not None:
            asyncio.create_task(self._session.close())

    def _resolve_channel_id(self) -> Optional[int]:
        settings = self.coordinator.settings
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

    async def _fetch_cadbury_links(self) -> list[str]:
        """Fetch the 23 Cadbury links from the starfreebies page."""
        session = await self._get_session()
        try:
            async with session.get(STARFREEBIES_URL, allow_redirects=True) as response:
                if response.status != 200:
                    return []
                html_content = await response.text()
                
                # Extract links that look like Cadbury Secret Santa links
                # Look for URLs containing cadbury, secret-santa, or similar patterns
                link_pattern = r'https?://[^\s<>"\'\)]+(?:cadbury|secret[_-]?santa)[^\s<>"\'\)]*'
                links = re.findall(link_pattern, html_content, re.IGNORECASE)
                
                # Also look for links in href attributes (including relative URLs)
                href_pattern = r'href=["\']([^"\']*(?:cadbury|secret[_-]?santa)[^"\']*)["\']'
                href_links = re.findall(href_pattern, html_content, re.IGNORECASE)
                
                # Convert relative URLs to absolute
                base_url = str(response.url)
                absolute_links = []
                for link in href_links:
                    if link.startswith(('http://', 'https://')):
                        absolute_links.append(link)
                    elif link.startswith('/'):
                        # Absolute path on same domain
                        absolute_links.append(urljoin(base_url, link))
                    elif link.startswith(('cadbury', 'secret', 'www')):
                        # Might be a domain-relative link
                        absolute_links.append(f"https://{link}")
                
                # Combine and deduplicate
                all_links = list(set(links + absolute_links))
                
                # Filter to only valid HTTP(S) URLs, exclude starfreebies links, and limit to 23
                valid_links = [
                    link for link in all_links 
                    if link.startswith(('http://', 'https://'))
                    and "starfreebies.co.uk" not in link.lower()
                ][:23]
                
                return valid_links
        except Exception:
            return []

    def _check_availability(self, html_content: str, url: str = "") -> bool:
        """Check if the page indicates chocolate is available."""
        content_lower = html_content.lower()
        url_lower = url.lower()
        
        # Check if URL is the missed-out page
        if "/missed-out" in url_lower:
            return False
        
        # Common indicators that chocolate is NOT available
        unavailable_indicators = [
            "all claimed",
            "fully claimed",
            "no longer available",
            "sold out",
            "unavailable",
            "limit reached",
            "daily limit",
            "all gone",
            "out of stock",
            "all codes have been claimed",
            "sorry, all",
            "no longer accepting",
            "limit exceeded",
            "out of chocolate",  # Specific to the missed-out page
            "postal service is out of chocolate",  # Exact text from missed-out page
            "sorry! the cadbury secret santa",  # Start of missed-out page message
        ]
        
        # Check for unavailable indicators
        for indicator in unavailable_indicators:
            if indicator in content_lower:
                return False
        
        # Common indicators that chocolate IS available
        available_indicators = [
            "send a free",
            "claim your",
            "get your free",
            "free chocolate",
            "available now",
            "claim now",
            "send chocolate",
            "enter your details",
            "send to a friend",
            "claim your free",
        ]
        
        # Check for available indicators
        for indicator in available_indicators:
            if indicator in content_lower:
                return True
        
        # Check for form elements or buttons that suggest claiming is possible
        if "form" in content_lower or "submit" in content_lower or "button" in content_lower:
            # If there's a form/button and no unavailable indicators, likely available
            return True
        
        # If we can't determine, assume available if page loads successfully
        # (better to have false positives than miss opportunities)
        return True

    def _should_skip_url(self, url: str) -> bool:
        """Check if we should skip monitoring this URL."""
        url_lower = url.lower()
        # Skip starfreebies.co.uk links - these are just informational pages
        if "starfreebies.co.uk" in url_lower:
            return True
        return False

    async def _check_link(self, url: str) -> bool:
        """Check if chocolate is available at a given link."""
        # Skip starfreebies links
        if self._should_skip_url(url):
            return False
        
        session = await self._get_session()
        try:
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    return False
                # Check the final URL after redirects
                final_url = str(response.url)
                # Also check final URL after redirects
                if self._should_skip_url(final_url):
                    return False
                html_content = await response.text()
                return self._check_availability(html_content, final_url)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    async def _announce_availability(self, url: str) -> None:
        """Send Discord notification when chocolate becomes available."""
        channel = await self._get_channel()
        if channel is None:
            return
        
        # Get user ID from settings to ping
        user_id = getattr(self.coordinator.settings, 'chocolate_notify_user_id', None)
        mention = f"<@{user_id}>" if user_id else "@here"
        
        message = (
            f"🍫 **FREE CHOCOLATE AVAILABLE!** 🍫\n"
            f"{mention} A Cadbury Secret Santa link has free chocolate available!\n"
            f"🔗 {url}\n"
            f"⏰ Claim it quickly before it's gone!"
        )
        
        await channel.send(message)

    @tasks.loop(seconds=60)
    async def monitor_chocolate(self) -> None:
        """Monitor all 23 links for chocolate availability."""
        # Refresh links from starfreebies page every hour (every 60 checks)
        self._link_refresh_counter += 1
        if len(self._cadbury_links) == 0 or self._link_refresh_counter >= 60:
            self._cadbury_links = await self._fetch_cadbury_links()
            self._link_refresh_counter = 0
            # If we couldn't fetch links, use a fallback pattern
            if len(self._cadbury_links) == 0:
                # Fallback: try common Cadbury Secret Santa URL patterns
                self._cadbury_links = [
                    f"https://www.cadbury.co.uk/campaigns/secret-santa/{i}" 
                    for i in range(1, 24)
                ]
        
        if not self._cadbury_links:
            return
        
        for url in self._cadbury_links:
            try:
                is_available = await self._check_link(url)
                prev_available = self._availability_cache.get(url, False)
                self._availability_cache[url] = is_available
                
                # Only notify when it becomes available (not when it stays available)
                if not prev_available and is_available:
                    await self._announce_availability(url)
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(1)
            except Exception:
                # Log error but continue monitoring other links
                continue

    @monitor_chocolate.before_loop
    async def before_monitor(self) -> None:
        await self.coordinator.discord_bot.wait_until_ready()

