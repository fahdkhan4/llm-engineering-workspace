import { defineStore } from 'pinia'

import { checkHealth } from '@/services/health'

export type ConnectionState = 'unknown' | 'online' | 'offline'

const POLL_INTERVAL_MS = 30000

let timer: number | null = null

export const useHealthStore = defineStore('health', {
  state: () => ({
    status: 'unknown' as ConnectionState,
    lastCheckedAt: null as string | null,
    checking: false,
  }),

  getters: {
    isOffline: (state) => state.status === 'offline',
    label: (state) => {
      if (state.status === 'online') return 'Connected'
      if (state.status === 'offline') return 'Backend unavailable'
      return 'Checking…'
    },
  },

  actions: {
    async refresh() {
      this.checking = true
      try {
        const response = await checkHealth()
        this.status = response.status === 'ok' ? 'online' : 'offline'
      } catch {
        this.status = 'offline'
      } finally {
        this.checking = false
        this.lastCheckedAt = new Date().toISOString()
      }
    },

    startPolling() {
      if (timer !== null) return
      void this.refresh()
      timer = window.setInterval(() => void this.refresh(), POLL_INTERVAL_MS)
    },

    stopPolling() {
      if (timer === null) return
      window.clearInterval(timer)
      timer = null
    },
  },
})
