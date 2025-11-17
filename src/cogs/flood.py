from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

import discord
import httpx
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ..relay import RelayCoordinator


class FloodCog(commands.Cog):
    """Spam flood commands for testing network connectivity."""

    def __init__(self, coordinator: RelayCoordinator):
        self.coordinator = coordinator

    def _parse_url(self, url: str, port: int) -> tuple[str, str]:
        """Parse URL and return (scheme, netloc with port)."""
        # If URL doesn't have a scheme, add http://
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"
        
        parsed = urlparse(url)
        scheme = parsed.scheme or "http"
        netloc = parsed.netloc or parsed.path.split("/")[0]
        
        # Remove existing port if present
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        
        # Add the specified port
        netloc_with_port = f"{netloc}:{port}"
        
        return scheme, netloc_with_port

    @app_commands.command(name="flood", description="Spam flood a domain/URL with HTTP requests.")
    @app_commands.describe(
        url="Domain or URL to flood (e.g. example.com or http://example.com)",
        port="Port number to connect to",
        count="Number of requests to send"
    )
    async def flood_target(
        self,
        interaction: discord.Interaction,
        url: str,
        port: int,
        count: int,
    ) -> None:
        """Flood a target URL with HTTP requests."""
        if not url or len(url) > 255:
            await interaction.response.send_message(
                "Please provide a valid domain or URL.",
                ephemeral=True,
            )
            return

        if port < 1 or port > 65535:
            await interaction.response.send_message(
                "Port must be between 1 and 65535.",
                ephemeral=True,
            )
            return

        if count < 1 or count > 1000:
            await interaction.response.send_message(
                "Count must be between 1 and 1000.",
                ephemeral=True,
            )
            return

        # Respond immediately to avoid timeout
        await interaction.response.send_message(
            f"🚀 Starting flood of `{url}:{port}` with {count} requests...",
            ephemeral=True,
        )

        # Process in background
        asyncio.create_task(self._run_flood(interaction, url, port, count))

    async def _run_flood(
        self,
        interaction: discord.Interaction,
        url: str,
        port: int,
        count: int,
    ) -> None:
        """Run the flood in the background."""
        try:
            scheme, netloc = self._parse_url(url, port)
            target_url = f"{scheme}://{netloc}/"
            
            success_count = 0
            error_count = 0
            timeout = httpx.Timeout(3.0, connect=3.0)
            
            # Process in batches to avoid overwhelming the system
            batch_size = 50
            error_messages: dict[str, int] = {}  # Track error types
            
            # Create client with event hooks disabled to prevent logging
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                limits=httpx.Limits(max_connections=100),
                event_hooks={}  # Disable event hooks to prevent request logging
            ) as client:
                for batch_start in range(0, count, batch_size):
                    batch_end = min(batch_start + batch_size, count)
                    batch_tasks = [
                        self._make_request(client, target_url, i)
                        for i in range(batch_start, batch_end)
                    ]
                    
                    results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    for result in results:
                        if isinstance(result, Exception):
                            error_count += 1
                            error_msg = str(result)[:50]
                            error_messages[error_msg] = error_messages.get(error_msg, 0) + 1
                        elif isinstance(result, tuple):
                            success, error_msg = result
                            if success:
                                success_count += 1
                            else:
                                error_count += 1
                                if error_msg:
                                    error_messages[error_msg] = error_messages.get(error_msg, 0) + 1
                        else:
                            error_count += 1
                    
                    # Small delay between batches to avoid rate limiting
                    if batch_end < count:
                        await asyncio.sleep(0.1)

            # Build result message
            message = (
                f"**Flood Complete**\n"
                f"Target: `{target_url}`\n"
                f"Requests sent: {count}\n"
                f"Successful: {success_count}\n"
                f"Failed: {error_count}"
            )
            
            # Add error details if all failed
            if success_count == 0 and error_messages:
                most_common_error = max(error_messages.items(), key=lambda x: x[1])
                message += f"\n\n**Most common error:** {most_common_error[0]} ({most_common_error[1]}x)"
                if "not be an HTTP server" in most_common_error[0] or "Protocol error" in most_common_error[0]:
                    message += "\n⚠️ **Note:** Target must be an HTTP/HTTPS server (not IRC, FTP, etc.)"
            
            await interaction.followup.send(message[:2000], ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error during flood: {str(e)[:500]}",
                ephemeral=True,
            )

    async def _make_request(self, client: httpx.AsyncClient, url: str, request_num: int) -> tuple[bool, Optional[str]]:
        """Make a single HTTP request and return (success, error_message)."""
        try:
            response = await client.get(url)
            return (response.status_code < 500, None)
        except httpx.ConnectError as e:
            return (False, f"Connection refused - target may not be an HTTP server")
        except httpx.TimeoutException:
            return (False, "Connection timeout")
        except httpx.ProtocolError as e:
            return (False, f"Protocol error - target doesn't speak HTTP")
        except Exception as e:
            return (False, str(e)[:100])

    @app_commands.command(name="pingflood", description="Send multiple ICMP ping packets to a domain/IP.")
    @app_commands.describe(
        target="Domain or IP address to ping (e.g. example.com or 8.8.8.8)",
        count="Number of ping packets to send (1-10000)"
    )
    async def ping_flood(
        self,
        interaction: discord.Interaction,
        target: str,
        count: int,
    ) -> None:
        """Flood a target with ICMP ping packets."""
        if not target or len(target) > 255:
            await interaction.response.send_message(
                "Please provide a valid domain or IP address.",
                ephemeral=True,
            )
            return

        if count < 1 or count > 10000:
            await interaction.response.send_message(
                "Count must be between 1 and 10000.",
                ephemeral=True,
            )
            return

        # Respond immediately to avoid timeout
        await interaction.response.send_message(
            f"🏓 Starting ping flood of `{target}` with {count} packets...",
            ephemeral=True,
        )

        # Process in background
        asyncio.create_task(self._run_ping_flood(interaction, target, count))

    async def _run_ping_flood(
        self,
        interaction: discord.Interaction,
        target: str,
        count: int,
    ) -> None:
        """Run the ping flood in the background."""
        try:
            # Extract hostname/IP from target (remove http:// etc if present)
            hostname = target
            if "://" in hostname:
                from urllib.parse import urlparse
                parsed = urlparse(target)
                hostname = parsed.netloc or parsed.path.split("/")[0]
            # Remove port if present
            if ":" in hostname:
                hostname = hostname.split(":")[0]

            # Use ping command with high count
            # On macOS/Linux: ping -c count -W timeout target
            # -c: count, -W: timeout per packet (seconds)
            process = await asyncio.create_subprocess_exec(
                "ping",
                "-c",
                str(count),
                "-W",
                "1",  # 1 second timeout per packet
                hostname,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for completion with a reasonable timeout
            # Estimate: 1 second per packet + overhead
            timeout_seconds = min(count * 1.5 + 30, 300)  # Max 5 minutes
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                await interaction.followup.send(
                    f"⏱️ Ping flood timed out after {timeout_seconds} seconds. "
                    f"Processed some packets before timeout.",
                    ephemeral=True,
                )
                return

            # Parse ping output to get statistics
            output = stdout.decode("utf-8", errors="ignore")
            error_output = stderr.decode("utf-8", errors="ignore")

            if process.returncode != 0 and not output:
                await interaction.followup.send(
                    f"❌ Ping failed: {error_output[:500] if error_output else 'Unknown error'}",
                    ephemeral=True,
                )
                return

            # Extract statistics from ping output
            lines = output.split("\n")
            stats_line = None
            for line in reversed(lines):
                if "packets transmitted" in line.lower() or "packet loss" in line.lower():
                    stats_line = line
                    break

            # Build result message
            message = f"**Ping Flood Complete**\n"
            message += f"Target: `{hostname}`\n"
            message += f"Packets sent: {count}\n"
            
            if stats_line:
                message += f"\n**Statistics:**\n```\n{stats_line}\n```"
            
            # Include last few lines of output for details
            output_lines = [line for line in lines if line.strip()]
            if len(output_lines) > 3:
                message += f"\n**Last output:**\n```\n" + "\n".join(output_lines[-3:]) + "\n```"
            elif output_lines:
                message += f"\n**Output:**\n```\n" + "\n".join(output_lines) + "\n```"

            # Truncate if too long
            await interaction.followup.send(message[:2000], ephemeral=True)

        except asyncio.SubprocessError as e:
            await interaction.followup.send(
                f"❌ Unable to execute ping command: {str(e)[:500]}",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error during ping flood: {str(e)[:500]}",
                ephemeral=True,
            )

