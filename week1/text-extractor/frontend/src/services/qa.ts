import type { AnswerResponse, AskParams, SourceRef } from '@/types/api'

import { ApiError, buildUrl, readErrorDetail, request } from './http'

/**
 * `GET /` — answer a question from the extracted documents.
 *
 * `session_key` comes back on every answer and must be sent with the next
 * question to keep the thread going.
 */
export function askQuestion(params: AskParams, signal?: AbortSignal): Promise<AnswerResponse> {
  return request<AnswerResponse>('/', {
    query: {
      question: params.question,
      document_id: params.document_id ?? undefined,
      session_key: params.session_key ?? undefined,
      top_k: params.top_k ?? undefined,
    },
    signal,
  })
}

export interface StreamEvent {
  sources?: SourceRef[]
  session_key?: string
  chunk?: string
  done?: boolean
  model?: string | null
  usage?: Record<string, unknown>
  error?: string
}

/**
 * `POST /ask/stream` — stream an answer using Server-Sent Events (SSE).
 */
export async function askQuestionStream(
  params: AskParams,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const url = buildUrl('/ask/stream', {
    question: params.question,
    document_id: params.document_id ?? undefined,
    session_key: params.session_key ?? undefined,
    top_k: params.top_k ?? undefined,
  })

  let response: Response
  try {
    response = await fetch(url, { method: 'POST', signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError('Cannot reach the backend. Check that the API is running.', 0, {
      offline: true,
    })
  }

  if (!response.ok) {
    throw new ApiError(await readErrorDetail(response), response.status)
  }

  if (!response.body) {
    throw new ApiError('Response body is empty.', response.status)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() ?? ''
      for (const part of parts) {
        for (const line of part.split('\n')) {
          const trimmed = line.trim()
          if (trimmed.startsWith('data: ')) {
            const dataStr = trimmed.slice(6)
            try {
              const event = JSON.parse(dataStr) as StreamEvent
              onEvent(event)
            } catch {
              // ignore malformed lines
            }
          }
        }
      }
    }

    if (buffer.trim()) {
      for (const line of buffer.split('\n')) {
        const trimmed = line.trim()
        if (trimmed.startsWith('data: ')) {
          try {
            const event = JSON.parse(trimmed.slice(6)) as StreamEvent
            onEvent(event)
          } catch {
            // ignore malformed lines
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
