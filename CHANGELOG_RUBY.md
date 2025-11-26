# Ruby Bot Changelog

## [Unreleased]

### Added
- ✅ **Dashboard Authentication**: JWT-based authentication for API endpoints
  - Added `lib/ruby_bot/auth.rb` module with JWT token generation/verification
  - Supports both bcrypt-hashed and plain text passwords (backwards compatible)
  - Login endpoint: `POST /api/auth/login`
  - Protected API routes require Bearer token authentication
  
- ✅ **Discord Slash Commands**: Basic command system
  - Added `lib/ruby_bot/commands.rb` module
  - `/relaystatus` - Show Discord ↔ IRC bridge status
  - `/relayping` - Measure Discord latency

- ✅ **Configuration**: Dashboard settings
  - Added `dashboard_username`, `dashboard_password`, `dashboard_secret_key` to config
  - Uses same `.env` variables as Python version

### Changed
- Updated `Gemfile` to include `jwt` gem
- API routes now protected by authentication (except `/api/health`)
- Updated `lib/ruby_bot.rb` to require auth module

### Security
- API endpoints now require JWT authentication
- Supports bcrypt password hashing
- Token expiration (24 hours by default)

---

## Previous Releases

### Initial Release
- Core Discord/IRC relay functionality
- Basic API server
- Configuration and storage systems
- Multi-network IRC support


