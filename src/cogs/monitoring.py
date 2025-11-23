from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING, Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


class MonitoringCog(commands.Cog):
    """Website uptime monitoring with alerting into Discord."""

    def __init__(self, coordinator: "RelayCoordinator"):
        self.coordinator = coordinator
        self._session: Optional[aiohttp.ClientSession] = None
        self._status_cache: dict[str, bool] = {}
        self.monitor_websites.start()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def cog_unload(self) -> None:
        if self.monitor_websites.is_running():
            self.monitor_websites.cancel()
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

    async def _announce(self, message: str) -> None:
        channel = await self._get_channel()
        if channel:
            await channel.send(message)

    @tasks.loop(seconds=60)
    async def monitor_websites(self) -> None:
        targets = await self.coordinator.config_store.list_monitor_targets()
        if not targets:
            return
        session = await self._get_session()
        for target in targets:
            url = target["url"]
            result = await self._probe_target(session, target)
            await self.coordinator.config_store.record_monitor_sample(url, result)
            prev_status = self._status_cache.get(url)
            self._status_cache[url] = result["is_up"]
            if prev_status is None:
                continue
            if prev_status and not result["is_up"]:
                reason = result.get("reason") or "unknown issue"
                await self._announce(f"🔻 {url} appears to be **down** ({reason}).")
            elif not prev_status and result["is_up"]:
                latency = result.get("latency_ms")
                latency_str = f"{latency:.0f} ms" if latency is not None else "restored"
                await self._announce(f"✅ {url} has recovered ({latency_str}).")

    async def _probe_target(self, session: aiohttp.ClientSession, target: dict[str, Any]) -> dict[str, Any]:
        url = target["url"]
        metadata = {
            "keyword": target.get("keyword"),
            "expected_status": target.get("expected_status"),
        }
        timestamp = datetime.now(timezone.utc).isoformat()
        base_result: dict[str, Any] = {
            "url": url,
            "timestamp": timestamp,
            "keyword": metadata["keyword"],
            "expected_status": metadata["expected_status"],
        }

        start = time.perf_counter()
        try:
            async with session.get(url, allow_redirects=True) as response:
                latency_ms = (time.perf_counter() - start) * 1000
                status_code = response.status
                is_up = 200 <= status_code < 400
                reason: Optional[str] = None

                expected_status = metadata["expected_status"]
                if expected_status is not None and status_code != expected_status:
                    is_up = False
                    reason = f"status {status_code}, expected {expected_status}"

                keyword = metadata["keyword"]
                keyword_present: Optional[bool] = None
                if keyword:
                    body_text = await self._read_body_sample(response)
                    keyword_present = keyword.lower() in body_text.lower()
                    if not keyword_present:
                        is_up = False
                        reason = f"missing keyword '{keyword}'"

                tls_days_remaining = self._extract_tls_days_remaining(response)

                if not is_up and reason is None:
                    reason = f"HTTP {status_code}"

                base_result.update(
                    {
                        "status_code": status_code,
                        "is_up": is_up,
                        "latency_ms": round(latency_ms, 2),
                        "reason": reason,
                        "keyword_present": keyword_present,
                        "tls_days_remaining": tls_days_remaining,
                    }
                )
                return base_result
        except asyncio.TimeoutError:
            base_result.update(
                {
                    "is_up": False,
                    "reason": "request timed out",
                }
            )
        except aiohttp.ClientError as exc:
            base_result.update(
                {
                    "is_up": False,
                    "reason": str(exc),
                }
            )

        return base_result

    async def _read_body_sample(self, response: aiohttp.ClientResponse, limit: int = 256_000) -> str:
        try:
            chunk = await response.content.read(limit)
        except Exception:
            return ""
        return chunk.decode("utf-8", errors="ignore")

    def _extract_tls_days_remaining(self, response: aiohttp.ClientResponse) -> Optional[int]:
        if response.url.scheme != "https":
            return None
        connection = response.connection
        if connection is None or connection.transport is None:
            return None
        ssl_object = connection.transport.get_extra_info("ssl_object")
        if ssl_object is None:
            return None
        cert = ssl_object.getpeercert()
        not_after = cert.get("notAfter")
        if not not_after:
            return None
        try:
            expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
        delta = expiry - datetime.now(timezone.utc)
        days = int(delta.total_seconds() // 86400)
        return max(days, 0)

    @monitor_websites.before_loop
    async def before_monitor(self) -> None:
        await self.coordinator.discord_bot.wait_until_ready()
        interval = self.coordinator.settings.monitor_interval_seconds
        self.monitor_websites.change_interval(seconds=interval)

    @app_commands.command(name="monitorlist", description="List the URLs currently being monitored.")
    async def monitor_list(self, interaction: discord.Interaction) -> None:
        targets = await self.coordinator.config_store.list_monitor_targets()
        if not targets:
            await interaction.response.send_message("No monitoring targets configured.", ephemeral=True)
            return

        lines = []
        for target in targets:
            url = target["url"]
            snapshot = await self.coordinator.config_store.get_monitor_snapshot(url)
            status = snapshot["is_up"] if snapshot else None
            emoji = "✅" if status else ("🔻" if status is False else "⚪️")
            extras: list[str] = []
            if snapshot and snapshot.get("latency_ms") is not None:
                extras.append(f"{snapshot['latency_ms']:.0f} ms")
            if snapshot and snapshot.get("status_code"):
                extras.append(f"HTTP {snapshot['status_code']}")
            if snapshot and snapshot.get("tls_days_remaining") is not None:
                extras.append(f"TLS {snapshot['tls_days_remaining']}d")
            if target.get("keyword"):
                extras.append(f"keyword='{target['keyword']}'")
            if target.get("expected_status"):
                extras.append(f"expect={target['expected_status']}")
            lines.append(f"{emoji} {url} ({', '.join(extras) if extras else 'no samples yet'})")

        await interaction.response.send_message("**Monitoring Targets**\n" + "\n".join(lines), ephemeral=True)

    @app_commands.command(name="monitorhistory", description="Show recent check history for a URL.")
    @app_commands.describe(url="URL to inspect", limit="Number of recent samples to include (max 15)")
    async def monitor_history(
        self,
        interaction: discord.Interaction,
        url: str,
        limit: app_commands.Range[int, 1, 15] = 5,
    ) -> None:
        history = await self.coordinator.config_store.get_monitor_history(url, limit=limit)
        if not history:
            await interaction.response.send_message("No samples recorded for that URL yet.", ephemeral=True)
            return

        lines = []
        for sample in reversed(history):
            status = "UP" if sample.get("is_up") else "DOWN"
            latency = f"{sample.get('latency_ms', 0):.0f} ms" if sample.get("latency_ms") is not None else "n/a"
            status_code = sample.get("status_code") or "-"
            reason = sample.get("reason") or "ok"
            timestamp = sample.get("timestamp", "unknown")
            lines.append(f"[{timestamp}] {status} ({status_code}, {latency}) – {reason}")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        message = "Unable to process that monitoring request."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


