<script lang="ts">
import { defineComponent } from 'vue'
import { mapState } from 'pinia'

import DocumentsTable from '@/components/documents/DocumentsTable.vue'
import AlertPanel from '@/components/ui/AlertPanel.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import StatTile from '@/components/ui/StatTile.vue'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore, type StatusFilter } from '@/stores/documents'
import { useToastStore } from '@/stores/toasts'
import type { DocumentSummary } from '@/types/api'
import { formatNumber } from '@/utils/format'

export default defineComponent({
  name: 'LibraryPage',
  components: { AlertPanel, AppIcon, ConfirmDialog, DocumentsTable, EmptyState, StatTile },
  data() {
    return {
      pendingDelete: null as DocumentSummary | null,
      statusOptions: [
        { value: 'all', label: 'All statuses' },
        { value: 'completed', label: 'Completed' },
        { value: 'processing', label: 'Processing' },
        { value: 'pending', label: 'Pending' },
        { value: 'failed', label: 'Failed' },
      ],
    }
  },
  computed: {
    ...mapState(useDocumentsStore, [
      'items',
      'visibleItems',
      'loading',
      'error',
      'offline',
      'total',
      'limit',
      'offset',
      'search',
      'statusFilter',
      'isFiltered',
      'page',
      'pageCount',
      'hasNextPage',
      'hasPreviousPage',
      'deletingId',
      'details',
      'stats',
      'statsLoading',
    ]),

    tiles(): { key: string; label: string; value: string; icon: string; tone: string }[] {
      const stats = this.stats
      return [
        {
          key: 'documents',
          label: 'Documents',
          value: formatNumber(stats?.documents ?? 0),
          icon: 'library',
          tone: 'brand',
        },
        {
          key: 'ready',
          label: 'Ready to query',
          value: formatNumber(stats?.completed ?? 0),
          icon: 'check-circle',
          tone: 'green',
        },
        {
          key: 'pages',
          label: 'Pages read',
          value: formatNumber(stats?.pages ?? 0),
          icon: 'file-text',
          tone: 'blue',
        },
        {
          key: 'words',
          label: 'Words indexed',
          value: formatNumber(stats?.words ?? 0),
          icon: 'database',
          tone: 'violet',
        },
      ]
    },

    isEmptyLibrary(): boolean {
      return !this.loading && !this.error && this.total === 0
    },

    noFilterMatches(): boolean {
      return !this.loading && this.items.length > 0 && this.visibleItems.length === 0
    },

    rangeLabel(): string {
      if (!this.total) return 'No documents'
      const from = this.offset + 1
      const to = Math.min(this.offset + this.items.length, this.total)
      return `${from}–${to} of ${formatNumber(this.total)}`
    },

    /** `DocumentSummary` carries no error text, so failed rows read it from detail. */
    errorsById(): Record<number, string | null> {
      const map: Record<number, string | null> = {}
      for (const item of this.items) {
        if (item.status === 'failed') map[item.id] = this.details[item.id]?.error_message ?? null
      }
      return map
    },

    searchValue: {
      get(): string {
        return this.search
      },
      set(value: string) {
        useDocumentsStore().setSearch(value)
      },
    },

    statusValue: {
      get(): StatusFilter {
        return this.statusFilter
      },
      set(value: StatusFilter) {
        useDocumentsStore().setStatusFilter(value)
      },
    },
  },
  created() {
    void this.load()
  },
  methods: {
    async load() {
      const store = useDocumentsStore()
      await store.fetch()
      void store.fetchStats()
      // Pull the error text for anything that failed, so the row can explain itself.
      await Promise.all(
        store.items
          .filter((item) => item.status === 'failed')
          .map((item) => store.fetchDetail(item.id)),
      )
    },

    open(item: DocumentSummary) {
      void this.$router.push(`/documents/${item.id}`)
    },

    ask(item: DocumentSummary) {
      useChatStore().startThread(item.id, item.filename)
      void this.$router.push({ path: '/chat', query: { document_id: String(item.id) } })
    },

    requestDelete(item: DocumentSummary) {
      this.pendingDelete = item
    },

    async confirmDelete() {
      const target = this.pendingDelete
      if (!target) return

      const store = useDocumentsStore()
      const succeeded = await store.remove(target.id)
      this.pendingDelete = null

      if (succeeded) {
        void store.fetchStats()
        useChatStore().forgetDocument(target.id)
        useToastStore().success('Document deleted', target.filename)
      } else {
        useToastStore().error('Could not delete document', store.error ?? undefined)
      }
    },

    clearFilters() {
      useDocumentsStore().clearFilters()
    },

    nextPage() {
      void useDocumentsStore().nextPage()
    },

    previousPage() {
      void useDocumentsStore().previousPage()
    },
  },
})
</script>

