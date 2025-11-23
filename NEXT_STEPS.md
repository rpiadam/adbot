# Next Steps for Ruby Bot

Here's what you can do next to complete and improve the Ruby bot implementation:

## ✅ Completed

- [x] Core project structure
- [x] Configuration system
- [x] Storage system
- [x] Discord/IRC relay coordinator
- [x] Basic API server
- [x] Main entry point
- [x] Documentation

## 🔧 Immediate Next Steps

### 1. **Test Basic Setup**
   ```bash
   # Install dependencies
   bundle install
   
   # Check Ruby version (should be 3.0+)
   ruby --version
   
   # Verify syntax
   ruby -c lib/ruby_bot.rb
   ```

### 2. **Add Dashboard Authentication**
   The Ruby API currently lacks authentication. Add:
   - JWT token generation/verification (using `jwt` gem)
   - Login endpoint with password hashing (using `bcrypt`)
   - Protected routes that require authentication
   - Session management

### 3. **Fix Minor Issues**
   - Remove duplicate `httparty` dependency in Gemfile (already done)
   - Improve error handling in IRC connection logic
   - Add better logging configuration
   - Handle IRC reconnection more gracefully

### 4. **Add Discord Slash Commands**
   Implement basic commands from Python version:
   - `/relaystatus` - Show bridge status
   - `/relayping` - Ping test
   - Basic help command

## 📋 Feature Parity Checklist

To match the Python version, consider adding:

### High Priority
- [ ] Dashboard authentication (JWT-based)
- [ ] Discord slash commands
- [ ] Welcome system (new member greetings)
- [ ] Monitoring service (URL health checks)
- [ ] RSS feed polling

### Medium Priority
- [ ] Moderation commands (kick, ban, timeout, etc.)
- [ ] Games system (coinflip, dice, slots, etc.)
- [ ] Help system with categories
- [ ] Feature flag enforcement in commands

### Lower Priority (can be added later)
- [ ] Music playback
- [ ] Advanced monitoring (TLS expiry, keyword checks)
- [ ] Backup/restore functionality
- [ ] Admin utilities

## 🧪 Testing Strategy

1. **Unit Tests** (using RSpec):
   ```bash
   # Create test structure
   mkdir -p spec/lib/ruby_bot
   
   # Write tests for:
   # - Config loading/validation
   # - Storage operations
   # - API endpoints
   ```

2. **Integration Testing**:
   - Test Discord connection
   - Test IRC connection
   - Test message relay
   - Test API endpoints

## 🔨 Quick Fixes Needed

1. **Logger Configuration**: Set up proper log rotation (like Python version)
2. **Error Handling**: Add try-catch blocks where missing
3. **Webhook Handling**: Improve Discord webhook creation/usage
4. **Thread Safety**: Verify all storage operations are thread-safe

## 📚 Recommended Next Actions

### Option A: Test & Fix Core (Recommended First)
Focus on making the basic relay work reliably:
```bash
# 1. Test basic connectivity
# 2. Fix any connection issues
# 3. Add proper error handling
# 4. Test message relay
```

### Option B: Add Dashboard Auth
Make the dashboard secure:
```bash
# 1. Add jwt gem to Gemfile
# 2. Implement login endpoint
# 3. Add token verification middleware
# 4. Protect API routes
```

### Option C: Add Discord Commands
Start adding functionality:
```bash
# 1. Implement slash command handlers
# 2. Add /relaystatus command
# 3. Add basic help command
# 4. Register commands with Discord
```

## 🐛 Known Issues to Address

1. **IRC Bot**: The Cinch bot connection logic may need refinement
2. **Webhook**: Discord webhook creation might fail silently
3. **Threading**: IRC bots run in threads - need to verify thread safety
4. **API Server**: Currently runs in same process - might want separate process

## 💡 Suggestions

1. **Start Small**: Get basic relay working first, then add features incrementally
2. **Share Data**: Both bots can use same `data/config_state.json` - test switching between them
3. **Logging**: Set up file-based logging with rotation (similar to Python version)
4. **Docker**: Consider adding Ruby bot to docker-compose.yml

## 📝 Code Improvements

1. Add `require` statements for all dependencies
2. Use proper exception handling (rescue StandardError)
3. Add type hints/comments for better documentation
4. Follow Ruby style guide (run `rubocop`)

## 🚀 Quick Start Testing

To test the Ruby bot right now:

```bash
# 1. Ensure .env file exists and is configured
cp example.env .env
# Edit .env with your tokens

# 2. Install gems
bundle install

# 3. Test configuration loading
ruby -r './lib/ruby_bot' -e "puts RubyBot::Config.new.inspect"

# 4. Run the bot (when ready)
./bin/ruby_bot
```

---

**Recommended Order:**
1. Test basic setup & fix syntax errors
2. Add dashboard authentication
3. Test Discord/IRC connections
4. Add basic slash commands
5. Implement monitoring/RSS features
6. Add remaining features as needed

