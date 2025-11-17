# Deployment Guide

This guide covers deploying the UpLove bot in production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Docker Deployment](#docker-deployment)
- [Systemd Service](#systemd-service)
- [Production Checklist](#production-checklist)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- Python 3.10+ or Docker
- Discord Bot Token
- IRC server access
- (Optional) Domain/SSL certificate for dashboard

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd botnew
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp example.env .env
# Edit .env with your configuration
```

**Required variables:**
- `DISCORD_TOKEN` - Your Discord bot token
- `DISCORD_CHANNEL_ID` - Channel ID for relay
- `IRC_SERVER` - IRC server address
- `IRC_CHANNEL` - IRC channel name
- `IRC_NICK` - IRC nickname

### 3. Hash Dashboard Password (Production)

```bash
python scripts/hash_dashboard_password.py your-secure-password
# Copy the hash to .env as DASHBOARD_PASSWORD
```

### 4. Run the Bot

```bash
python -m src.main
```

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Manual Docker Build

```bash
# Build image
docker build -t uplove-bot .

# Run container
docker run -d \
  --name uplove-bot \
  -p 8000:8000 \
  -v $(pwd)/.env:/app/.env:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  uplove-bot
```

### Docker Environment Variables

You can override environment variables in `docker-compose.yml`:

```yaml
environment:
  - API_PORT=8000
  - DISCORD_TOKEN=${DISCORD_TOKEN}
```

## Systemd Service

Create a systemd service for automatic startup:

```bash
sudo nano /etc/systemd/system/uplove-bot.service
```

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

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable uplove-bot
sudo systemctl start uplove-bot
sudo systemctl status uplove-bot
```

## Production Checklist

### Security

- [ ] Change `DASHBOARD_SECRET_KEY` from default
- [ ] Use hashed password for dashboard (not plain text)
- [ ] Encrypt sensitive `.env` values or entire file
- [ ] Set proper file permissions on `.env` and `.encryption_key`
- [ ] Enable rate limiting (already enabled by default)
- [ ] Use HTTPS reverse proxy for dashboard if exposed

### Configuration

- [ ] Verify all required environment variables are set
- [ ] Test configuration with `python -m src.main` (will validate on startup)
- [ ] Configure welcome moderation settings
- [ ] Set up monitoring URLs and RSS feeds
- [ ] Configure moderation log channel

### Monitoring

- [ ] Set up log rotation (automatic, but verify `logs/` directory)
- [ ] Monitor bot uptime via dashboard
- [ ] Set up alerts for high error rates
- [ ] Regular backup of `data/` directory

### Performance

- [ ] Adjust `MONITOR_INTERVAL_SECONDS` based on needs
- [ ] Adjust `RSS_POLL_INTERVAL_SECONDS` based on needs
- [ ] Monitor resource usage (CPU, memory)
- [ ] Set appropriate rate limits if needed

## Reverse Proxy Setup (Nginx)

If exposing the dashboard publicly:

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

For HTTPS, add SSL certificates and redirect HTTP to HTTPS.

## Troubleshooting

### Bot Won't Start

1. **Check configuration validation:**
   ```bash
   python -m src.main
   ```
   Look for validation errors in the output.

2. **Check logs:**
   ```bash
   tail -f logs/bot.log
   ```

3. **Verify environment variables:**
   ```bash
   python -c "from src.config import settings; print(settings.validate())"
   ```

### Discord Connection Issues

- Verify `DISCORD_TOKEN` is correct
- Check bot has necessary permissions in Discord
- Ensure bot is invited to the server
- Check Discord status page for outages

### IRC Connection Issues

- Verify IRC server address and port
- Check firewall rules allow outbound connections
- Verify IRC credentials if required
- Test IRC connection manually: `nc irc.server.com 6667`

### Dashboard Not Accessible

- Check API port is not blocked by firewall
- Verify `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD` are set
- Check logs for authentication errors
- Ensure rate limiting isn't blocking you

### High Error Count

- Check `logs/bot.log` for error details
- Review recent moderation logs in dashboard
- Check Discord/IRC connection status
- Verify all required permissions are granted

## Backup and Recovery

### Regular Backups

```bash
# Create backup
python scripts/backup_config.py backup

# List backups
python scripts/backup_config.py list

# Restore backup
python scripts/backup_config.py restore backup_20240101_120000
```

### What to Backup

- `data/config_state.json` - All dynamic configuration
- `.env` or `.env.encrypted` - Environment configuration
- `.encryption_key` - Encryption key (store securely!)
- `logs/` - Log files (optional)

### Automated Backups

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * cd /path/to/botnew && python scripts/backup_config.py backup
```

## Performance Tuning

### Resource Limits

For Docker:

```yaml
deploy:
  resources:
    limits:
      cpus: '1'
      memory: 512M
```

### Log Rotation

Logs automatically rotate at 10MB, keeping 5 backups. Adjust in `src/main.py` if needed.

### Connection Pooling

The bot uses connection pooling for HTTP requests. No additional configuration needed.

## Scaling

The bot is designed for single-instance deployment. For multiple instances:

- Use different Discord bots for each instance
- Use different IRC channels or servers
- Share configuration via external storage if needed

## Support

For issues and questions:
- Check logs in `logs/bot.log`
- Review dashboard health metrics
- Check GitHub issues
- Review documentation in `docs/`

