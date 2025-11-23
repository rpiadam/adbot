Admin Command Reference
=======================

Relay Management
----------------
- `/relayannounce <message>` — send a formatted announcement to the configured channel.
- `/relayreload` — reload dynamic configuration from disk and resync slash commands.
- `/relayrestart` — gracefully restart the relay process.
- `/relaystats` — view detailed runtime statistics (guilds, users, latency, uptime, message counts, health status, etc.).
- `/relaydebug` — inspect environment and configuration context for troubleshooting.
- `/relaystatus` — show Discord ↔ IRC bridge status with detailed network information.
- `/relayping` — measure the relay's Discord latency.
- `/serverinfo` — show information about the current Discord server (members, channels, roles, permissions, etc.).
- `/downloadbot [version]` — download the bot code as a zip file (python or ruby version).
- `/relayshutdown` — shut down the relay bot gracefully.
- `/reward <member> <amount> [overwrite]` — grant or set gamble credits for a user.

Moderation Essentials
---------------------
- `/kick <member> [reason]` — remove a member from the guild.
- `/ban <member> [reason]` — ban with 24-hour message pruning by default.
- `/unban <user> [reason]` — unban a user from the server (use user ID or username).
- `/timeout <member> <minutes> [reason]` — apply Discord's native timeout.
- `/mute <member> <minutes> [reason]` — assign the configured muted role temporarily.
- `/unmute <member> [reason]` — lift a mute early and cancel timers.
- `/warn <member> [reason]` — DM a warning and log it. Tracks warning count per user.
- `/warnings <member>` — View all warnings for a member with details.
- `/clearwarnings <member>` — Clear all warnings for a member.
- `/purge <count>` — bulk delete messages in the current channel (max 100).
- `/slowmode <seconds>` — set slowmode delay in the active text channel (0-21600).

Role Controls
-------------
- `/roleadd <member> <role> [reason]` — grant a role.
- `/roleremove <member> <role> [reason]` — remove a role.
- `/temprole <member> <role> <minutes> [reason]` — assign a role with auto-expiry (5-2880 minutes).

ZNC Management
--------------
- `/znc config [base_url] [admin_username] [admin_password]` — configure ZNC server settings (view current config if no parameters provided).

Configuration Management
------------------------
- `/monitor list` — show all monitored URLs.
- `/monitor add <url>` — add a URL to the monitoring list.
- `/monitor remove <url>` — remove a URL from monitoring.
- `/rss list` — show all configured RSS feeds.
- `/rss add <url>` — add an RSS/Atom feed to monitor.
- `/rss remove <url>` — remove an RSS feed.
- `/football config` — view or update default football values.

Web Dashboard
-------------
Access the web dashboard at `http://<API_HOST>:<API_PORT>/` to:
- View bot statistics in real-time
- Toggle features on/off (games, music, monitoring, RSS, welcome, moderation, football, znc)
- Manage bot configuration via web interface

Configure dashboard credentials in `.env`:
- `DASHBOARD_USERNAME` — login username
- `DASHBOARD_PASSWORD` — login password
- `DASHBOARD_SECRET_KEY` — JWT secret key (change from default)

