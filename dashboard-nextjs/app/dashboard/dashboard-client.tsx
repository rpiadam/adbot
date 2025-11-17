'use client'

import { useSession, signOut } from 'next-auth/react'
import { useState } from 'react'
import OverviewTab from '@/components/tabs/OverviewTab'
import FeaturesTab from '@/components/tabs/FeaturesTab'
import MonitoringTab from '@/components/tabs/MonitoringTab'
import RssTab from '@/components/tabs/RssTab'
import LogsTab from '@/components/tabs/LogsTab'
import BackupsTab from '@/components/tabs/BackupsTab'

type Tab = 'overview' | 'features' | 'monitoring' | 'rss' | 'logs' | 'backups'

export default function DashboardClient() {
  const { data: session } = useSession()
  const [activeTab, setActiveTab] = useState<Tab>('overview')

  const tabs: { id: Tab; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'features', label: 'Features' },
    { id: 'monitoring', label: 'Monitoring' },
    { id: 'rss', label: 'RSS Feeds' },
    { id: 'logs', label: 'Moderation Logs' },
    { id: 'backups', label: 'Backups' },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-primary-500 to-purple-600 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold">UpLove Dashboard</h1>
              <p className="text-primary-100 text-sm">
                {session?.user?.name || session?.user?.email}
              </p>
            </div>
            <button
              onClick={() => signOut({ callbackUrl: '/auth/signin' })}
              className="bg-white/20 hover:bg-white/30 px-4 py-2 rounded-lg transition-colors"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-white rounded-lg shadow-sm mt-6 mb-6">
          <div className="flex border-b border-gray-200">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-6 py-4 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'text-primary-600 border-b-2 border-primary-600'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          {activeTab === 'overview' && <OverviewTab />}
          {activeTab === 'features' && <FeaturesTab />}
          {activeTab === 'monitoring' && <MonitoringTab />}
          {activeTab === 'rss' && <RssTab />}
          {activeTab === 'logs' && <LogsTab />}
          {activeTab === 'backups' && <BackupsTab />}
        </div>
      </div>
    </div>
  )
}


