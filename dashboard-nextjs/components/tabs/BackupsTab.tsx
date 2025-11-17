'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dashboardApi } from '@/lib/api'
import { useState } from 'react'
import { RefreshCw, Plus, Database } from 'lucide-react'

export default function BackupsTab() {
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['backups'],
    queryFn: async () => {
      const response = await dashboardApi.getBackups()
      return response.data.backups
    },
  })

  const createMutation = useMutation({
    mutationFn: () => dashboardApi.createBackup(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backups'] })
      setMessage({ text: 'Backup created successfully', type: 'success' })
      setTimeout(() => setMessage(null), 3000)
    },
    onError: () => {
      setMessage({ text: 'Failed to create backup', type: 'error' })
      setTimeout(() => setMessage(null), 3000)
    },
  })

  if (isLoading) {
    return <div className="text-center py-8">Loading...</div>
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Backup Management</h2>
        <div className="flex gap-2">
          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ['backups'] })}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            {createMutation.isPending ? 'Creating...' : 'Create Backup'}
          </button>
        </div>
      </div>

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

      <div className="space-y-2">
        {data && data.length > 0 ? (
          data.map((backup: any) => (
            <div
              key={backup.name}
              className="p-4 bg-gray-50 rounded-lg border border-gray-200"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <Database className="w-5 h-5 text-primary-600 mt-1" />
                  <div>
                    <h3 className="font-semibold text-gray-900">{backup.name}</h3>
                    <p className="text-sm text-gray-600 mt-1">
                      {backup.timestamp || 'Unknown date'}
                    </p>
                    <p className="text-sm text-gray-500 mt-1">
                      {backup.files?.length || 0} files
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="text-center py-8 text-gray-500">
            No backups available
          </div>
        )}
      </div>
    </div>
  )
}


