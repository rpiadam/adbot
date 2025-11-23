#!/usr/bin/env python3
"""
Resolve a Discord invite code to get server information.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import discord
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN or DISCORD_TOKEN == "replace-me":
    print("ERROR: DISCORD_TOKEN not set in .env file")
    sys.exit(1)


async def resolve_invite(invite_code: str):
    """Resolve a Discord invite and get server/channel info."""
    client = discord.Client(intents=discord.Intents.default())
    
    try:
        await client.login(DISCORD_TOKEN)
        invite = await client.fetch_invite(invite_code, with_counts=True)
        
        print("\n" + "=" * 60)
        print("Discord Invite Information")
        print("=" * 60)
        print(f"Server Name: {invite.guild.name}")
        print(f"Server ID (Guild ID): {invite.guild.id}")
        print(f"Server Description: {invite.guild.description or 'N/A'}")
        print(f"Member Count: {invite.approximate_member_count}")
        print(f"Online Count: {invite.approximate_presence_count}")
        
        if invite.channel:
            print(f"\nChannel: #{invite.channel.name}")
            print(f"Channel ID: {invite.channel.id}")
            print(f"Channel Type: {invite.channel.type}")
        
        print("\n" + "=" * 60)
        print("Configuration for .env:")
        print("=" * 60)
        print(f"DISCORD_GUILD_ID={invite.guild.id}")
        if invite.channel:
            if invite.channel.type == discord.ChannelType.text:
                print(f"DISCORD_CHANNEL_ID={invite.channel.id}")
            else:
                print("# Note: This invite points to a non-text channel.")
                print(f"# Channel ID: {invite.channel.id} (Type: {invite.channel.type})")
                print("# You'll need to find a text channel ID from the server.")
        else:
            print("# Note: No channel specified in invite.")
            print("# You'll need to find a text channel ID from the server.")
        print("=" * 60)
        
    except discord.NotFound:
        print(f"ERROR: Invite code '{invite_code}' not found or expired.")
        sys.exit(1)
    except discord.HTTPException as e:
        print(f"ERROR: Failed to fetch invite: {e}")
        sys.exit(1)
    finally:
        await client.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/resolve_invite.py <invite_code>")
        print("Example: python scripts/resolve_invite.py 77jcCNfT")
        sys.exit(1)
    
    invite_code = sys.argv[1]
    # Remove https://discord.gg/ prefix if present
    if "discord.gg/" in invite_code:
        invite_code = invite_code.split("discord.gg/")[-1].split("?")[0]
    
    asyncio.run(resolve_invite(invite_code))

