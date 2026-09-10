/**
 * Single place where HTTP happens. Components and stores call the typed
 * service modules; nothing else builds URLs or reads `fetch` responses.
 */

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

/** Normalised error every service throws, so the UI can render one shape. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: string
  /** True when the backend could not be reached at all. */
  readonly offline: boolean

  constructor(message: string, status: number, options: { offline?: boolean } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = message
    this.offline = options.offline ?? false
  }

  get isNotFound(): boolean {
    return this.status === 404
  }

  get isTooLarge(): boolean {
    return this.status === 413
  }

  get isUnsupportedType(): boolean {
    return this.status === 415
  }

  /** 422 from this backend means extraction failed, not a validation problem. */
  get isUnprocessable(): boolean {
    return this.status === 422
  }
}

type QueryValue = string | number | boolean | null | undefined

interface RequestOptions {
  method?: 'GET' | 'POST' | 'DELETE'
  query?: Record<string, QueryValue>
  body?: BodyInit
  signal?: AbortSignal
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const url = `${BASE_URL}${path}`
  if (!query) return url

  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== null && value !== undefined && value !== '') {
      params.append(key, String(value))
    }
  }
  const queryString = params.toString()
  return queryString ? `${url}?${queryString}` : url
}

/** FastAPI returns `{detail: string}` or `{detail: [{msg, loc}, ...]}`. */
async function readErrorDetail(response: Response): Promise<string> {
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    return response.statusText || `Request failed with status ${response.status}`
  }

  const detail = (payload as { detail?: unknown })?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item as { msg?: string })?.msg)
      .filter((msg): msg is string => Boolean(msg))
    if (messages.length) return messages.join('. ')
  }
  return response.statusText || `Request failed with status ${response.status}`
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', query, body, signal } = options

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), { method, body, signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(
      'Cannot reach the backend. Check that the API is running.',
      0,
      { offline: true },
    )
  }

  if (!response.ok) {
    throw new ApiError(await readErrorDetail(response), response.status)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
