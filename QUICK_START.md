# Quick Start Guide - Running the Bot on Your PC

## Step 1: Install Python Dependencies

Open a terminal in the `botnew` folder and run:

```bash
# Create a virtual environment (recommended)
python3 -m venv .venv

# Activate the virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate

# Install all required packages
pip install -r requirements.txt
```

## Step 2: Configure Environment Variables

1. Copy the example environment file:
   ```bash
   cp example.env .env
   ```

2. Edit `.env` and fill in your values. **Minimum required settings:**
   - `DISCORD_TOKEN` - Your Discord bot token (get from https://discord.com/developers/applications)
   - `DISCORD_CHANNEL_ID` - The Discord channel ID where the bot should operate
   - `IRC_SERVER` - IRC server address (e.g., `irc.vibetalk.net`)
   - `IRC_CHANNEL` - IRC channel name (e.g., `#testing`)
   - `IRC_NICK` - Your IRC nickname

3. **Optional but recommended:**
   - `DASHBOARD_USERNAME` - Username for web dashboard
   - `DASHBOARD_PASSWORD` - Password for web dashboard (or hash it using `python scripts/hash_dashboard_password.py yourpassword`)
   - `DASHBOARD_SECRET_KEY` - Random secret key for JWT tokens

## Step 3: Run the Bot

```bash
# Make sure virtual environment is activated
source .venv/bin/activate  # macOS/Linux
# OR
# .venv\Scripts\activate  # Windows

# Run the bot
python -m src.main
```

The bot will:
- Connect to Discord
- Connect to IRC
- Start the web API server on `http://0.0.0.0:8000`

## Step 4: Access the Dashboard (Optional)

Open your browser and go to:
- **Dashboard**: `http://localhost:8000/`
- **API Docs**: `http://localhost:8000/docs`

## Troubleshooting

- **"Module not found" errors**: Make sure you activated the virtual environment and installed dependencies
- **"Port already in use"**: Change `API_PORT` in `.env` to a different port (e.g., 8001)
- **Discord connection fails**: Check your `DISCORD_TOKEN` is correct
- **IRC connection fails**: Check your IRC server settings and network connection

## Running in Background (Optional)

### macOS/Linux:
```bash
# Run in background with nohup
nohup python -m src.main > bot.log 2>&1 &

# Or use screen/tmux
screen -S bot
python -m src.main
# Press Ctrl+A then D to detach
```

### Windows:
Use Task Scheduler or run it in a separate terminal window.

## Stopping the Bot

- Press `Ctrl+C` in the terminal
- Or if running in background, find the process and kill it:
  ```bash
  # Find the process
  ps aux | grep "src.main"
  # Kill it
  kill <PID>
  ```

