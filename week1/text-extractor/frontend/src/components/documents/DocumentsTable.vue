<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import FileTypeBadge from '@/components/ui/FileTypeBadge.vue'
import SkeletonRow from '@/components/ui/SkeletonRow.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import type { DocumentSummary } from '@/types/api'
import { formatDateTime, formatNumber, formatRelative } from '@/utils/format'

export default defineComponent({
  name: 'DocumentsTable',
  components: { AppIcon, FileTypeBadge, SkeletonRow, StatusBadge },
  props: {
    items: { type: Array as PropType<DocumentSummary[]>, required: true },
    loading: { type: Boolean, default: false },
    deletingId: { type: Number as PropType<number | null>, default: null },
    /** Error text per document id, so a failed row can explain itself inline. */
    errors: { type: Object as PropType<Record<number, string | null>>, default: () => ({}) },
  },
  emits: ['open', 'delete', 'ask'],
  methods: {
    formatDateTime,
    formatRelative,

    /** DOCX has no page model in the extractor, so only PDFs report pages. */
    extracted(item: DocumentSummary): string {
      const parts: string[] = []
      if (item.file_type === 'pdf' && item.page_count) {
        parts.push(`${formatNumber(item.page_count)} pages`)
      }
      if (item.word_count) parts.push(`${formatNumber(item.word_count)} words`)
      return parts.join(' · ') || '—'
    },
  },
})
</script>

<template>
  <div class="table-wrap">
    <table class="documents-table">
      <thead>
        <tr>
          <th scope="col">Document</th>
          <th scope="col" class="col-extracted">Extracted</th>
          <th scope="col" class="col-status">Status</th>
          <th scope="col" class="col-date">Uploaded</th>
          <th scope="col" class="col-actions"><span class="sr-only">Actions</span></th>
        </tr>
      </thead>

      <tbody v-if="loading">
        <tr v-for="n in 5" :key="`skeleton-${n}`" class="skeleton-row">
          <td><SkeletonRow width="58%" :height="13" /></td>
          <td class="col-extracted"><SkeletonRow width="80px" /></td>
          <td class="col-status"><SkeletonRow width="76px" :height="18" /></td>
          <td class="col-date"><SkeletonRow width="64px" /></td>
          <td class="col-actions" />
        </tr>
      </tbody>

      <tbody v-else>
        <template v-for="item in items" :key="item.id">
          <tr class="doc-row" @click="$emit('open', item)">
            <td>
              <div class="name-cell">
                <span class="file-glyph" :class="item.file_type">
                  <AppIcon name="file-text" :size="15" />
                </span>
                <div class="name-text">
                  <span class="filename" :title="item.filename">{{ item.filename }}</span>
                  <span v-if="item.title && item.title !== item.filename" class="doc-title">
                    {{ item.title }}
                  </span>
                </div>
                <FileTypeBadge :file-type="item.file_type" />
              </div>
            </td>
            <td class="col-extracted numeric">{{ extracted(item) }}</td>
            <td class="col-status"><StatusBadge :status="item.status" /></td>
            <td class="col-date" :title="formatDateTime(item.created_at)">
              {{ formatRelative(item.created_at) }}
            </td>
            <td class="col-actions">
              <div class="actions" @click.stop>
                <button
                  v-if="item.status === 'completed'"
                  class="btn btn-ghost btn-icon"
                  type="button"
                  title="Ask about this document"
                  @click="$emit('ask', item)"
                >
                  <AppIcon name="chat" :size="16" />
                </button>
                <button
                  class="btn btn-ghost btn-icon danger"
                  type="button"
                  title="Delete document"
                  :disabled="deletingId === item.id"
                  @click="$emit('delete', item)"
                >
                  <AppIcon name="trash" :size="16" />
                </button>
              </div>
            </td>
          </tr>

          <tr v-if="item.status === 'failed'" :key="`error-${item.id}`" class="error-row">
            <td colspan="5">
              <div class="error-note">
                <AppIcon name="alert" :size="14" />
                <span>{{ errors[item.id] || 'Extraction failed. Open the document for details.' }}</span>
              </div>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.table-wrap {
  /* Columns drop out below instead of scrolling; this is only a safety net. */
  overflow-x: auto;
}

.documents-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

thead th {
  padding: 10px 16px;
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border);
  text-align: left;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-tertiary);
  white-space: nowrap;
}

tbody td {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  vertical-align: middle;
}

tbody tr:last-child td {
  border-bottom: none;
}

.doc-row {
  cursor: pointer;
  transition: background var(--transition);
}

.doc-row:hover {
  background: var(--bg-hover);
}

/* Column widths — the name column takes whatever is left. */
.col-extracted { width: 27%; }
.col-status { width: 130px; }
.col-date { width: 130px; }
.col-actions { width: 84px; }

.name-cell {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
}

.file-glyph {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-tertiary);
}

.file-glyph.pdf { color: var(--red-600); }
.file-glyph.docx { color: var(--blue-600); }

.name-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.filename {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.doc-title {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.numeric {
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary);
  white-space: nowrap;
}

.col-date {
  color: var(--text-secondary);
  white-space: nowrap;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 2px;
  color: var(--text-tertiary);
  opacity: 0.65;
  transition: opacity var(--transition);
}

.doc-row:hover .actions,
.doc-row:focus-within .actions {
  opacity: 1;
}

.btn-icon.danger:hover:not(:disabled) {
  color: var(--red-600);
  background: var(--red-50);
}

.error-row td {
  padding-top: 0;
  padding-bottom: 11px;
}

.error-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 11px;
  border-radius: var(--radius-sm);
  background: var(--red-50);
  border: 1px solid var(--red-100);
  color: var(--red-700);
  font-size: 12.5px;
  line-height: 1.5;
}

.skeleton-row td {
  height: 56px;
}

/* Shed the least important columns rather than scrolling sideways. */
@media (max-width: 900px) {
  .col-extracted {
    display: none;
  }
}

@media (max-width: 680px) {
  .col-date {
    display: none;
  }

  thead th,
  tbody td {
    padding-left: 12px;
    padding-right: 12px;
  }
}
</style>
