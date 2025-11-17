from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

from atproto import Client
from discord.ext import commands, tasks
from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
)

if TYPE_CHECKING:
    from ..relay import RelayCoordinator

logger = logging.getLogger(__name__)


class RouterStatsCog(commands.Cog):
    """Collect router statistics via SNMP and post to Bluesky."""

    def __init__(self, coordinator: "RelayCoordinator"):
        self.coordinator = coordinator
        self.bluesky_client: Optional[Client] = None
        self._last_post_time: Optional[datetime] = None
        # Don't start immediately - check config when bot is ready

    async def _get_bluesky_config(self) -> tuple[Optional[str], Optional[str]]:
        """Get Bluesky credentials from config store or environment."""
        config = await self.coordinator.config_store.get_bluesky_config()
        handle = config.get("handle") or self.coordinator.settings.bluesky_handle
        password = config.get("app_password") or self.coordinator.settings.bluesky_app_password
        return handle, password

    async def _get_router_config(self) -> tuple[Optional[str], Optional[str], int]:
        """Get router SNMP config from config store or environment."""
        config = await self.coordinator.config_store.get_router_config()
        host = config.get("snmp_host") or self.coordinator.settings.router_snmp_host
        community = config.get("snmp_community") or self.coordinator.settings.router_snmp_community
        interval_str = config.get("stats_interval_seconds") or str(self.coordinator.settings.router_stats_interval_seconds)
        interval = int(interval_str) if interval_str else 3600
        return host, community, interval

    async def _should_start(self) -> bool:
        """Check if all required configuration is present."""
        handle, password = await self._get_bluesky_config()
        host, community, _ = await self._get_router_config()
        return bool(handle and password and host and community)

    async def _init_bluesky(self) -> bool:
        """Initialize Bluesky client if not already done."""
        if self.bluesky_client is not None:
            return True

        handle, password = await self._get_bluesky_config()
        if not handle or not password:
            return False

        try:
            # Create client and login in thread (atproto Client.login is blocking)
            def _login():
                client = Client()
                client.login(
                    login=handle,
                    password=password,
                )
                return client

            self.bluesky_client = await asyncio.to_thread(_login)
            logger.info("Successfully authenticated with Bluesky")
            return True
        except Exception as e:
            logger.error("Failed to authenticate with Bluesky: %s", e)
            self.bluesky_client = None
            return False

    async def _get_snmp_value(self, oid: str) -> Optional[int]:
        """Get a single SNMP value from the router."""
        host, community, _ = await self._get_router_config()
        if not host or not community:
            return None

        def _snmp_get():
            try:
                iterator = getCmd(
                    SnmpEngine(),
                    CommunityData(community),
                    UdpTransportTarget((host, 161)),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid)),
                )
                errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
                if errorIndication:
                    logger.warning("SNMP error: %s", errorIndication)
                    return None
                if errorStatus:
                    logger.warning(
                        "SNMP error: %s at %s",
                        errorStatus.prettyPrint(),
                        errorIndex and varBinds[int(errorIndex) - 1][0] or "?",
                    )
                    return None
                for varBind in varBinds:
                    return int(varBind[1])
                return None
            except Exception as e:
                logger.warning("SNMP exception: %s", e)
                return None

        return await asyncio.to_thread(_snmp_get)

    def _format_bytes(self, bytes_value: int) -> str:
        """Format bytes into human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_value < 1024.0:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.2f} PB"

    def _format_uptime(self, seconds: int) -> str:
        """Format uptime in seconds to human-readable format."""
        td = timedelta(seconds=seconds)
        days = td.days
        hours, remainder = divmod(td.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        return " ".join(parts) if parts else "0m"

    async def _collect_router_stats(self) -> Optional[dict]:
        """Collect router statistics via SNMP."""
        # Common SNMP OIDs:
        # sysUpTime: 1.3.6.1.2.1.1.3.0 (System uptime in centiseconds)
        # ifInOctets (WAN interface): 1.3.6.1.2.1.2.2.1.10.1 (Input octets on interface 1)
        # ifOutOctets (WAN interface): 1.3.6.1.2.1.2.2.1.16.1 (Output octets on interface 1)
        # ipInReceives: 1.3.6.1.2.1.4.3.0 (IP packets received)
        # ipOutRequests: 1.3.6.1.2.1.4.10.0 (IP packets sent)

        stats = {}

        # Get uptime (in centiseconds, convert to seconds)
        uptime_centiseconds = await self._get_snmp_value("1.3.6.1.2.1.1.3.0")
        if uptime_centiseconds is not None:
            stats["uptime_seconds"] = uptime_centiseconds // 100

        # Try to get WAN interface stats (interface 1 is typically WAN)
        # Note: Interface numbers vary by router, may need to adjust
        if_in_octets = await self._get_snmp_value("1.3.6.1.2.1.2.2.1.10.1")
        if if_in_octets is not None:
            stats["bytes_in"] = if_in_octets

        if_out_octets = await self._get_snmp_value("1.3.6.1.2.1.2.2.1.16.1")
        if if_out_octets is not None:
            stats["bytes_out"] = if_out_octets

        # Get IP packet stats
        ip_in = await self._get_snmp_value("1.3.6.1.2.1.4.3.0")
        if ip_in is not None:
            stats["packets_in"] = ip_in

        ip_out = await self._get_snmp_value("1.3.6.1.2.1.4.10.0")
        if ip_out is not None:
            stats["packets_out"] = ip_out

        return stats if stats else None

    def _format_stats_post(self, stats: dict) -> str:
        """Format router stats into a Bluesky post."""
        lines = ["🔌 Router Stats"]
        lines.append("")

        if "uptime_seconds" in stats:
            uptime_str = self._format_uptime(stats["uptime_seconds"])
            lines.append(f"⏱️ Uptime: {uptime_str}")

        if "bytes_in" in stats and "bytes_out" in stats:
            total_bytes = stats["bytes_in"] + stats["bytes_out"]
            lines.append(f"📊 Total Traffic: {self._format_bytes(total_bytes)}")
            lines.append(
                f"   📥 In: {self._format_bytes(stats['bytes_in'])} | "
                f"📤 Out: {self._format_bytes(stats['bytes_out'])}"
            )

        if "packets_in" in stats and "packets_out" in stats:
            total_packets = stats["packets_in"] + stats["packets_out"]
            lines.append(
                f"📦 Total Packets: {total_packets:,} "
                f"({stats['packets_in']:,} in / {stats['packets_out']:,} out)"
            )

        lines.append("")
        lines.append(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)

    async def _post_to_bluesky(self, text: str) -> bool:
        """Post text to Bluesky."""
        if not await self._init_bluesky():
            return False

        try:
            # atproto Client.send_post is blocking, run in thread
            def _send_post():
                self.bluesky_client.send_post(text=text)

            await asyncio.to_thread(_send_post)
            logger.info("Posted router stats to Bluesky")
            self._last_post_time = datetime.now()
            return True
        except Exception as e:
            logger.error("Failed to post to Bluesky: %s", e)
            # Try to re-authenticate on next attempt
            self.bluesky_client = None
            return False

    @tasks.loop(seconds=3600)
    async def post_router_stats(self) -> None:
        """Periodically collect and post router stats to Bluesky."""
        # Check if config is still available
        if not await self._should_start():
            logger.warning("Router stats posting disabled: missing configuration")
            self.post_router_stats.stop()
            return

        stats = await self._collect_router_stats()
        if not stats:
            logger.warning("Failed to collect router stats")
            return

        post_text = self._format_stats_post(stats)
        await self._post_to_bluesky(post_text)

    @post_router_stats.before_loop
    async def before_post_stats(self) -> None:
        """Wait for bot to be ready before starting stats posting."""
        await self.coordinator.discord_bot.wait_until_ready()
        
        # Check if we should start
        if await self._should_start():
            _, _, interval = await self._get_router_config()
            self.post_router_stats.change_interval(seconds=interval)
            logger.info("Router stats posting started")
        else:
            logger.info("Router stats posting disabled: missing Bluesky or SNMP configuration")
            self.post_router_stats.stop()

    async def cog_load(self) -> None:
        """Start router stats posting when cog loads if config is available."""
        # Give it a moment for bot to be ready
        if self.coordinator.discord_bot.is_ready():
            if await self._should_start():
                self.post_router_stats.start()
        else:
            # Start when bot becomes ready
            self.post_router_stats.start()

    def cog_unload(self) -> None:
        """Clean up when cog is unloaded."""
        if self.post_router_stats.is_running():
            self.post_router_stats.cancel()

    @commands.command(name="routerstats")
    @commands.is_owner()
    async def router_stats_manual(self, ctx: commands.Context) -> None:
        """Manually trigger router stats collection and posting."""
        await ctx.send("Collecting router stats...", delete_after=5)

        stats = await self._collect_router_stats()
        if not stats:
            await ctx.send("❌ Failed to collect router stats.")
            return

        post_text = self._format_stats_post(stats)
        success = await self._post_to_bluesky(post_text)

        if success:
            await ctx.send(f"✅ Router stats posted to Bluesky!\n```\n{post_text}\n```")
        else:
            await ctx.send("❌ Failed to post to Bluesky. Check logs for details.")

