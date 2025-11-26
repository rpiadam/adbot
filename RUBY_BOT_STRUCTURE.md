# Ruby Bot Structure

This document describes the Ruby bot implementation that mirrors the Python bot functionality.

## Project Structure

```
botnew/
├── lib/
│   └── ruby_bot/
│       ├── version.rb       # Version constant
│       ├── config.rb        # Configuration loader (equivalent to src/config.py)
│       ├── storage.rb       # Persistent storage (equivalent to src/storage.py)
│       ├── relay.rb         # Discord/IRC relay coordinator (equivalent to src/relay.py)
│       └── api.rb           # Sinatra API server (equivalent to src/api.py)
├── bin/
│   └── ruby_bot            # Executable entry point
├── Gemfile                  # Ruby dependencies
├── README_RUBY.md          # Ruby bot documentation
└── .ruby-version           # Ruby version specification
```

## Key Components

### 1. Config (`lib/ruby_bot/config.rb`)
- Loads environment variables from `.env` file
- Supports single and multiple IRC network configurations
- Validates required settings on initialization
- Provides typed access to all configuration values

### 2. Storage (`lib/ruby_bot/storage.rb`)
- JSON-based persistent storage (same format as Python version)
- Thread-safe operations using Mutex
- Manages:
  - Monitor URLs
  - RSS feeds
  - User credits (for games)
  - Feature flags
  - Moderation logs

### 3. Relay Coordinator (`lib/ruby_bot/relay.rb`)
- Coordinates Discord and IRC connections
- Handles message forwarding between platforms
- Manages webhooks for better Discord message formatting
- Tracks health statistics (uptime, errors, message counts)
- Supports multiple IRC networks simultaneously

### 4. API Server (`lib/ruby_bot/api.rb`)
- Sinatra-based REST API
- Endpoints:
  - `/api/health` - System health status
  - `/api/features` - Feature flag management
  - `/api/monitor/urls` - Monitor URL management
  - `/api/rss/feeds` - RSS feed management
  - `/football-nation` - Football webhook endpoint
- Rate limiting via `rack-attack`
- Simple HTML dashboard at `/dashboard`

### 5. Main Entry Point (`lib/ruby_bot.rb` & `bin/ruby_bot`)
- Initializes configuration
- Starts Discord bot, IRC clients, and API server
- Handles graceful shutdown on SIGINT/SIGTERM

## Dependencies

Key Ruby gems used:
- `discordrb` - Discord bot library
- `cinch` - IRC client library
- `sinatra` - Web framework for API
- `puma` - Web server
- `dotenv` - Environment variable loading
- `rack-attack` - Rate limiting

## Differences from Python Version

1. **Language**: Ruby instead of Python
2. **Web Framework**: Sinatra instead of FastAPI
3. **IRC Library**: Cinch instead of pydle
4. **Async Model**: Threads instead of asyncio
5. **Scope**: Currently implements core relay functionality and API. Advanced features (moderation commands, games, music, etc.) can be added as needed.

## Usage

1. Install dependencies: `bundle install`
2. Configure `.env` file (same as Python version)
3. Run: `./bin/ruby_bot` or `ruby -Ilib bin/ruby_bot`

## Shared Configuration

Both Python and Ruby bots use the same:
- `.env` file format
- `data/config_state.json` storage format
- API endpoint structure
- Environment variable names

This means you can switch between Python and Ruby implementations without changing your configuration!

## Extending the Ruby Bot

To add features similar to the Python cogs:
1. Create new Ruby classes/modules in `lib/ruby_bot/`
2. Register Discord commands/events in `relay.rb`
3. Add API endpoints in `api.rb` if needed
4. Use the same `storage` instance for persistence

## Notes

- The Ruby bot shares the same data directory (`data/`) as the Python bot
- Both can read/write the same `config_state.json` file
- You should run only one bot at a time to avoid data conflicts
- The API port is configurable via `API_PORT` environment variable (default: 8000)


