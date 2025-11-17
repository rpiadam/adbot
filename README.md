# UpLove – Community Operations Suite

UpLove is a production-ready Python bot that bridges Discord and IRC while powering essential community operations: moderation, welcome automation, monitoring, RSS alerts, music playback, lightweight games, and Football Nation match broadcasts.

## Features

- **Discord ↔ IRC Relay**: Realtime bridge between a Discord text channel and an IRC channel.
- **Football Nation**: FastAPI webhook endpoint that formats match events for both Discord and IRC.
- **Welcome Experience**: Configurable welcomes in a designated channel and DMs for new members.
- **Welcome Moderation**: Auto-ban protection against raids with configurable account age requirements and join rate limiting.
- **Moderation Toolkit**: Purge, kick, ban, timeout, mute/unmute, profanity filtering, warning/strike tracking, URL validation, and join/leave logging with audit embeds.
- **Web Dashboard**: Browser-based management interface for feature toggles, configuration, bot statistics, and system health monitoring.
- **API Documentation**: Auto-generated OpenAPI/Swagger documentation at `/docs`.
- **Docker Support**: Containerized deployment with Docker and docker-compose.
- **Backup/Restore**: Configuration backup and restore functionality.
- **Admin Utilities**: Announcements, runtime stats, and configuration diagnostics.
- **Monitoring & Uptime**: Periodic URL checks with down/up alerts posted into Discord.
- **RSS Live Feed**: Poll configured RSS feeds and push new entries with rich embeds.
- **Dynamic Configuration**: Manage monitoring targets and RSS feeds with slash commands.
- **Music Playback**: Playlist-aware queue with rich now-playing embeds and thumbnails powered by yt-dlp + FFmpeg.
- **Games & Fun**: Coin flips, dice rolls, slots, hangman, tic-tac-toe, trivia, word ladders, and a credit-based gambling system with admin rewards.
- **Help System**: Category-based help command that summarizes available commands.

## Getting Started

