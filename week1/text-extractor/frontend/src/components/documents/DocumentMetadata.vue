<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import StatusBadge from '@/components/ui/StatusBadge.vue'
import type { DocumentDetail } from '@/types/api'
import { formatBytes, formatDateTime, formatNumber } from '@/utils/format'

interface Field {
  key: string
  label: string
  value: string
  mono?: boolean
}

/** Values the parser reports as empty are shown as "Not recorded", not blank. */
function textOrNull(value: unknown): string | null {
  if (value === null || value === undefined) return null
  const text = String(value).trim()
  return text ? text : null
}

export default defineComponent({
  name: 'DocumentMetadata',
  components: { StatusBadge },
  props: {
    document: { type: Object as PropType<DocumentDetail>, required: true },
  },
  computed: {
    fields(): Field[] {
      const doc = this.document
      const list: Field[] = [
        { key: 'filename', label: 'Filename', value: doc.filename },
        { key: 'type', label: 'Type', value: doc.file_type.toUpperCase() },
        { key: 'title', label: 'Title', value: textOrNull(doc.title) ?? 'Not recorded' },
        { key: 'author', label: 'Author', value: textOrNull(doc.author) ?? 'Not recorded' },
        { key: 'subject', label: 'Subject', value: textOrNull(doc.subject) ?? 'Not recorded' },
        { key: 'keywords', label: 'Keywords', value: textOrNull(doc.keywords) ?? 'None' },
      ]

      // DOCX extraction has no page model, so its page count is not meaningful.
      if (doc.file_type === 'pdf') {
        list.push({ key: 'pages', label: 'Pages', value: formatNumber(doc.page_count) })
      }

      list.push(
        { key: 'words', label: 'Words', value: formatNumber(doc.word_count) },
        { key: 'chars', label: 'Characters', value: formatNumber(doc.char_count) },
        { key: 'size', label: 'File size', value: formatBytes(doc.file_size) },
        { key: 'uploaded', label: 'Uploaded', value: formatDateTime(doc.created_at) },
      )
      return list
    },

    /** Whatever else the parser found — producer, creation dates, and so on. */
    extraFields(): Field[] {
      return Object.entries(this.document.extra_metadata ?? {})
        .map(([key, value]) => ({
          key,
          label: key.replace(/[_-]+/g, ' ').replace(/^\w/, (char) => char.toUpperCase()),
          value: textOrNull(value) ?? '',
          mono: true,
        }))
        .filter((field) => field.value !== '')
    },
  },
})
</script>

<template>
  <div class="metadata">
    <dl class="grid">
      <div v-for="field in fields" :key="field.key" class="field">
        <dt>{{ field.label }}</dt>
        <dd :class="{ subdued: field.value === 'Not recorded' || field.value === 'None' }">
          {{ field.value }}
        </dd>
      </div>
      <div class="field">
        <dt>Status</dt>
        <dd><StatusBadge :status="document.status" /></dd>
      </div>
    </dl>

    <details v-if="extraFields.length" class="extra">
      <summary>
        Parser metadata
        <span class="count">{{ extraFields.length }}</span>
      </summary>
      <dl class="grid extra-grid">
        <div v-for="field in extraFields" :key="field.key" class="field">
          <dt>{{ field.label }}</dt>
          <dd class="mono">{{ field.value }}</dd>
        </div>
      </dl>
    </details>
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
  gap: 16px 22px;
}

.field {
  min-width: 0;
}

.field dt {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-tertiary);
  letter-spacing: 0.02em;
  margin-bottom: 3px;
}

.field dd {
  font-size: 13px;
  font-weight: 450;
  overflow-wrap: anywhere;
  font-variant-numeric: tabular-nums;
}

.field dd.subdued {
  color: var(--text-tertiary);
  font-weight: 400;
}

.extra {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.extra summary {
  display: flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-secondary);
  list-style: none;
}

.extra summary::-webkit-details-marker {
  display: none;
}

.extra summary::before {
  content: '';
  width: 0;
  height: 0;
  border-left: 4px solid currentColor;
  border-top: 3.5px solid transparent;
  border-bottom: 3.5px solid transparent;
  transition: transform var(--transition);
}

.extra[open] summary::before {
  transform: rotate(90deg);
}

.count {
  padding: 0 6px;
  height: 17px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: var(--bg-muted);
  font-size: 10.5px;
  color: var(--text-tertiary);
}

.extra-grid {
  margin-top: 14px;
}

.extra-grid dd {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
