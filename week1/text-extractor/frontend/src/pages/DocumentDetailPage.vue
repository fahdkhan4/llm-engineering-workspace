<script lang="ts">
import { defineComponent } from 'vue'

import DocumentContent from '@/components/documents/DocumentContent.vue'
import DocumentMetadata from '@/components/documents/DocumentMetadata.vue'
import AlertPanel from '@/components/ui/AlertPanel.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import FileTypeBadge from '@/components/ui/FileTypeBadge.vue'
import SkeletonRow from '@/components/ui/SkeletonRow.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import {
  CONTENT_ENDPOINT_AVAILABLE,
  getDocumentContent,
} from '@/services/documentContent'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import { useToastStore } from '@/stores/toasts'
import type { DocumentDetail } from '@/types/api'
import type { DocumentBlock, DocumentTable } from '@/types/content'
import { formatPageRanges } from '@/utils/format'

export default defineComponent({
  name: 'DocumentDetailPage',
  components: {
    AlertPanel,
    AppIcon,
    ConfirmDialog,
    DocumentContent,
    DocumentMetadata,
    EmptyState,
    FileTypeBadge,
    SkeletonRow,
    StatusBadge,
  },
  props: {
    id: { type: String, required: true },
  },
  data() {
    return {
      document: null as DocumentDetail | null,
      loading: true,
      loadError: null as string | null,
      notFound: false,
      confirmingDelete: false,
      contentAvailable: CONTENT_ENDPOINT_AVAILABLE,
      blocks: [] as DocumentBlock[],
      tables: [] as DocumentTable[],
      contentLoading: false,
    }
  },
  computed: {
    documentId(): number {
      return Number(this.id)
    },

    ocrPages(): string {
      const pages = this.document?.ocr_required_pages ?? []
      return pages.length ? formatPageRanges(pages) : ''
    },

    isDocx(): boolean {
      return this.document?.file_type === 'docx'
    },

    deleting(): boolean {
      return useDocumentsStore().deletingId === this.documentId
    },
  },
  watch: {
    id: {
      immediate: true,
      handler() {
        void this.load()
      },
    },
  },
  methods: {
    async load() {
      this.loading = true
      this.loadError = null
      this.notFound = false

      const store = useDocumentsStore()
      const detail = await store.fetchDetail(this.documentId, { force: true })

      if (!detail) {
        this.loadError = store.detailError
        this.notFound = store.detailError?.toLowerCase().includes('not found') ?? false
      } else {
        this.document = detail
        if (detail.status === 'completed') void this.loadContent()
      }
      this.loading = false
    },

    async loadContent() {
      if (!this.contentAvailable) return
      this.contentLoading = true
      try {
        const content = await getDocumentContent(this.documentId)
        this.blocks = content.blocks
        this.tables = content.tables
      } catch {
        this.contentAvailable = false
      } finally {
        this.contentLoading = false
      }
    },

    askAboutDocument() {
      if (!this.document) return
      useChatStore().startThread(this.document.id, this.document.filename)
      void this.$router.push({ path: '/chat', query: { document_id: String(this.document.id) } })
    },

    async confirmDelete() {
      if (!this.document) return
      const store = useDocumentsStore()
      const name = this.document.filename
      const succeeded = await store.remove(this.document.id)
      this.confirmingDelete = false

      if (succeeded) {
        useChatStore().forgetDocument(this.documentId)
        useToastStore().success('Document deleted', `“${name}” was removed from your library.`)
        void this.$router.push('/library')
      } else {
        useToastStore().error('Could not delete document', store.error ?? undefined)
      }
    },
  },
})
</script>

