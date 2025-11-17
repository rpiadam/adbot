# UpLove Dashboard - Next.js with OAuth2

Modern Next.js dashboard for the UpLove bot with Discord OAuth2 authentication.

## Features

- ✅ **Next.js 14** with App Router
- ✅ **Discord OAuth2** authentication
- ✅ **TypeScript** for type safety
- ✅ **Tailwind CSS** for styling
- ✅ **React Query** for data fetching
- ✅ **Responsive design**
- ✅ **Real-time updates**

## Setup

### 1. Install Dependencies

```bash
npm install
# or
yarn install
# or
pnpm install
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

Edit `.env.local` with your values:

```env
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-secret-key-here
DISCORD_CLIENT_ID=your-discord-client-id
DISCORD_CLIENT_SECRET=your-discord-client-secret
API_BASE_URL=http://localhost:8000
```

### 3. Create Discord OAuth2 Application

1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Go to "OAuth2" section
4. Add redirect URI: `http://localhost:3000/api/auth/callback/discord`
5. Copy Client ID and Client Secret to `.env.local`

### 4. Generate NextAuth Secret

```bash
openssl rand -base64 32
```

Add the output to `NEXTAUTH_SECRET` in `.env.local`

### 5. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Production Deployment

### Build

```bash
npm run build
npm start
```

### Environment Variables for Production

Update these in your hosting platform:

- `NEXTAUTH_URL` - Your production URL (e.g., `https://dashboard.example.com`)
- `NEXTAUTH_SECRET` - Same secret key
- `DISCORD_CLIENT_ID` - Same Discord client ID
- `DISCORD_CLIENT_SECRET` - Same Discord client secret
- `API_BASE_URL` - Your FastAPI backend URL
- `NEXT_PUBLIC_API_BASE_URL` - Public API URL (same as API_BASE_URL)

### Update Discord OAuth2 Redirect URI

Add your production callback URL:
`https://your-domain.com/api/auth/callback/discord`

## Project Structure

```
dashboard-nextjs/
├── app/
│   ├── api/auth/[...nextauth]/  # NextAuth configuration
│   ├── auth/signin/             # Sign in page
│   ├── dashboard/               # Dashboard pages
│   └── layout.tsx               # Root layout
├── components/
│   └── tabs/                    # Dashboard tab components
├── lib/
│   └── api.ts                   # API client
└── middleware.ts                 # Auth middleware
```

## Features

- **Overview Tab**: Real-time bot statistics
- **Features Tab**: Toggle bot features
- **Monitoring Tab**: Manage monitor URLs
- **RSS Tab**: Manage RSS feeds
- **Logs Tab**: View and export moderation logs
- **Backups Tab**: Create and manage backups

## Troubleshooting

- **OAuth not working**: Check Discord redirect URI matches exactly
- **API errors**: Verify `API_BASE_URL` points to your FastAPI backend
- **Build errors**: Make sure all environment variables are set


