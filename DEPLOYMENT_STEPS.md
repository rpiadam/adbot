# Deployment Steps

## Quick Start Guide

### 1. Extract and Setup

1. Extract `botnew.zip` to your server
2. Navigate to the directory:
   ```bash
   cd botnew
   ```

### 2. Install Dependencies

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Linux/Mac
# OR
.venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

1. Copy the example environment file:
   ```bash
   cp example.env .env
   ```

2. Edit `.env` with your configuration:
   ```bash
   nano .env  # or use your preferred editor
   ```

3. **Required settings:**
   - `DISCORD_TOKEN` - Your Discord bot token
   - `DISCORD_CHANNEL_ID` - Channel ID for relay
   - `IRC_SERVER` - IRC server address
   - `IRC_CHANNEL` - IRC channel name (include # if needed)
   - `IRC_NICK` - IRC nickname

4. **Optional but recommended:**
   - `DASHBOARD_USERNAME` - Dashboard login username
   - `DASHBOARD_PASSWORD` - Dashboard password (hash it for production!)
   - `DASHBOARD_SECRET_KEY` - Change from default!

### 4. Hash Dashboard Password (Production)

```bash
python scripts/hash_dashboard_password.py your-secure-password
# Copy the output hash to .env as DASHBOARD_PASSWORD
```

### 5. Create Required Directories

```bash
mkdir -p logs data backups
```

### 6. Run the Bot

```bash
python -m src.main
```

The bot will:
- Connect to Discord
- Connect to IRC
- Start the web dashboard on port 8000 (default)

### 7. Access the Dashboard

Open your browser and navigate to:
```
http://your-server-ip:8000
```

Or if running locally:
```
http://localhost:8000
```

## Docker Deployment (Recommended)

### Using Docker Compose

1. Make sure you have `.env` configured
2. Run:
   ```bash
   docker-compose up -d
   ```

3. View logs:
   ```bash
   docker-compose logs -f
   ```

### Manual Docker

1. Build the image:
   ```bash
   docker build -t uplove-bot .
   ```

2. Run the container:
   ```bash
   docker run -d \
     --name uplove-bot \
     -p 8000:8000 \
     -v $(pwd)/.env:/app/.env:ro \
     -v $(pwd)/data:/app/data \
     -v $(pwd)/logs:/app/logs \
     --restart unless-stopped \
     uplove-bot
   ```

## Systemd Service (Linux)

1. Create service file:
   ```bash
   sudo nano /etc/systemd/system/uplove-bot.service
   ```

2. Add this content:
   ```ini
   [Unit]
   Description=UpLove Discord/IRC Bot
   After=network.target

   [Service]
   Type=simple
   User=your-user
   WorkingDirectory=/path/to/botnew
   Environment="PATH=/path/to/botnew/.venv/bin"
   ExecStart=/path/to/botnew/.venv/bin/python -m src.main
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable uplove-bot
   sudo systemctl start uplove-bot
   sudo systemctl status uplove-bot
   ```

## Reverse Proxy (Nginx)

If you want to access the dashboard via a domain:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Verification

1. **Check bot is running:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status":"ok"}
   ```

2. **Check Discord connection:**
   - Bot should appear online in Discord
   - Check logs: `tail -f logs/bot.log`

3. **Check IRC connection:**
   - Bot should appear in IRC channel
   - Check logs for connection messages

4. **Check dashboard:**
   - Visit `http://your-server:8000`
   - Login with dashboard credentials
   - Verify all tabs load correctly

## Troubleshooting

- **Bot won't start:** Check `.env` file has all required variables
- **Can't connect to Discord:** Verify `DISCORD_TOKEN` is correct
- **Can't connect to IRC:** Check firewall allows outbound connections
- **Dashboard not accessible:** Check port 8000 is open and not blocked
- **See logs:** `tail -f logs/bot.log`

For more help, see `docs/TROUBLESHOOTING.md`


