<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import type { DocumentDetail, ExtractionCounts } from '@/types/api'
import { formatNumber } from '@/utils/format'

interface Stat {
  key: string
  label: string
  value: string
  icon: string
}

export default defineComponent({
  name: 'ExtractionSummary',
  components: { AppIcon },
  props: {
    document: { type: Object as PropType<DocumentDetail>, required: true },
    counts: { type: Object as PropType<ExtractionCounts | null>, default: null },
  },
  computed: {
    stats(): Stat[] {
      const list: Stat[] = []
      if (this.counts) {
        list.push(
          { key: 'blocks', label: 'Sections', value: formatNumber(this.counts.blocks), icon: 'layers' },
          { key: 'tables', label: 'Tables', value: formatNumber(this.counts.tables), icon: 'table' },
          { key: 'chunks', label: 'Chunks', value: formatNumber(this.counts.chunks), icon: 'target' },
        )
      }
      // DOCX extraction has no page model, so a page count would be misleading.
      if (this.document.file_type === 'pdf') {
        list.push({
          key: 'pages',
          label: 'Pages',
          value: formatNumber(this.document.page_count),
          icon: 'file-text',
        })
      }
      list.push({
        key: 'words',
        label: 'Words',
        value: formatNumber(this.document.word_count),
        icon: 'book',
      })
      return list
    },
  },
})
</script>

<template>
  <div class="summary">
    <dl class="meta">
      <div class="meta-item">
        <dt>Title</dt>
        <dd>{{ document.title || document.filename }}</dd>
      </div>
      <div class="meta-item">
        <dt>Author</dt>
        <dd :class="{ empty: !document.author }">{{ document.author || 'Not recorded' }}</dd>
      </div>
    </dl>

    <ul class="stats">
      <li v-for="stat in stats" :key="stat.key" class="stat">
        <AppIcon :name="stat.icon" :size="14" class="stat-icon" />
        <span class="stat-value">{{ stat.value }}</span>
        <span class="stat-label">{{ stat.label }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.summary {
  display: flex;
  flex-direction: column;
  gap: 13px;
}

.meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px 20px;
}

.meta-item dt {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-tertiary);
  letter-spacing: 0.02em;
  margin-bottom: 2px;
}

.meta-item dd {
  font-size: 13px;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.meta-item dd.empty {
  font-weight: 400;
  color: var(--text-tertiary);
}

.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.stat {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
}

.stat-icon {
  color: var(--text-tertiary);
}

.stat-value {
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
