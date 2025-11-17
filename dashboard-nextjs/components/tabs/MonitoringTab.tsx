'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dashboardApi } from '@/lib/api'
import { useState } from 'react'
import { Trash2, Plus } from 'lucide-react'

export default function MonitoringTab() {
  const queryClient = useQueryClient()
  const [url, setUrl] = useState('')
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['monitor-urls'],
    queryFn: async () => {
      const response = await dashboardApi.getMonitorUrls()
      return response.data.urls
    },
  })

  const addMutation = useMutation({
    mutationFn: (url: string) => dashboardApi.addMonitorUrl(url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitor-urls'] })
      setUrl('')
      setMessage({ text: 'Monitor URL added successfully', type: 'success' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: () => {
      setMessage({ text: 'Failed to add URL', type: 'error' })
      setTimeout(() => setMessage(null), 3000)
    },
  })

  const removeMutation = useMutation({
    mutationFn: (url: string) => dashboardApi.removeMonitorUrl(url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['monitor-urls'] })
      setMessage({ text: 'Monitor URL removed', type: 'success' })
      setTimeout(() => setMessage(null), 3000)
    },
  })

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault()
    if (url.trim()) {
      addMutation.mutate(url.trim())
    }
  }

  if (isLoading) {
    return <div className="text-center py-8">Loading...</div>
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Monitor URLs</h2>

      {message && (
        <div
          className={`mb-4 p-4 rounded-lg ${
            message.type === 'success'
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      <form onSubmit={handleAdd} className="mb-6 flex gap-2">
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com"
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          required
        />
        <button
          type="submit"
          className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          Add URL
        </button>
      </form>

      <div className="space-y-2">
        {data && data.length > 0 ? (
          data.map((url: string) => (
            <div
              key={url}
              className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200"
            >
              <span className="text-gray-900">{url}</span>
              <button
                onClick={() => {
                  if (confirm(`Remove ${url}?`)) {
                    removeMutation.mutate(url)
                  }
                }}
                className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))
        ) : (
          <div className="text-center py-8 text-gray-500">
            No monitor URLs configured
          </div>
        )}
      </div>
    </div>
  )
}


