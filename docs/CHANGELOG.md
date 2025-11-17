# Changelog

All notable changes to the UpLove bot project.

## [Unreleased]

### Added
- **Warning/Strike Tracking System**: Persistent warning tracking for users
  - `/warn` command now tracks and displays warning count
  - `/warnings` command to view warning history
  - `/clearwarnings` command to clear all warnings
  - Warnings stored with moderator, reason, and timestamp
- **Dashboard Export Features**: Export moderation logs
  - Export logs as JSON or CSV
  - Download buttons in dashboard
- **Backup Management UI**: Web interface for backups
  - Create backups from dashboard
  - List and view backup metadata
- **Comprehensive Test Suite**:
  - API endpoint tests
  - Moderation feature tests
  - Integration tests for storage and configuration
  - Utility function tests
- **Utility Functions Module**: Reusable helper functions
  - Uptime/bytes formatting
  - Filename sanitization
  - Text truncation and chunking
  - Duration parsing and formatting
  - URL validation
  - Markdown escaping
  - Safe type conversions
- **Enhanced Error Handling**:
  - Better error messages in API endpoints
  - URL validation for monitor URLs and RSS feeds
  - Improved export functionality with timestamped filenames
- **Welcome Moderation**: Auto-ban protection against raids
  - Account age checking (configurable minimum days)
  - Join rate limiting (configurable threshold)
  - Automatic logging of all actions
- **Web Dashboard**: Comprehensive management interface
  - Real-time bot statistics
  - Feature flag toggles
  - Monitor URL management
  - RSS feed management
  - Moderation logs viewing
  - System health monitoring
- **API Rate Limiting**: Protection against abuse
  - Login: 5 requests/minute
  - Feature toggles: 10 requests/minute
  - Stats/logs: 30-60 requests/minute
- **API Documentation**: OpenAPI/Swagger docs at `/docs`
- **Docker Support**: Complete containerization
  - Dockerfile for building images
  - docker-compose.yml for easy deployment
  - .dockerignore for optimized builds
- **Backup/Restore**: Configuration backup system
  - Command-line backup utility
  - API endpoints for backup management
  - Timestamped backups with manifests
- **System Health Tracking**:
  - Uptime monitoring
  - Error counting
  - Reconnection tracking
  - Message rate statistics
  - Health status indicators
- **Error Recovery**:
  - Auto-reconnect for IRC on unexpected disconnects
  - Discord reconnection tracking
  - Error recording and reporting
- **Environment Validation**: Startup configuration checks
  - Validates required variables
  - Checks port ranges
  - Validates moderation settings
  - Warns about insecure defaults
- **Enhanced Logging**:
  - File-based logging with rotation
  - 10MB per file, 5 backups
  - Structured log format
- **CI/CD Pipeline**:
  - GitHub Actions workflows
  - Automated testing (Python 3.10, 3.11, 3.12)
  - Code quality checks (flake8, black, isort)
  - Docker build automation
- **Security Improvements**:
  - Bcrypt password hashing support
  - Password hash generation script
  - Rate limiting on all API endpoints
- **Documentation**:
  - Deployment guide
  - Troubleshooting guide
  - Enhanced README

### Changed
- Dashboard password authentication now supports bcrypt hashes
- Moderation logs are now stored persistently for dashboard viewing
- Health checks include more detailed metrics
- Error handling improved throughout

### Fixed
- Token handling in dashboard (now reads from URL params)
- Improved error messages for configuration issues

## Previous Versions

See git history for earlier changes.