<template>
  <div class="page">
    <RouterLink to="/library" class="back-link">
      <AppIcon name="chevron-left" :size="14" />
      Library
    </RouterLink>

    <div v-if="loading" class="loading surface">
      <SkeletonRow width="38%" :height="20" />
      <SkeletonRow width="22%" />
      <SkeletonRow width="90%" />
      <SkeletonRow width="72%" />
    </div>

    <div v-else-if="notFound" class="surface">
      <EmptyState
        icon="search"
        title="This document no longer exists"
        description="It may have been deleted."
      >
        <template #actions>
          <RouterLink class="btn btn-primary" to="/library">Back to library</RouterLink>
        </template>
      </EmptyState>
    </div>

    <AlertPanel v-else-if="loadError" tone="danger" title="Could not load this document">
      {{ loadError }}
      <template #actions>
        <button class="btn btn-sm btn-secondary" type="button" @click="load">Try again</button>
      </template>
    </AlertPanel>

    <template v-else-if="document">
      <header class="doc-header">
        <div class="doc-identity">
          <span class="doc-glyph" :class="document.file_type">
            <AppIcon name="file-text" :size="20" />
          </span>
          <div class="doc-titles">
            <h2 class="doc-name">{{ document.filename }}</h2>
            <p v-if="document.title && document.title !== document.filename" class="doc-subtitle">
              {{ document.title }}
            </p>
            <div class="doc-badges">
              <FileTypeBadge :file-type="document.file_type" />
              <StatusBadge :status="document.status" />
            </div>
          </div>
        </div>

        <div class="doc-actions">
          <button
            class="btn btn-secondary"
            type="button"
            :disabled="deleting"
            @click="confirmingDelete = true"
          >
            <AppIcon name="trash" :size="15" />
            Delete
          </button>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="document.status !== 'completed'"
            :title="document.status !== 'completed' ? 'Only completed documents can be searched' : ''"
            @click="askAboutDocument"
          >
            <AppIcon name="chat" :size="15" />
            Ask about this document
          </button>
        </div>
      </header>

      <AlertPanel
        v-if="document.status === 'failed'"
        tone="danger"
        title="Extraction failed"
        class="stack-alert"
      >
        {{ document.error_message || 'The document could not be parsed.' }}
        <template #actions>
          <RouterLink class="btn btn-sm btn-secondary" to="/upload">Upload it again</RouterLink>
        </template>
      </AlertPanel>

      <AlertPanel
        v-if="ocrPages"
        tone="warning"
        title="Some pages contain no extractable text"
        class="stack-alert"
      >
        Page{{ document.ocr_required_pages.length > 1 ? 's' : '' }} {{ ocrPages }} appear to be
        scanned images, so their content is not searchable or citable.
      </AlertPanel>

      <section class="surface card">
        <h3 class="card-title">Document information</h3>
        <DocumentMetadata :document="document" />
      </section>

      <section class="surface card">
        <div class="card-head">
          <h3 class="card-title">Extracted content</h3>
          <span v-if="isDocx" class="badge badge-neutral">No page positions</span>
        </div>

        <p v-if="isDocx" class="docx-note">
          <AppIcon name="info" :size="13" />
          Word documents have no page positions, so pages are never cited for this file.
        </p>

        <DocumentContent
          v-if="contentAvailable && blocks.length"
          :blocks="blocks"
          :tables="tables"
          :file-type="document.file_type"
          class="content-block"
        />

        <div v-else-if="contentLoading" class="loading-inline">
          <SkeletonRow width="60%" :height="16" />
          <SkeletonRow width="94%" />
          <SkeletonRow width="88%" />
          <SkeletonRow width="76%" />
        </div>

        <EmptyState
          v-else
          icon="book"
          compact
          title="The extracted body is not available from the API"
          tone="warning"
        >
          <template #description>
            This document's headings, paragraphs, lists and tables were extracted and stored on
            upload, but the backend exposes no endpoint that returns them — <span class="mono"
              >GET /documents/{id}</span
            >
            returns metadata only. The reading view is built and will render as soon as a content
            endpoint exists. In the meantime, the same text is reachable through Chat, which cites
            the exact passage it used.
          </template>
          <template #actions>
            <button
              class="btn btn-primary btn-sm"
              type="button"
              :disabled="document.status !== 'completed'"
              @click="askAboutDocument"
            >
              <AppIcon name="chat" :size="14" />
              Ask about this document
            </button>
          </template>
        </EmptyState>
      </section>
    </template>

    <ConfirmDialog
      :open="confirmingDelete"
      title="Delete this document?"
      confirm-label="Delete permanently"
      :busy="deleting"
      @cancel="confirmingDelete = false"
      @confirm="confirmDelete"
    >
      <strong>{{ document?.filename }}</strong> and everything extracted from it — blocks, tables
      and searchable chunks — will be removed. This cannot be undone.
    </ConfirmDialog>
  </div>
</template>

<style scoped>
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 16px;
  font-size: 12.5px;
  color: var(--text-secondary);
  transition: color var(--transition);
}

.back-link:hover {
  color: var(--text-primary);
}

.loading {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 24px;
}

.doc-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.doc-identity {
  display: flex;
  gap: 13px;
  min-width: 0;
}

.doc-glyph {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-tertiary);
}

.doc-glyph.pdf { color: var(--red-600); }
.doc-glyph.docx { color: var(--blue-600); }

.doc-titles {
  min-width: 0;
}

.doc-name {
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.018em;
  overflow-wrap: anywhere;
}

.doc-subtitle {
  margin-top: 2px;
  font-size: 13px;
  color: var(--text-secondary);
}

.doc-badges {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 9px;
}

.doc-actions {
  display: flex;
  gap: 9px;
  flex-wrap: wrap;
}

.stack-alert {
  margin-bottom: 16px;
}

.card {
  padding: 20px;
  margin-bottom: 16px;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
}

.card-head .card-title {
  margin-bottom: 0;
}

.card > .card-title {
  margin-bottom: 16px;
}

.docx-note {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin-bottom: 16px;
  padding: 9px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.55;
}

.content-block {
  margin-top: 4px;
}

.loading-inline {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 0;
}
</style>
