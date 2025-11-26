# Choosing Between Python and Ruby Versions

This bot is available in both **Python** and **Ruby** implementations. Both provide the same core Discord ↔ IRC relay functionality and share the same configuration format.

## Quick Comparison

| Feature | Python Version | Ruby Version |
|---------|---------------|--------------|
| **Core Relay** | ✅ Full-featured | ✅ Core functionality |
| **Web Dashboard** | ✅ Full dashboard | ✅ Basic dashboard |
| **API Server** | ✅ FastAPI (OpenAPI docs) | ✅ Sinatra |
| **Discord Commands** | ✅ Full command set | ⚠️ Basic commands (expandable) |
| **Moderation** | ✅ Complete toolkit | 🔜 To be added |
| **Games** | ✅ All games | 🔜 To be added |
| **Music** | ✅ Full playback | 🔜 To be added |
| **Monitoring** | ✅ Advanced | ✅ Basic |
| **RSS** | ✅ Full featured | ✅ Basic |
| **Docker** | ✅ Supported | 🔜 To be added |

## Which Should I Choose?

### Choose **Python** if:
- ✅ You want all features right now (moderation, games, music, etc.)
- ✅ You prefer Python ecosystem
- ✅ You want full Discord slash commands
- ✅ You need advanced monitoring features
- ✅ You want OpenAPI/Swagger API docs

### Choose **Ruby** if:
- ✅ You prefer Ruby ecosystem
- ✅ You only need core relay functionality
- ✅ You want to contribute Ruby code
- ✅ You're building custom features on top

## Setup Instructions

### Python Version

```bash
# 1. Install dependencies
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure (create .env file)
cp example.env .env
# Edit .env with your tokens

# 3. Run
python -m src.main
```

**Read more:** See main [README.md](README.md)

### Ruby Version

```bash
# 1. Install dependencies
bundle install

# 2. Configure (create .env file - same as Python!)
cp example.env .env
# Edit .env with your tokens

# 3. Run
./bin/ruby_bot
# Or: ruby -Ilib bin/ruby_bot
```

**Read more:** See [README_RUBY.md](README_RUBY.md)

## Shared Configuration

**Both versions use the same `.env` file!** You can switch between Python and Ruby without changing your configuration:

```env
# .env file works for both Python and Ruby
DISCORD_TOKEN=your_token_here
IRC_SERVER=irc.example.com
IRC_CHANNEL=#channel
# ... etc
```

**Note:** You should only run **one bot at a time** to avoid conflicts. The data storage format is compatible between both versions.

## Switching Between Versions

1. Stop the current bot (Ctrl+C)
2. Start the other version using the commands above
3. Both use the same `.env` and `data/` directory

## Contributing

If you want to help improve either version:
- **Python**: See main [README.md](README.md) and code in `src/`
- **Ruby**: See [README_RUBY.md](README_RUBY.md) and code in `lib/ruby_bot/`

Both versions aim for feature parity over time!


