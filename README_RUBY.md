# UpLove Ruby Bot

This is the Ruby version of the UpLove Discord/IRC relay bot. It provides the same core functionality as the Python version.

## Features

- **Discord ↔ IRC Relay**: Real-time bridge between a Discord text channel and IRC channels
- **Web Dashboard**: Browser-based management interface
- **REST API**: JSON API for integration and automation
- **Multi-network IRC Support**: Connect to multiple IRC networks simultaneously
- **Dynamic Configuration**: Manage monitor URLs and RSS feeds via API
- **Feature Flags**: Enable/disable features at runtime

## Prerequisites

- Ruby 3.0 or higher
- Bundler gem (`gem install bundler`)

## Installation

1. **Install dependencies:**

   ```bash
   bundle install
   ```

2. **Configure environment variables:**

   Copy `example.env` to `.env` and fill in your secrets. At minimum you must set:

   - `DISCORD_TOKEN` - Your Discord bot token (get from https://discord.com/developers/applications)
   - `DISCORD_CHANNEL_ID` - The Discord channel ID to bridge
   - `IRC_SERVER` or `IRC_SERVERS` - IRC server address(es)
   - `IRC_CHANNEL` or `IRC_CHANNELS` - IRC channel name(s)
   - `IRC_NICK` or `IRC_NICKS` - IRC nickname(s)

   For multiple IRC networks, use `IRC_SERVERS`, `IRC_PORTS`, `IRC_TLS`, `IRC_CHANNELS`, and `IRC_NICKS` as comma-separated lists.

3. **Make the executable script executable:**

   ```bash
   chmod +x bin/ruby_bot
   ```

## Running the Bot

```bash
# Using the executable script
./bin/ruby_bot

# Or using Ruby directly
ruby -Ilib bin/ruby_bot
```

The bot will:
- Connect to Discord using your bot token
- Connect to all configured IRC networks
- Start the web API server on `API_HOST:API_PORT` (default: `0.0.0.0:8000`)

## Web Dashboard

Access the dashboard at `http://<API_HOST>:<API_PORT>/dashboard`

The dashboard provides:
- Real-time bot statistics (uptime, Discord/IRC status, message count, errors)
- Feature flag toggles
- Monitor URL management
- RSS feed management

## API Endpoints

### Health Status
```
GET /api/health
```
Returns bot health statistics including uptime, connection status, and error counts.

### Features
```
GET /api/features
POST /api/features/:feature?enabled=true
```
Get or set feature flags.

### Monitor URLs
```
GET /api/monitor/urls
POST /api/monitor/urls (body: {"url": "https://example.com"})
DELETE /api/monitor/urls/:url
```
Manage monitoring URLs.

### RSS Feeds
```
GET /api/rss/feeds
POST /api/rss/feeds (body: {"url": "https://example.com/rss.xml"})
DELETE /api/rss/feeds/:url
```
Manage RSS feeds.

### Football Nation Webhook
```
POST /football-nation
```
Receive Football Nation match events. Include `X-Webhook-Secret` header if `FOOTBALL_WEBHOOK_SECRET` is configured.

## Architecture

The Ruby bot is structured similarly to the Python version:

- `lib/ruby_bot/config.rb` - Configuration loading and validation
- `lib/ruby_bot/storage.rb` - Persistent state storage (JSON-based)
- `lib/ruby_bot/relay.rb` - Discord/IRC relay coordinator
- `lib/ruby_bot/api.rb` - Sinatra-based REST API server
- `lib/ruby_bot.rb` - Main entry point

## Differences from Python Version

The Ruby version currently implements the core relay functionality and API. Some advanced features from the Python version (like moderation commands, games, music playback, etc.) are not yet implemented but can be added as needed.

## Development

The Ruby bot uses standard Ruby conventions:
- Gems are managed via `Gemfile` and Bundler
- Code follows Ruby style conventions
- Logging goes to stdout/stderr

## Troubleshooting

1. **Bot won't start**: Check that all required environment variables are set in `.env`
2. **IRC connection fails**: Verify IRC server address, port, and TLS settings
3. **Discord connection fails**: Verify your Discord bot token is correct and the bot has proper permissions
4. **API server won't start**: Check if the port is already in use: `lsof -i :8000`

## License

MIT License. See `LICENSE` for details.


