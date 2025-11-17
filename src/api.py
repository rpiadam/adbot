from datetime import timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, Header, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from jinja2 import Template
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import Settings
from .dashboard import authenticate_user, create_access_token, verify_token
from .models import FootballEvent
from .relay import RelayCoordinator

security = HTTPBearer(auto_error=False)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


def create_app(coordinator: RelayCoordinator, settings: Settings) -> FastAPI:
    app = FastAPI(
        title="UpLove Dashboard",
        version="1.0.0",
        description="Community Operations Suite - Discord/IRC Bridge Bot",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Setup rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # Setup static files
    dashboard_dir = Path(__file__).parent.parent / "dashboard"
    dashboard_dir.mkdir(exist_ok=True)
    
    static_dir = dashboard_dir / "static"
    static_dir.mkdir(exist_ok=True)
    
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
        """Verify JWT token and return user info."""
        if credentials is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        token = credentials.credentials
        payload = verify_token(token, settings.dashboard_secret_key)
        if payload is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return payload

    @app.get("/", response_class=HTMLResponse)
    async def dashboard_root():
        """Serve the dashboard login page."""
        login_html = (dashboard_dir / "login.html")
        if login_html.exists():
            return FileResponse(login_html)
        return HTMLResponse(content=_get_login_html())

    @app.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_page(request: Request):
        """Serve the main dashboard page."""
        # Check for token in query or header
        token = request.query_params.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "")
        if token:
            payload = verify_token(token, settings.dashboard_secret_key)
            if payload is None:
                return HTMLResponse(content="Invalid token", status_code=401)
        else:
            # Return login redirect if no token
            return HTMLResponse(content='<script>window.location.href="/";</script>', status_code=401)
        
        dashboard_html = (dashboard_dir / "dashboard.html")
        if dashboard_html.exists():
            return FileResponse(dashboard_html)
        return HTMLResponse(content=_get_dashboard_html())

    @app.post("/api/auth/login")
    @limiter.limit("5/minute")
    async def login(request: Request, username: str = Form(...), password: str = Form(...)):
        """Authenticate user and return JWT token."""
        if not authenticate_user(username, password, settings):
            raise HTTPException(status_code=401, detail="Incorrect username or password")
        
        access_token = create_access_token(
            data={"sub": username},
            secret_key=settings.dashboard_secret_key,
            expires_delta=timedelta(hours=24)
        )
        return {"access_token": access_token, "token_type": "bearer"}

    @app.get("/api/features")
    @limiter.limit("30/minute")
    async def get_features(request: Request, user: dict = Depends(get_current_user)):
        """Get all feature flags."""
        flags = await coordinator.config_store.get_feature_flags()
        return {"features": flags}

    @app.post("/api/features/{feature_name}")
    @limiter.limit("10/minute")
    async def toggle_feature(
        request: Request,
        feature_name: str,
        enabled: str = Form(...),
        user: dict = Depends(get_current_user)
    ):
        """Toggle a feature flag."""
        enabled_bool = enabled.lower() in ("true", "1", "yes", "on")
        success = await coordinator.config_store.set_feature_flag(feature_name, enabled_bool)
        if not success:
            raise HTTPException(status_code=404, detail="Feature not found")
        return {"feature": feature_name, "enabled": enabled_bool, "success": True}

    @app.get("/api/stats")
    @limiter.limit("60/minute")
    async def get_stats(request: Request, user: dict = Depends(get_current_user)):
        """Get bot statistics."""
        bot = coordinator.discord_bot
        health = coordinator.get_health_stats()
        return {
            "guilds": len(bot.guilds),
            "users": sum(g.member_count or 0 for g in bot.guilds),
            "latency": bot.latency * 1000 if bot.latency else 0.0,
            "irc_connected": any(client.connected for client in coordinator.irc_clients) if coordinator.irc_clients else False,
            "irc_networks": [
                {
                    "server": client.network_config.server,
                    "port": client.network_config.port,
                    "channel": client.network_config.channel,
                    "connected": client.connected,
                }
                for client in coordinator.irc_clients
            ],
            "uptime_seconds": health["uptime_seconds"],
            "uptime_formatted": health["uptime_formatted"],
            "error_count": health["error_count"],
            "discord_connected": health["discord_connected"],
        }

    @app.get("/api/health")
    @limiter.limit("60/minute")
    async def get_health(request: Request, user: dict = Depends(get_current_user)):
        """Get detailed system health information."""
        health = coordinator.get_health_stats()
        bot = coordinator.discord_bot
        return {
            **health,
            "guilds": len(bot.guilds),
            "users": sum(g.member_count or 0 for g in bot.guilds),
            "latency_ms": bot.latency * 1000 if bot.latency else 0.0,
        }

    @app.get("/api/monitor")
    @limiter.limit("30/minute")
    async def get_monitor_urls(request: Request, user: dict = Depends(get_current_user)):
        """Get all monitor URLs."""
        urls = await coordinator.config_store.list_monitor_urls()
        return {"urls": urls}

    @app.post("/api/monitor")
    @limiter.limit("10/minute")
    async def add_monitor_url(request: Request, url: str = Form(...), user: dict = Depends(get_current_user)):
        """Add a monitor URL."""
        success = await coordinator.config_store.add_monitor_url(url)
        if not success:
            raise HTTPException(status_code=400, detail="URL already exists or is invalid")
        return {"url": url, "success": True}

    @app.delete("/api/monitor")
    @limiter.limit("10/minute")
    async def remove_monitor_url(request: Request, url: str, user: dict = Depends(get_current_user)):
        """Remove a monitor URL."""
        success = await coordinator.config_store.remove_monitor_url(url)
        if not success:
            raise HTTPException(status_code=404, detail="URL not found")
        return {"url": url, "success": True}

    @app.get("/api/rss")
    @limiter.limit("30/minute")
    async def get_rss_feeds(request: Request, user: dict = Depends(get_current_user)):
        """Get all RSS feeds."""
        feeds = await coordinator.config_store.list_rss_feeds()
        return {"feeds": feeds}

    @app.post("/api/rss")
    @limiter.limit("10/minute")
    async def add_rss_feed(request: Request, url: str = Form(...), user: dict = Depends(get_current_user)):
        """Add an RSS feed."""
        success = await coordinator.config_store.add_rss_feed(url)
        if not success:
            raise HTTPException(status_code=400, detail="Feed already exists or is invalid")
        return {"url": url, "success": True}

    @app.delete("/api/rss")
    @limiter.limit("10/minute")
    async def remove_rss_feed(request: Request, url: str, user: dict = Depends(get_current_user)):
        """Remove an RSS feed."""
        success = await coordinator.config_store.remove_rss_feed(url)
        if not success:
            raise HTTPException(status_code=404, detail="Feed not found")
        return {"url": url, "success": True}

    @app.get("/api/logs")
    @limiter.limit("30/minute")
    async def get_moderation_logs(request: Request, limit: int = 100, user: dict = Depends(get_current_user)):
        """Get recent moderation logs."""
        if limit > 500:
            limit = 500  # Cap at 500
        logs = await coordinator.config_store.get_moderation_logs(limit=limit)
        return {"logs": logs}

    @app.get("/api/logs/export")
    @limiter.limit("10/minute")
    async def export_logs(request: Request, format: str = "json", user: dict = Depends(get_current_user)):
        """Export moderation logs in JSON or CSV format."""
        from fastapi.responses import Response
        from src.utils import sanitize_filename
        import csv
        import io
        from datetime import datetime
        
        try:
            logs = await coordinator.config_store.get_moderation_logs(limit=1000)
            
            if format.lower() == "csv":
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=["timestamp", "guild_id", "guild_name", "message"])
                writer.writeheader()
                for log in logs:
                    writer.writerow({
                        "timestamp": log.get("timestamp", ""),
                        "guild_id": log.get("guild_id", ""),
                        "guild_name": log.get("guild_name", ""),
                        "message": log.get("message", ""),
                    })
                filename = sanitize_filename(f"moderation_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                return Response(
                    content=output.getvalue(),
                    media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
            else:
                import json
                filename = sanitize_filename(f"moderation_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                return Response(
                    content=json.dumps(logs, indent=2),
                    media_type="application/json",
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )
        except Exception as e:
            logger.error(f"Failed to export logs: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to export logs: {str(e)}")

    @app.post("/api/backup")
    @limiter.limit("5/hour")
    async def create_backup(request: Request, user: dict = Depends(get_current_user)):
        """Create a backup of configuration and data."""
        import subprocess
        try:
            result = subprocess.run(
                ["python", "scripts/backup_config.py", "backup"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return {"success": True, "message": "Backup created successfully", "output": result.stdout}
            else:
                raise HTTPException(status_code=500, detail=f"Backup failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=500, detail="Backup operation timed out")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")

    @app.get("/api/backups")
    @limiter.limit("10/minute")
    async def list_backups(request: Request, user: dict = Depends(get_current_user)):
        """List all available backups."""
        from pathlib import Path
        import json
        
        backup_dir = Path("backups")
        if not backup_dir.exists():
            return {"backups": []}
        
        backups = []
        for backup_path in sorted(backup_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if backup_path.is_dir():
                manifest_path = backup_path / "manifest.json"
                if manifest_path.exists():
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                    backups.append({
                        "name": backup_path.name,
                        "timestamp": manifest.get("timestamp", ""),
                        "files": manifest.get("files", [])
                    })
        
        return {"backups": backups}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/football-nation")
    async def football_webhook(
        payload: FootballEvent,
        x_webhook_secret: Optional[str] = Header(None, convert_underscores=False),
    ) -> dict[str, str]:
        expected_secret = settings.football_webhook_secret
        if expected_secret and expected_secret != x_webhook_secret:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

        summary = payload.to_summary(settings)
        await coordinator.announce_football_event(summary)
        return {"status": "accepted"}

    return app


def _get_login_html() -> str:
    """Return the login page HTML."""
    return """<!DOCTYPE html>
<html>
<head>
    <title>UpLove Dashboard - Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 20px;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            width: 100%;
            max-width: 400px;
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            color: #333;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #555;
            font-weight: 500;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        button {
            width: 100%;
            padding: 12px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
            font-weight: 600;
        }
        button:hover {
            background: #5568d3;
        }
        .error {
            color: #e74c3c;
            margin-top: 10px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>UpLove Dashboard</h1>
        <form id="loginForm">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Login</button>
            <div id="error" class="error" style="display: none;"></div>
        </form>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                body: formData
            });
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('token', data.access_token);
                window.location.href = '/dashboard';
            } else {
                document.getElementById('error').textContent = 'Invalid username or password';
                document.getElementById('error').style.display = 'block';
            }
        });
    </script>
</body>
</html>"""


def _get_dashboard_html() -> str:
    """Return the dashboard page HTML."""
    return """<!DOCTYPE html>
<html>
<head>
    <title>UpLove Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header h1 {
            margin-bottom: 10px;
        }
        .container {
            max-width: 1200px;
            margin: 30px auto;
            padding: 0 20px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .stat-card h3 {
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
        }
        .stat-card .value {
            font-size: 32px;
            font-weight: bold;
            color: #333;
        }
        .features {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .features h2 {
            margin-bottom: 20px;
            color: #333;
        }
        .feature-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            border-bottom: 1px solid #eee;
        }
        .feature-item:last-child {
            border-bottom: none;
        }
        .toggle {
            position: relative;
            width: 60px;
            height: 30px;
        }
        .toggle input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
            border-radius: 30px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 22px;
            width: 22px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: #667eea;
        }
        input:checked + .slider:before {
            transform: translateX(30px);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>UpLove Dashboard</h1>
        <p>Bot Management & Control</p>
    </div>
    <div class="container">
        <div class="stats" id="stats">
            <div class="stat-card">
                <h3>Guilds</h3>
                <div class="value" id="guilds">-</div>
            </div>
            <div class="stat-card">
                <h3>Users</h3>
                <div class="value" id="users">-</div>
            </div>
            <div class="stat-card">
                <h3>Latency</h3>
                <div class="value" id="latency">-</div>
            </div>
            <div class="stat-card">
                <h3>IRC Status</h3>
                <div class="value" id="irc">-</div>
            </div>
        </div>
        <div class="features">
            <h2>Feature Toggles</h2>
            <div id="features"></div>
        </div>
    </div>
    <script>
        const token = localStorage.getItem('token');
        if (!token) {
            window.location.href = '/';
        }
        
        const headers = {
            'Authorization': `Bearer ${token}`
        };
        
        async function loadStats() {
            const response = await fetch('/api/stats', { headers });
            if (response.ok) {
                const data = await response.json();
                document.getElementById('guilds').textContent = data.guilds;
                document.getElementById('users').textContent = data.users.toLocaleString();
                document.getElementById('latency').textContent = Math.round(data.latency) + 'ms';
                document.getElementById('irc').textContent = data.irc_connected ? 'Connected' : 'Disconnected';
            }
        }
        
        async function loadFeatures() {
            const response = await fetch('/api/features', { headers });
            if (response.ok) {
                const data = await response.json();
                const container = document.getElementById('features');
                container.innerHTML = '';
                for (const [feature, enabled] of Object.entries(data.features)) {
                    const div = document.createElement('div');
                    div.className = 'feature-item';
                    div.innerHTML = `
                        <span style="text-transform: capitalize; font-weight: 500;">${feature}</span>
                        <label class="toggle">
                            <input type="checkbox" ${enabled ? 'checked' : ''} onchange="toggleFeature('${feature}', this.checked)">
                            <span class="slider"></span>
                        </label>
                    `;
                    container.appendChild(div);
                }
            }
        }
        
        async function toggleFeature(feature, enabled) {
            const formData = new FormData();
            formData.append('enabled', enabled);
            const response = await fetch(`/api/features/${feature}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });
            if (!response.ok) {
                alert('Failed to toggle feature');
                loadFeatures();
            }
        }
        
        loadStats();
        loadFeatures();
        setInterval(loadStats, 5000);
    </script>
</body>
</html>"""


