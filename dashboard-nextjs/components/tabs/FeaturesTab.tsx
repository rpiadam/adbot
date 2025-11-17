'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dashboardApi } from '@/lib/api'
import { Toggle } from '@/components/ui/Toggle'

export default function FeaturesTab() {
  const queryClient = useQueryClient()

  const { data: features, isLoading } = useQuery({
    queryKey: ['features'],
    queryFn: async () => {
      const response = await dashboardApi.getFeatures()
      return response.data.features
    },
  })

  const toggleMutation = useMutation({
    mutationFn: async ({ feature, enabled }: { feature: string; enabled: boolean }) => {
      const formData = new FormData()
      formData.append('enabled', enabled.toString())
      return dashboardApi.toggleFeature(feature, enabled)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['features'] })
    },
  })

  if (isLoading) {
    return <div className="text-center py-8">Loading...</div>
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Feature Toggles</h2>
      <div className="space-y-4">
        {features &&
          Object.entries(features).map(([feature, enabled]) => (
            <div
              key={feature}
              className="flex items-center justify-between p-4 bg-gray-50 rounded-lg border border-gray-200"
            >
              <div>
                <h3 className="font-semibold text-gray-900 capitalize">{feature}</h3>
                <p className="text-sm text-gray-600">
                  {enabled ? 'Enabled' : 'Disabled'}
                </p>
              </div>
              <Toggle
                enabled={enabled as boolean}
                onToggle={(newState) =>
                  toggleMutation.mutate({ feature, enabled: newState })
                }
              />
            </div>
          ))}
      </div>
    </div>
  )
}