<template>
  <div class="page">
    <header class="page-header header-row">
      <div>
        <h2 class="page-title">Library</h2>
        <p class="page-subtitle">
          Open a document to inspect it, or ask a question across the library.
        </p>
      </div>
      <RouterLink class="btn btn-primary" to="/upload">
        <AppIcon name="upload" :size="15" />
        Upload document
      </RouterLink>
    </header>

    <section v-if="total > 0" class="stats-strip" aria-label="Library at a glance">
      <StatTile
        v-for="tile in tiles"
        :key="tile.key"
        compact
        :label="tile.label"
        :value="tile.value"
        :icon="tile.icon"
        :tone="tile.tone"
        :loading="statsLoading && !stats"
      />
    </section>

    <AlertPanel v-if="error && !offline" tone="danger" title="Could not load the library" class="page-alert">
      {{ error }}
      <template #actions>
        <button class="btn btn-sm btn-secondary" type="button" @click="load">Try again</button>
      </template>
    </AlertPanel>

    <section class="surface panel">
      <div class="toolbar">
        <div class="search-field">
          <AppIcon name="search" :size="15" class="search-icon" />
          <input
            v-model="searchValue"
            class="input search-input"
            type="search"
            placeholder="Filter by filename, title or author…"
            aria-label="Filter documents"
          />
        </div>

        <select v-model="statusValue" class="select status-select" aria-label="Filter by status">
          <option v-for="option in statusOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>

        <button
          class="btn btn-secondary btn-icon"
          type="button"
          title="Refresh"
          :disabled="loading"
          @click="load"
        >
          <AppIcon name="refresh" :size="15" />
        </button>
      </div>

      <p v-if="isFiltered && !loading" class="filter-note">
        <AppIcon name="info" :size="13" />
        Filtering applies to this page of results.
      </p>

      <EmptyState
        v-if="isEmptyLibrary"
        icon="library"
        tone="accent"
        title="Your library is empty"
        description="Upload a PDF or Word document to make it searchable."
      >
        <template #actions>
          <RouterLink class="btn btn-primary" to="/upload">
            <AppIcon name="upload" :size="15" />
            Upload your first document
          </RouterLink>
        </template>
      </EmptyState>

      <EmptyState
        v-else-if="noFilterMatches"
        icon="search"
        compact
        title="No documents match these filters"
        description="Try a different term, or clear the filters."
      >
        <template #actions>
          <button class="btn btn-secondary" type="button" @click="clearFilters">Clear filters</button>
        </template>
      </EmptyState>

      <DocumentsTable
        v-else
        :items="visibleItems"
        :loading="loading"
        :deleting-id="deletingId"
        :errors="errorsById"
        @open="open"
        @ask="ask"
        @delete="requestDelete"
      />

      <div v-if="total > 0 && !isEmptyLibrary" class="pagination">
        <span class="range">{{ rangeLabel }}</span>
        <div class="spacer" />
        <span class="page-indicator">Page {{ page }} of {{ pageCount }}</span>
        <button
          class="btn btn-secondary btn-sm"
          type="button"
          :disabled="!hasPreviousPage || loading"
          @click="previousPage"
        >
          <AppIcon name="chevron-left" :size="14" />
          Previous
        </button>
        <button
          class="btn btn-secondary btn-sm"
          type="button"
          :disabled="!hasNextPage || loading"
          @click="nextPage"
        >
          Next
          <AppIcon name="chevron-right" :size="14" />
        </button>
      </div>
    </section>

    <ConfirmDialog
      :open="pendingDelete !== null"
      title="Delete this document?"
      confirm-label="Delete permanently"
      :busy="deletingId !== null"
      @cancel="pendingDelete = null"
      @confirm="confirmDelete"
    >
      <strong>{{ pendingDelete?.filename }}</strong> and everything extracted from it will be
      removed. This cannot be undone.
    </ConfirmDialog>
  </div>
</template>

<style scoped>
.stats-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
}

.page-alert {
  margin-bottom: 16px;
}

.panel {
  overflow: hidden;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 13px 14px;
  border-bottom: 1px solid var(--border);
}

.search-field {
  position: relative;
  flex: 1;
  min-width: 180px;
  max-width: 380px;
}

.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-tertiary);
  pointer-events: none;
}

.search-input {
  padding-left: 31px;
}

.search-input::-webkit-search-cancel-button {
  cursor: pointer;
}

.status-select {
  width: 158px;
  flex-shrink: 0;
}

.filter-note {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 15px;
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border);
  color: var(--text-tertiary);
  font-size: 12px;
}

.pagination {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 14px;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}

.range,
.page-indicator {
  font-size: 12.5px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 900px) {
  .stats-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .toolbar {
    flex-wrap: wrap;
  }

  .search-field {
    max-width: none;
    flex-basis: 100%;
  }
}
</style>
