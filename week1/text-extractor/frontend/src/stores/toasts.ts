import { defineStore } from 'pinia'

export type ToastTone = 'success' | 'error' | 'info'

export interface Toast {
  id: number
  tone: ToastTone
  title: string
  description?: string
}

let nextId = 1

export const useToastStore = defineStore('toasts', {
  state: () => ({
    items: [] as Toast[],
  }),

  actions: {
    push(tone: ToastTone, title: string, description?: string) {
      const toast: Toast = { id: nextId++, tone, title, description }
      this.items.push(toast)
      window.setTimeout(() => this.dismiss(toast.id), tone === 'error' ? 8000 : 4500)
      return toast.id
    },

    success(title: string, description?: string) {
      return this.push('success', title, description)
    },

    error(title: string, description?: string) {
      return this.push('error', title, description)
    },

    info(title: string, description?: string) {
      return this.push('info', title, description)
    },

    dismiss(id: number) {
      this.items = this.items.filter((toast) => toast.id !== id)
    },
  },
})
