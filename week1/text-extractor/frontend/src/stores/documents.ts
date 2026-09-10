import { defineStore } from 'pinia'

import { ApiError } from '@/services/http'
import {
  deleteDocument,
  getDocument,
  listDocuments,
} from '@/services/documents'
import type { DocumentDetail, DocumentStatus, DocumentSummary, FileType } from '@/types/api'

export type StatusFilter = DocumentStatus | 'all'

/**
 * `GET /documents` returns no aggregates, so the overview totals are summed
 * from the newest page of rows. `sampled` says so when the library is larger
 * than that page, rather than presenting a partial sum as a library total.
 */
export interface LibraryStats {
  documents: number
  completed: number
  processing: number
  failed: number
  pages: number
  words: number
  sampled: boolean
}

const STATS_SAMPLE_SIZE = 100

interface DocumentsState {
  items: DocumentSummary[]
  total: number
  limit: number
  offset: number
  loading: boolean
  error: string | null
  offline: boolean
  search: string
  statusFilter: StatusFilter
  /** Detail responses, cached by id. Also backs the file-type lookup below. */
  details: Record<number, DocumentDetail>
  detailLoading: boolean
  detailError: string | null
  deletingId: number | null
  stats: LibraryStats | null
  statsLoading: boolean
}

/**
 * `GET /documents` takes only `limit`/`offset` — there is no server-side search
 * or status filter — so filtering applies to the page that is currently loaded.
 * The UI states this rather than implying a library-wide search.
 */
export const useDocumentsStore = defineStore('documents', {
  state: (): DocumentsState => ({
    items: [],
    total: 0,
    limit: 25,
    offset: 0,
    loading: false,
    error: null,
    offline: false,
    search: '',
    statusFilter: 'all',
    details: {},
    detailLoading: false,
    detailError: null,
    deletingId: null,
    stats: null,
    statsLoading: false,
  }),

  getters: {
    visibleItems(state): DocumentSummary[] {
      const term = state.search.trim().toLowerCase()
      return state.items.filter((item) => {
        if (state.statusFilter !== 'all' && item.status !== state.statusFilter) return false
        if (!term) return true
        return (
          item.filename.toLowerCase().includes(term) ||
          (item.title ?? '').toLowerCase().includes(term) ||
          (item.author ?? '').toLowerCase().includes(term)
        )
      })
    },

    isFiltered(state): boolean {
      return state.search.trim() !== '' || state.statusFilter !== 'all'
    },

    page(state): number {
      return Math.floor(state.offset / state.limit) + 1
    },

    pageCount(state): number {
      return Math.max(1, Math.ceil(state.total / state.limit))
    },

    hasNextPage(state): boolean {
      return state.offset + state.limit < state.total
    },

    hasPreviousPage(state): boolean {
      return state.offset > 0
    },

    /** Completed documents are the only ones with chunks to search. */
    searchableDocuments(state): DocumentSummary[] {
      return state.items.filter((item) => item.status === 'completed')
    },

    fileTypeById(state) {
      return (documentId: number): FileType | null => {
        const listed = state.items.find((item) => item.id === documentId)
        return listed?.file_type ?? state.details[documentId]?.file_type ?? null
      }
    },
  },

  actions: {
    async fetch() {
      this.loading = true
      this.error = null
      try {
        const response = await listDocuments(this.limit, this.offset)
        this.items = response.items
        this.total = response.total
        this.offset = response.offset
        this.limit = response.limit
        this.offline = false

        // An emptied last page (after deletes) should fall back, not show blank.
        if (!response.items.length && response.offset > 0) {
          this.offset = Math.max(0, response.offset - response.limit)
          await this.fetch()
        }
      } catch (error) {
        const apiError = error as ApiError
        this.error = apiError.detail || 'Could not load your documents.'
        this.offline = apiError.offline ?? false
        this.items = []
        this.total = 0
      } finally {
        this.loading = false
      }
    },

    /** Totals for the overview. Silent on failure — the page still renders. */
    async fetchStats() {
      this.statsLoading = true
      try {
        const response = await listDocuments(STATS_SAMPLE_SIZE, 0)
        const summary = response.items.reduce(
          (accumulator, item) => {
            if (item.status === 'completed') accumulator.completed += 1
            if (item.status === 'processing' || item.status === 'pending') {
              accumulator.processing += 1
            }
            if (item.status === 'failed') accumulator.failed += 1
            // DOCX has no page model in the extractor, so only PDFs count pages.
            if (item.file_type === 'pdf') accumulator.pages += item.page_count
            accumulator.words += item.word_count
            return accumulator
          },
          { completed: 0, processing: 0, failed: 0, pages: 0, words: 0 },
        )

        this.stats = {
          ...summary,
          documents: response.total,
          sampled: response.total > response.items.length,
        }
      } catch {
        this.stats = null
      } finally {
        this.statsLoading = false
      }
    },

    async goToPage(page: number) {
      const target = Math.min(Math.max(page, 1), this.pageCount)
      this.offset = (target - 1) * this.limit
      await this.fetch()
    },

    async nextPage() {
      if (!this.hasNextPage) return
      this.offset += this.limit
      await this.fetch()
    },

    async previousPage() {
      if (!this.hasPreviousPage) return
      this.offset = Math.max(0, this.offset - this.limit)
      await this.fetch()
    },

    setSearch(value: string) {
      this.search = value
    },

    setStatusFilter(value: StatusFilter) {
      this.statusFilter = value
    },

    clearFilters() {
      this.search = ''
      this.statusFilter = 'all'
    },

    async fetchDetail(id: number, { force = false } = {}): Promise<DocumentDetail | null> {
      if (!force && this.details[id]) return this.details[id]

      this.detailLoading = true
      this.detailError = null
      try {
        const detail = await getDocument(id)
        this.details[id] = detail
        return detail
      } catch (error) {
        this.detailError = (error as ApiError).detail || 'Could not load this document.'
        return null
      } finally {
        this.detailLoading = false
      }
    },

    /** Source cards need the file type to decide whether pages can be cited. */
    async ensureFileType(id: number) {
      if (this.fileTypeById(id)) return
      await this.fetchDetail(id)
    },

    async remove(id: number): Promise<boolean> {
      this.deletingId = id
      try {
        await deleteDocument(id)
        delete this.details[id]
        await this.fetch()
        return true
      } catch (error) {
        this.error = (error as ApiError).detail || 'Could not delete this document.'
        return false
      } finally {
        this.deletingId = null
      }
    },

    /** Called after a successful upload so the library reflects it immediately. */
    cacheDetail(detail: DocumentDetail) {
      this.details[detail.id] = detail
    },
  },
})
