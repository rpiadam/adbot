# Deployment Guide for bot.m7iau.co.uyk

## Option 1: Next.js Dashboard (Recommended - Modern with OAuth2)

### What to Upload:
Upload the entire `dashboard-nextjs` folder to your server.

### Steps:

1. **Upload files to your server:**
   ```bash
   # Upload dashboard-nextjs folder to your server
   scp -r dashboard-nextjs user@bot.m7iau.co.uyk:/path/to/dashboard
   ```

2. **SSH into your server:**
   ```bash
   ssh user@bot.m7iau.co.uyk
   ```

3. **Install Node.js (if not installed):**
   ```bash
   # Ubuntu/Debian
   curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
   sudo apt-get install -y nodejs
   ```

4. **Navigate to dashboard folder:**
   ```bash
   cd /path/to/dashboard
   ```

5. **Install dependencies:**
   ```bash
   npm install
   ```

6. **Create `.env.local` file:**
   ```bash
   nano .env.local
   ```
   
   Add:
   ```env
   NEXTAUTH_URL=https://bot.m7iau.co.uyk
   NEXTAUTH_SECRET=your-secret-key-here
   DISCORD_CLIENT_ID=your-discord-client-id
   DISCORD_CLIENT_SECRET=your-discord-client-secret
   API_BASE_URL=http://localhost:8000
   NEXT_PUBLIC_API_BASE_URL=https://bot.m7iau.co.uyk/api
   ```

7. **Build the application:**
   ```bash
   npm run build
   ```

8. **Run with PM2 (recommended):**
   ```bash
   npm install -g pm2
   pm2 start npm --name "dashboard" -- start
   pm2 save
   pm2 startup
   ```

9. **Or run directly:**
   ```bash
   npm start
   ```

10. **Set up Nginx reverse proxy:**
   ```nginx
   server {
       listen 80;
       server_name bot.m7iau.co.uyk;

       location / {
           proxy_pass http://localhost:3000;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection 'upgrade';
           proxy_set_header Host $host;
           proxy_cache_bypass $http_upgrade;
       }
   }
   ```

---

## Option 2: Simple HTML Dashboard (Easier - Static Files)

### What to Upload:
Upload the `dashboard` folder contents (dashboard.html, login.html, static/)

### Steps:

1. **Upload files:**
   ```bash
   # Upload dashboard files to web root
   scp dashboard/* user@bot.m7iau.co.uyk:/var/www/html/
   ```

2. **Set up Nginx:**
   ```nginx
   server {
       listen 80;
       server_name bot.m7iau.co.uyk;
       root /var/www/html;
       index index.html login.html;

       location / {
           try_files $uri $uri/ =404;
       }

       # Proxy API requests to FastAPI backend
       location /api {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

**Note:** This option requires your FastAPI backend to be running on port 8000 and accessible.

---

## Which Should You Use?

- **Next.js Dashboard**: Better UI, OAuth2, modern React, requires Node.js
- **HTML Dashboard**: Simpler, static files, works with just Nginx

## Quick Setup Checklist:

### For Next.js:
- [ ] Upload `dashboard-nextjs` folder
- [ ] Install Node.js 20+
- [ ] Run `npm install`
- [ ] Create `.env.local` with Discord OAuth credentials
- [ ] Run `npm run build`
- [ ] Start with PM2 or systemd
- [ ] Configure Nginx reverse proxy

### For HTML:
- [ ] Upload `dashboard` folder files
- [ ] Configure Nginx to serve files
- [ ] Ensure FastAPI backend is running
- [ ] Configure API proxy in Nginx

## Discord OAuth2 Setup (for Next.js):

1. Go to https://discord.com/developers/applications
2. Create new application
3. Go to OAuth2 section
4. Add redirect URI: `https://bot.m7iau.co.uyk/api/auth/callback/discord`
5. Copy Client ID and Secret to `.env.local`


