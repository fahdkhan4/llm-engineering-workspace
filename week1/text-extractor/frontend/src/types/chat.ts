import type { SourceRef } from './api'

/**
 * Conversation state held by the frontend.
 *
 * The backend persists sessions and messages (`chat_sessions`/`chat_messages`)
 * but exposes no endpoint to read them back, so threads are kept locally and
 * keyed by the `session_key` the backend returns. See `stores/chat.ts`.
 */

export type MessageRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  createdAt: string
  sources?: SourceRef[]
  model?: string | null
  /** False when the backend answered with the LLM stub still in place. */
  llmConfigured?: boolean
  /** Set when the request failed, so the turn can be shown as an error. */
  error?: string
  /** True while tokens are streaming in from the backend. */
  streaming?: boolean
}

export interface ChatThread {
  id: string
  /** Returned by the backend on the first answer; null until then. */
  sessionKey: string | null
  title: string
  /** Null means "ask across every document". */
  documentId: number | null
  documentName: string | null
  topK: number
  messages: ChatMessage[]
  createdAt: string
  updatedAt: string
}
