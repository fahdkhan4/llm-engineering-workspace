import { defineStore } from 'pinia'

import { askQuestion, askQuestionStream } from '@/services/qa'
import { ApiError } from '@/services/http'
import type { ChatMessage, ChatThread } from '@/types/chat'
import { truncate } from '@/utils/format'

/**
 * BACKEND GAP — thread history is local.
 *
 * The backend persists `chat_sessions` and `chat_messages` and returns a
 * `session_key` with every answer, but exposes no endpoint to list sessions or
 * replay their messages. Threads are therefore kept in localStorage, keyed by
 * the backend's own `session_key`.
 *
 * The server side of the conversation is real: sending `session_key` back with
 * the next question makes the backend load that thread's history for the LLM.
 * Only the *replay* of past threads in this UI is local. When a listing
 * endpoint is added, replace `restore()` with the fetch and keep everything
 * else — components only ever touch this store.
 */

const STORAGE_KEY = 'diw.chat.threads.v1'
const MAX_STORED_THREADS = 40
export const DEFAULT_TOP_K = 6

interface ChatState {
  threads: ChatThread[]
  activeThreadId: string | null
  sending: boolean
  error: string | null
}

function createId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function newThread(documentId: number | null, documentName: string | null): ChatThread {
  const now = new Date().toISOString()
  return {
    id: createId(),
    sessionKey: null,
    title: 'New conversation',
    documentId,
    documentName,
    topK: DEFAULT_TOP_K,
    messages: [],
    createdAt: now,
    updatedAt: now,
  }
}

export const useChatStore = defineStore('chat', {
  state: (): ChatState => ({
    threads: [],
    activeThreadId: null,
    sending: false,
    error: null,
  }),

  getters: {
    activeThread(state): ChatThread | null {
      return state.threads.find((thread) => thread.id === state.activeThreadId) ?? null
    },

    orderedThreads(state): ChatThread[] {
      return [...state.threads].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
    },

    /** Threads that have never produced a turn are not worth listing. */
    startedThreads(): ChatThread[] {
      return this.orderedThreads.filter((thread: ChatThread) => thread.messages.length > 0)
    },
  },

  actions: {
    restore() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY)
        if (raw) this.threads = JSON.parse(raw) as ChatThread[]
      } catch {
        this.threads = []
      }
      if (!this.threads.length) this.startThread(null, null)
      else this.activeThreadId = this.orderedThreads[0].id
    },

    persist() {
      try {
        const keep = this.orderedThreads
          .filter((thread) => thread.messages.length > 0)
          .slice(0, MAX_STORED_THREADS)
        localStorage.setItem(STORAGE_KEY, JSON.stringify(keep))
      } catch {
        // Storage can be unavailable (private mode, quota). Threads stay in memory.
      }
    },

    startThread(documentId: number | null, documentName: string | null): ChatThread {
      // Reuse an untouched thread instead of stacking up empty ones.
      const empty = this.threads.find((thread) => thread.messages.length === 0)
      if (empty) {
        empty.documentId = documentId
        empty.documentName = documentName
        empty.updatedAt = new Date().toISOString()
        this.activeThreadId = empty.id
        return empty
      }

      const thread = newThread(documentId, documentName)
      this.threads.push(thread)
      this.activeThreadId = thread.id
      return thread
    },

    selectThread(id: string) {
      if (this.threads.some((thread) => thread.id === id)) this.activeThreadId = id
    },

    deleteThread(id: string) {
      this.threads = this.threads.filter((thread) => thread.id !== id)
      if (this.activeThreadId === id) {
        this.activeThreadId = this.orderedThreads[0]?.id ?? null
        if (!this.activeThreadId) this.startThread(null, null)
      }
      this.persist()
    },

    /**
     * Changing scope mid-thread would make earlier citations misleading, so a
     * started thread gets a fresh one instead.
     */
    setScope(documentId: number | null, documentName: string | null) {
      const thread = this.activeThread
      if (!thread) return
      if (thread.messages.length) {
        this.startThread(documentId, documentName)
        return
      }
      thread.documentId = documentId
      thread.documentName = documentName
    },

    setTopK(value: number) {
      if (this.activeThread) this.activeThread.topK = Math.min(20, Math.max(1, value))
    },

    async send(question: string) {
      const thread = this.activeThread
      const trimmed = question.trim()
      if (!thread || !trimmed || this.sending) return

      const now = new Date().toISOString()
      const userMessage: ChatMessage = {
        id: createId(),
        role: 'user',
        content: trimmed,
        createdAt: now,
      }
      thread.messages.push(userMessage)
      if (thread.messages.length === 1) thread.title = truncate(trimmed, 60)
      thread.updatedAt = now

      this.sending = true
      this.error = null

      try {
        const response = await askQuestion({
          question: trimmed,
          document_id: thread.documentId,
          session_key: thread.sessionKey,
          top_k: thread.topK,
        })

        // The backend mints the key on the first answer; reuse it from then on.
        thread.sessionKey = response.session_key
        thread.messages.push({
          id: createId(),
          role: 'assistant',
          content: response.answer,
          createdAt: new Date().toISOString(),
          sources: response.sources,
          model: response.model,
          llmConfigured: response.llm_configured,
        })
      } catch (error) {
        const apiError = error as ApiError
        this.error = apiError.detail || 'The question could not be answered.'
        thread.messages.push({
          id: createId(),
          role: 'assistant',
          content: '',
          createdAt: new Date().toISOString(),
          error: this.error,
        })
      } finally {
        thread.updatedAt = new Date().toISOString()
        this.sending = false
        this.persist()
      }
    },

    /** Drops threads scoped to a document that no longer exists. */
    forgetDocument(documentId: number) {
      this.threads = this.threads.filter((thread) => thread.documentId !== documentId)
      if (!this.threads.length) this.startThread(null, null)
      else if (!this.threads.some((thread) => thread.id === this.activeThreadId)) {
        this.activeThreadId = this.orderedThreads[0].id
      }
      this.persist()
    },
  },
})
