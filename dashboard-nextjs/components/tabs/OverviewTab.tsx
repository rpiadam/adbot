'use client'

import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '@/lib/api'
import { Activity, Users, Globe, Clock, AlertCircle, Wifi } from 'lucide-react'

export default function OverviewTab() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: async () => {
      const response = await dashboardApi.getStats()
      return response.data
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  if (isLoading) {
    return <div className="text-center py-8">Loading...</div>
  }

  const statCards = [
    {
      label: 'Guilds',
      value: stats?.guilds || 0,
      icon: Users,
      color: 'text-blue-600',
    },
    {
      label: 'Users',
      value: stats?.users?.toLocaleString() || '0',
      icon: Users,
      color: 'text-green-600',
    },
    {
      label: 'Latency',
      value: `${Math.round(stats?.latency || 0)}ms`,
      icon: Activity,
      color: 'text-purple-600',
    },
    {
      label: 'IRC Status',
      value: stats?.irc_connected ? 'Connected' : 'Disconnected',
      icon: Wifi,
      color: stats?.irc_connected ? 'text-green-600' : 'text-red-600',
    },
    {
      label: 'Uptime',
      value: stats?.uptime_formatted || '0s',
      icon: Clock,
      color: 'text-indigo-600',
    },
    {
      label: 'Errors',
      value: stats?.error_count || 0,
      icon: AlertCircle,
      color: 'text-red-600',
    },
  ]

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Overview</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {statCards.map((stat) => {
          const Icon = stat.icon
          return (
            <div
              key={stat.label}
              className="bg-gray-50 rounded-lg p-6 border border-gray-200"
            >
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-gray-600">{stat.label}</p>
                <Icon className={`w-5 h-5 ${stat.color}`} />
              </div>
              <p className="text-3xl font-bold text-gray-900">{stat.value}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}


