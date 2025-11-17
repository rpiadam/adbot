# Troubleshooting Guide

Common issues and solutions for the UpLove bot.

## Configuration Issues

### "Configuration validation failed"

**Problem:** Bot won't start due to invalid configuration.

**Solutions:**
1. Check the error message for specific issues
2. Verify all required environment variables are set
3. Check port numbers are in valid range (1-65535)
4. Ensure moderation rate limit settings are paired correctly

**Example errors:**
- `DISCORD_TOKEN is required` - Set your Discord bot token
- `IRC_PORT must be between 1 and 65535` - Fix port number
- `MODERATION_JOIN_RATE_LIMIT_COUNT is required when MODERATION_JOIN_RATE_LIMIT_SECONDS is set` - Set both or neither

### "Invalid token" or "Authentication required"

**Problem:** Dashboard login fails.

**Solutions:**
1. Verify `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD` are set
2. If using hashed password, ensure it starts with `$2b$` or `$2a$`
3. Check `DASHBOARD_SECRET_KEY` is set and not default value
4. Clear browser localStorage and try again

## Connection Issues

### Discord Bot Not Connecting

**Symptoms:**
- Bot doesn't appear online
- No "IRC relay is online" message
- Dashboard shows Discord disconnected

**Solutions:**
1. Verify `DISCORD_TOKEN` is correct
2. Check bot is invited to server with proper permissions
3. Verify `DISCORD_CHANNEL_ID` is correct
4. Check Discord status: https://discordstatus.com
5. Review logs: `tail -f logs/bot.log`

**Permissions needed:**
- View Channels
- Send Messages
- Embed Links
- Read Message History
- Manage Webhooks (optional, for better formatting)

### IRC Not Connecting

**Symptoms:**
- Dashboard shows IRC disconnected
- Messages not relayed to IRC
- Connection errors in logs

**Solutions:**
1. Verify IRC server address and port
2. Check firewall allows outbound connections
3. Test IRC connection manually:
   ```bash
   nc irc.server.com 6667
   ```
4. Verify IRC channel name (include # if needed)
5. Check IRC server requires authentication
6. Review logs for specific error messages

### Frequent Reconnections

**Symptoms:**
- High reconnect count in dashboard
- Connection drops frequently
- Unstable relay

**Solutions:**
1. Check network stability
2. Verify server resources (CPU, memory)
3. Check for rate limiting on IRC server
4. Review error logs for patterns
5. Consider increasing reconnection delay

## Performance Issues

### High Latency

**Symptoms:**
- Slow message relay
- High latency in dashboard

**Solutions:**
1. Check Discord API status
2. Verify network connection quality
3. Check server resource usage
4. Reduce monitoring/RSS poll intervals if too frequent
5. Review logs for bottlenecks

### High Error Count

**Symptoms:**
- Error count increasing rapidly
- Health status shows "unhealthy"

**Solutions:**
1. Check `logs/bot.log` for error details
2. Review recent errors in moderation logs
3. Verify all permissions are correct
4. Check for API rate limiting
5. Review Discord/IRC connection stability

### Memory Usage

**Symptoms:**
- Bot using excessive memory
- Server running out of memory

**Solutions:**
1. Check moderation log size (limited to 1000 entries)
2. Review number of monitored URLs/RSS feeds
3. Check for memory leaks in logs
4. Restart bot periodically if needed
5. Consider increasing server memory

## Feature Issues

### Welcome Messages Not Sending

**Solutions:**
1. Verify `WELCOME_CHANNEL_ID` is set
2. Check bot has permission to send messages in channel
3. Verify welcome feature is enabled (check dashboard)
4. Check logs for permission errors

### Moderation Commands Not Working

**Solutions:**
1. Verify bot has required permissions:
   - Kick Members
   - Ban Members
   - Manage Roles
   - Moderate Members
2. Check moderation feature is enabled
3. Verify command user has required permissions
4. Check `MODERATION_LOG_CHANNEL_ID` is set for logging

### Music Not Playing

**Solutions:**
1. Verify `MUSIC_VOICE_CHANNEL_ID` and `MUSIC_TEXT_CHANNEL_ID` are set
2. Check bot has "Connect" and "Speak" permissions in voice channel
3. Ensure FFmpeg is installed
4. Check music feature is enabled
5. Verify yt-dlp is working: `yt-dlp --version`

### Monitoring Not Working

**Solutions:**
1. Verify URLs are added (check dashboard or `/monitor list`)
2. Check `MONITOR_INTERVAL_SECONDS` is reasonable (>= 60)
3. Verify bot can reach the URLs (firewall, network)
4. Check monitoring feature is enabled
5. Review logs for HTTP errors

## Dashboard Issues

### Can't Access Dashboard

**Solutions:**
1. Verify API server is running (check logs)
2. Check port is not blocked by firewall
3. Verify `API_HOST` and `API_PORT` settings
4. Try accessing `/health` endpoint
5. Check for rate limiting (wait a minute and retry)

### Dashboard Shows Wrong Data

**Solutions:**
1. Refresh the page
2. Check browser console for errors
3. Verify token is valid (logout and login again)
4. Check API endpoints are responding: `/api/stats`
5. Review server logs for API errors

### Features Not Toggling

**Solutions:**
1. Check browser console for errors
2. Verify API response (check Network tab)
3. Check rate limiting isn't blocking requests
4. Review server logs
5. Try refreshing the page

## Backup/Restore Issues

### Backup Fails

**Solutions:**
1. Verify `backups/` directory is writable
2. Check disk space
3. Verify files exist to backup
4. Check permissions on data files
5. Review error message in output

### Restore Doesn't Work

**Solutions:**
1. Verify backup name is correct (use `list` command)
2. Check backup manifest exists
3. Verify destination files are writable
4. Check for conflicting processes
5. Review restore output for errors

## Log Analysis

### Understanding Logs

Logs are in `logs/bot.log` with rotation:
- Current: `bot.log`
- Backups: `bot.log.1`, `bot.log.2`, etc.

**Common log patterns:**
- `INFO` - Normal operation
- `WARNING` - Non-critical issues
- `ERROR` - Errors that need attention
- `DEBUG` - Detailed debugging (if enabled)

### Finding Issues

```bash
# Recent errors
grep ERROR logs/bot.log | tail -20

# Connection issues
grep -i "connect\|disconnect" logs/bot.log | tail -20

# Configuration issues
grep -i "config\|validation" logs/bot.log | tail -20
```

## Getting Help

1. **Check logs first:** `logs/bot.log`
2. **Review dashboard:** Check health metrics
3. **Validate config:** Run bot to see validation errors
4. **Check documentation:** Review `docs/` directory
5. **GitHub issues:** Search for similar issues

## Common Error Messages

### "Port X is already in use"
- Another process is using the port
- Change `API_PORT` in `.env`
- Or stop the conflicting process

### "Invalid authentication credentials"
- Token expired or invalid
- Logout and login again
- Check token in localStorage

### "Rate limit exceeded"
- Too many requests to API
- Wait before retrying
- Check rate limits in code

### "Failed to sync application commands"
- Discord API issue
- Bot permissions issue
- Usually resolves on retry

### "IRC client not connected"
- IRC connection lost
- Bot will attempt auto-reconnect
- Check IRC server status

