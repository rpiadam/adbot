#!/usr/bin/env python3
"""
Helper script to get Discord Server (Guild) and Channel IDs.
This script connects to Discord and lists all servers and channels the bot is in.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN or DISCORD_TOKEN == "replace-me":
    print("ERROR: DISCORD_TOKEN not set in .env file")
    print("Please set DISCORD_TOKEN in your .env file first.")
    sys.exit(1)


class IDHelperBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.messages = True
        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self):
        print("\n" + "=" * 60)
        print("Discord Bot Connected!")
        print("=" * 60)
        print(f"Bot: {self.user} ({self.user.id})")
        print(f"Connected to {len(self.guilds)} server(s)\n")

        for guild in self.guilds:
            print(f"Server: {guild.name}")
            print(f"  Guild ID: {guild.id}")
            print(f"  Channels:")
            
            for channel in guild.text_channels:
                # Check if bot has permission to view the channel
                if channel.permissions_for(guild.me).view_channel:
                    print(f"    - #{channel.name}")
                    print(f"      Channel ID: {channel.id}")
            
            print()

        # If a specific channel ID is configured, show it
        channel_id = os.getenv("DISCORD_CHANNEL_ID")
        if channel_id and channel_id != "123456789012345678":
            try:
                channel = self.get_channel(int(channel_id))
                if channel:
                    print("=" * 60)
                    print("Currently Configured Channel:")
                    print(f"  Server: {channel.guild.name} ({channel.guild.id})")
                    print(f"  Channel: #{channel.name} ({channel.id})")
                    print("=" * 60)
                else:
                    print("=" * 60)
                    print(f"WARNING: Configured channel ID {channel_id} not found!")
                    print("The bot may not have access to this channel.")
                    print("=" * 60)
            except ValueError:
                print(f"WARNING: Invalid DISCORD_CHANNEL_ID: {channel_id}")

        print("\nTo update your .env file, use:")
        print("  DISCORD_GUILD_ID=<guild_id>")
        print("  DISCORD_CHANNEL_ID=<channel_id>")
        print("\nDisconnecting...")
        await self.close()


async def main():
    bot = IDHelperBot()
    try:
        await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("ERROR: Invalid Discord token. Please check your DISCORD_TOKEN in .env")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

