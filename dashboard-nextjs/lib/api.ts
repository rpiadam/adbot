import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add auth token to requests
export const setAuthToken = (token: string) => {
  api.defaults.headers.common['Authorization'] = `Bearer ${token}`
}

export const removeAuthToken = () => {
  delete api.defaults.headers.common['Authorization']
}

// API endpoints
export const dashboardApi = {
  // Stats
  getStats: () => api.get('/api/stats'),
  getHealth: () => api.get('/api/health'),

  // Features
  getFeatures: () => api.get('/api/features'),
  toggleFeature: (feature: string, enabled: boolean) =>
    api.post(`/api/features/${feature}`, { enabled }),

  // Monitor URLs
  getMonitorUrls: () => api.get('/api/monitor'),
  addMonitorUrl: (url: string) => api.post('/api/monitor', { url }),
  removeMonitorUrl: (url: string) => api.delete(`/api/monitor?url=${encodeURIComponent(url)}`),

  // RSS Feeds
  getRssFeeds: () => api.get('/api/rss'),
  addRssFeed: (url: string) => api.post('/api/rss', { url }),
  removeRssFeed: (url: string) => api.delete(`/api/rss?url=${encodeURIComponent(url)}`),

  // Logs
  getLogs: (limit: number = 100) => api.get(`/api/logs?limit=${limit}`),
  exportLogs: (format: 'json' | 'csv') => api.get(`/api/logs/export?format=${format}`, { responseType: 'blob' }),

  // Backups
  createBackup: () => api.post('/api/backup'),
  getBackups: () => api.get('/api/backups'),
}