1. **Create a virtual environment and install dependencies:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**

   Copy `example.env` to `.env` and fill in your secrets. At minimum you must set:

   - `DISCORD_TOKEN` - Your Discord bot token (get from https://discord.com/developers/applications)
   - `DISCORD_CHANNEL_ID` - The Discord channel ID to bridge
   - `IRC_SERVER` or `IRC_SERVERS` - IRC server address(es)
   - `IRC_CHANNEL` or `IRC_CHANNELS` - IRC channel name(s)
   - `IRC_NICK` or `IRC_NICKS` - IRC nickname(s)
   
   **Note:** For multiple IRC networks, use `IRC_SERVERS`, `IRC_PORTS`, `IRC_TLS`, `IRC_CHANNELS`, and `IRC_NICKS` as comma-separated lists. See `example.env` for details.

   Optionally set:

   - `DISCORD_WEBHOOK_URL` if you want Football Nation events mirrored through a Discord incoming webhook in addition to the bot post.
   - `WELCOME_CHANNEL_ID`, `ANNOUNCEMENTS_CHANNEL_ID`, `MODERATION_LOG_CHANNEL_ID` for targeted messaging.
   - `MODERATION_MIN_ACCOUNT_AGE_DAYS`, `MODERATION_JOIN_RATE_LIMIT_COUNT`, `MODERATION_JOIN_RATE_LIMIT_SECONDS` for welcome moderation (anti-raid protection).
   - `DASHBOARD_USERNAME`, `DASHBOARD_PASSWORD`, `DASHBOARD_SECRET_KEY` for web dashboard access.
   - `MONITOR_URLS`, `RSS_FEEDS`, `MUSIC_VOICE_CHANNEL_ID`, `MUSIC_TEXT_CHANNEL_ID` to enable monitoring, RSS, and music experiences.
   - `FOOTBALL_WEBHOOK_SECRET`, `FOOTBALL_DEFAULT_COMPETITION`, `FOOTBALL_DEFAULT_TEAM` to enrich match updates.

3. **Run the bot:**

   ```bash
   source .venv/bin/activate
   python -m src.main
   ```

   The web server listens on `API_HOST:API_PORT` (default `0.0.0.0:8000`). The Discord bot connects using `DISCORD_TOKEN`, and the IRC client joins `IRC_CHANNEL`.

4. **Access the Web Dashboard (optional):**

   Navigate to `http://<API_HOST>:<API_PORT>/` in your browser. The dashboard provides:
   - Real-time bot statistics (guilds, users, latency, IRC status, uptime, error count)
   - Feature flag toggles (enable/disable bot features)
   - Monitor URL management
   - RSS feed management
   - Moderation logs viewing
   - System health monitoring
   
   **API Documentation**: Visit `http://<API_HOST>:<API_PORT>/docs` for interactive API documentation.
   
   **Security Note**: For production, hash your dashboard password:
   ```bash
   python scripts/hash_dashboard_password.py yourpassword
   ```
   Then use the generated hash in your `.env` file instead of the plain password.

## Webhook Contract

Send an HTTP `POST` to `http://<host>:<port>/football-nation` with JSON like:

```json
{
  "title": "Second Half Kick-off",
  "competition": "Premier League",
  "team": "Football Nation FC",
  "opponent": "Rivals United",
  "minute": 46,
  "score_home": 1,
  "score_away": 0,
  "commentary": "We're back underway!"
}
```

Include the header `X-Webhook-Secret` if `FOOTBALL_WEBHOOK_SECRET` is set. The bot formats the payload into a concise update and posts it to both Discord and IRC.

## Command Overview

| Category    | Sample Slash Commands                                                                 |
| ----------- | ------------------------------------------------------------------------------------- |
| Features    | `/relaystatus`, `/relayping`, `/relayshutdown`                                        |
| Moderation  | `/purge`, `/kick`, `/ban`, `/timeout`, `/slowmode`, `/warn`, `/roleadd`, `/temprole`   |
| Admin       | `/relayannounce`, `/relaystats`, `/relaydebug`, `/relayreload`, `/relayrestart`       |
| Games       | `/coinflip`, `/roll`, `/pick`, `/slots`, `/gamble`, `/hangman start`, `/tictactoe start`, `/trivia`, `/reward`, `/credits` |
| Monitoring  | `/monitor list`, `/monitor add`, `/monitor remove`                                    |
| RSS         | `/rss list`, `/rss add`, `/rss remove`                                                |
| Help        | `/help overview`, `/help category`, `/help admin`                                     |
| Music       | `/music join`, `/music play`, `/music skip`, `/music stop`, `/music queue`            |
| Football    | `/football`                                                                           |

Use `/help` for a complete overview or `/help <category>` to drill down.

## Welcome Moderation

The bot includes automatic protection against raids and suspicious accounts:

- **Account Age Check**: Auto-ban accounts created less than a configured number of days ago (default: 7 days)
- **Rate Limiting**: Auto-ban if too many users join within a time window (default: 5 joins per 60 seconds)

Configure via environment variables:
- `MODERATION_MIN_ACCOUNT_AGE_DAYS` - Minimum account age in days (set to 0 or omit to disable)
- `MODERATION_JOIN_RATE_LIMIT_COUNT` - Maximum joins allowed in the time window
- `MODERATION_JOIN_RATE_LIMIT_SECONDS` - Time window in seconds

## Web Dashboard

Access the dashboard at `http://<API_HOST>:<API_PORT>/` to:
- View real-time bot statistics
- Toggle feature flags on/off
- Manage monitor URLs
- Manage RSS feeds

**Security**: The dashboard supports both plain text and bcrypt-hashed passwords. For production, use a hashed password:
```bash
python scripts/hash_dashboard_password.py yourpassword
```

## Docker Deployment

The bot can be deployed using Docker:

```bash
# Build and run with docker-compose
docker-compose up -d

# Or build manually
docker build -t uplove-bot .
docker run -d --name uplove-bot -p 8000:8000 -v $(pwd)/.env:/app/.env:ro -v $(pwd)/data:/app/data uplove-bot
```

Make sure to mount your `.env` file and `data` directory as volumes for persistence.

## Backup and Restore

Backup your configuration and data:

```bash
# Create a backup
python scripts/backup_config.py backup

# List all backups
python scripts/backup_config.py list

# Restore from a backup
python scripts/backup_config.py restore backup_20240101_120000
```

Backups are stored in the `backups/` directory and include:
- Configuration state (`data/config_state.json`)
- Environment files (`.env`, `.env.encrypted`)
- All data files

## CI/CD

The project includes GitHub Actions workflows:
- **CI**: Automated testing on Python 3.10, 3.11, 3.12
- **Linting**: Code quality checks (flake8, black, isort)
- **Docker Build**: Automated Docker image building

See `.github/workflows/` for details.

## Development Tips

- Run `uvicorn src.api:create_app --factory` if you wish to iterate on the API independently.
- Adjust logging levels by modifying `configure_logging()` in `src/main.py` if you need more or less verbosity.
- Extend `RelayCoordinator` if you need multi-channel or multi-guild support for the IRC bridge.
- Logs are written to `logs/bot.log` with automatic rotation (10MB per file, 5 backups).
- Run tests with `pytest tests/` to verify functionality.
- API endpoints are rate-limited to prevent abuse (login: 5/min, other endpoints: 10-60/min).
- Configuration is validated on startup - fix any errors before the bot will start.

## Testing

Run the test suite with:

```bash
pytest tests/ -v
```

The test suite includes:
- API endpoint tests
- Moderation feature tests
- Storage and configuration tests
- Integration tests
- Warning system tests

## Documentation

- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [Deployment Steps](DEPLOYMENT_STEPS.md) - Quick deployment guide
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [Admin Help](docs/help/admin.md) - Administrator command reference

## License

MIT License. See `LICENSE` for details.


