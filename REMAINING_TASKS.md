# Remaining Tasks for Ruby Bot

## ✅ What's Complete (Already Pushed)

- ✅ Core project structure (`lib/ruby_bot/`)
- ✅ Configuration system (`config.rb`)
- ✅ Storage system (`storage.rb`)
- ✅ Discord/IRC relay coordinator (`relay.rb`)
- ✅ Basic API server (`api.rb`)
- ✅ Main entry point (`bin/ruby_bot`)
- ✅ Documentation (README_RUBY.md, CHOOSING_LANGUAGE.md)
- ✅ Gemfile with dependencies
- ✅ All files pushed to GitHub

## 🔴 Critical - Must Have for Basic Functionality

### 1. **Testing & Bug Fixes**
   - [ ] Test Discord connection
   - [ ] Test IRC connection
   - [ ] Test message relay (Discord → IRC and IRC → Discord)
   - [ ] Fix any syntax errors or runtime issues
   - [ ] Test configuration loading from `.env`

### 2. **Dashboard Authentication** 
   Currently missing - API endpoints are open!
   - [ ] Add JWT gem to Gemfile (`gem 'jwt'`)
   - [ ] Implement login endpoint with password verification
   - [ ] Add JWT token generation/verification
   - [ ] Protect API routes with authentication middleware
   - [ ] Match Python's dashboard authentication system

### 3. **Better Error Handling**
   - [ ] Improve IRC connection error handling
   - [ ] Add reconnection logic for IRC
   - [ ] Handle Discord reconnection gracefully
   - [ ] Add proper logging configuration (file rotation like Python)

## 🟡 High Priority Features (Python Has, Ruby Doesn't)

### 4. **Discord Slash Commands**
   Python has extensive slash commands, Ruby has none yet:
   - [ ] `/relaystatus` - Show bridge status
   - [ ] `/relayping` - Test connectivity
   - [ ] `/help` - Help system with categories
   - [ ] Basic command registration system

### 5. **Welcome System**
   - [ ] Welcome new members in designated channel
   - [ ] Send DM welcome messages
   - [ ] Welcome moderation (auto-ban protection)

### 6. **Monitoring Service**
   - [ ] URL health check background worker
   - [ ] Post alerts to Discord when URLs go down/up
   - [ ] Store monitoring history

### 7. **RSS Feed Polling**
   - [ ] Poll RSS feeds at configured intervals
   - [ ] Post new entries to Discord
   - [ ] Track already-posted entries

## 🟢 Medium Priority Features

### 8. **Moderation Commands**
   Python has full moderation toolkit:
   - [ ] `/purge` - Delete messages
   - [ ] `/kick`, `/ban` - User management
   - [ ] `/timeout` - Temporary mute
   - [ ] `/warn` - Warning system
   - [ ] Profanity filtering
   - [ ] Join/leave logging

### 9. **Games System**
   - [ ] `/coinflip`, `/roll`, `/pick`
   - [ ] `/slots`, `/gamble`
   - [ ] `/hangman`, `/tictactoe`, `/trivia`
   - [ ] Credit system (already in storage)

### 10. **Advanced Monitoring**
   - [ ] TLS expiry checking
   - [ ] Keyword assertions
   - [ ] Status code validation
   - [ ] Historical samples/stats

## 🔵 Lower Priority / Nice to Have

### 11. **Music Playback**
   - [ ] Voice channel connection
   - [ ] YouTube/audio playback
   - [ ] Queue management
   - [ ] Now-playing embeds

### 12. **Admin Utilities**
   - [ ] `/relayannounce` - Announcements
   - [ ] `/relaystats` - Statistics
   - [ ] `/relaydebug` - Diagnostics
   - [ ] `/relayreload` - Reload config

### 13. **Infrastructure**
   - [ ] Docker support (Dockerfile for Ruby)
   - [ ] docker-compose.yml integration
   - [ ] Better logging (rotating file logs)
   - [ ] Backup/restore scripts

## 📝 Code Quality Improvements

- [ ] Add RSpec tests for core functionality
- [ ] Fix any Rubocop style violations
- [ ] Add better documentation/comments
- [ ] Improve thread safety where needed
- [ ] Add proper exception handling everywhere

## 🐛 Known Issues to Fix

1. **IRC Bot Connection**: May need refinement for better reliability
2. **Webhook Creation**: Discord webhook setup might fail silently
3. **Thread Safety**: Verify all operations are thread-safe
4. **API Authentication**: Currently unprotected
5. **Logging**: No file-based logging yet (only stdout)

## 📊 Feature Comparison

| Feature | Python | Ruby | Status |
|---------|--------|------|--------|
| Core Relay | ✅ | ✅ | Complete |
| API Server | ✅ | ✅ | Complete (needs auth) |
| Dashboard | ✅ | ✅ | Basic (needs auth) |
| Slash Commands | ✅ 15+ | ❌ 0 | Not started |
| Welcome System | ✅ | ❌ | Not started |
| Monitoring | ✅ | ❌ | Not started |
| RSS | ✅ | ❌ | Not started |
| Moderation | ✅ | ❌ | Not started |
| Games | ✅ | ❌ | Not started |
| Music | ✅ | ❌ | Not started |
| Docker | ✅ | ❌ | Not started |

## 🎯 Recommended Next Steps (Priority Order)

1. **Test & Fix Core** (Do first!)
   - Install dependencies: `bundle install`
   - Test config loading
   - Test Discord connection
   - Test IRC connection
   - Test message relay

2. **Add Dashboard Auth** (Security!)
   - Add JWT gem
   - Implement login
   - Protect API routes

3. **Add Basic Slash Commands**
   - `/relaystatus`
   - `/relayping`
   - `/help`

4. **Add Background Services**
   - Monitoring worker
   - RSS polling worker

5. **Expand Features**
   - Welcome system
   - Moderation commands
   - Games system

## 📦 Files Still Needed

If adding more features, you may need:
- `lib/ruby_bot/commands/` - Discord command handlers
- `lib/ruby_bot/workers/` - Background workers (monitoring, RSS)
- `lib/ruby_bot/services/` - Service classes (welcome, moderation)
- `spec/lib/ruby_bot/` - Test files

## 💡 Quick Wins

These could be done quickly:
1. Add JWT authentication (2-3 hours)
2. Add `/relaystatus` command (1 hour)
3. Add file-based logging (1 hour)
4. Fix any connection issues (as found)

---

**Current Status**: Ruby bot has solid foundation, needs testing and feature expansion to match Python version.

