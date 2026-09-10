<script lang="ts">
import { defineComponent } from 'vue'
import { mapState } from 'pinia'

import AppIcon from '@/components/ui/AppIcon.vue'
import FileTypeBadge from '@/components/ui/FileTypeBadge.vue'
import StatTile from '@/components/ui/StatTile.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import WorkflowShowcase from '@/components/workflow/WorkflowShowcase.vue'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import type { DocumentSummary } from '@/types/api'
import { formatNumber, formatRelative } from '@/utils/format'

interface Tile {
  key: string
  label: string
  value: string
  caption: string
  icon: string
  tone: string
}

export default defineComponent({
  name: 'OverviewPage',
  components: { AppIcon, FileTypeBadge, StatTile, StatusBadge, WorkflowShowcase },
  computed: {
    ...mapState(useDocumentsStore, ['items', 'total', 'stats', 'statsLoading']),

    hasDocuments(): boolean {
      return this.total > 0
    },

    recent(): DocumentSummary[] {
      return this.items.slice(0, 4)
    },

    tiles(): Tile[] {
      const stats = this.stats
      return [
        {
          key: 'documents',
          label: 'Documents',
          value: formatNumber(stats?.documents ?? 0),
          caption: 'in the library',
          icon: 'library',
          tone: 'brand',
        },
        {
          key: 'ready',
          label: 'Ready to query',
          value: formatNumber(stats?.completed ?? 0),
          caption: 'fully extracted',
          icon: 'check-circle',
          tone: 'green',
        },
        {
          key: 'pages',
          label: 'Pages read',
          value: formatNumber(stats?.pages ?? 0),
          caption: 'across your PDFs',
          icon: 'file-text',
          tone: 'blue',
        },
        {
          key: 'words',
          label: 'Words indexed',
          value: formatNumber(stats?.words ?? 0),
          caption: 'searchable text',
          icon: 'database',
          tone: 'violet',
        },
      ]
    },
  },
  created() {
    const documents = useDocumentsStore()
    if (!documents.items.length) void documents.fetch()
    void documents.fetchStats()
  },
  methods: {
    formatRelative,

    open(item: DocumentSummary) {
      void this.$router.push(`/documents/${item.id}`)
    },

    ask(item: DocumentSummary) {
      useChatStore().startThread(item.id, item.filename)
      void this.$router.push({ path: '/chat', query: { document_id: String(item.id) } })
    },
  },
})
</script>

<template>
  <div class="page overview">
    <!-- Hero ------------------------------------------------------------- -->
    <section class="hero">
      <div class="hero-copy">
        <h2 class="hero-title">
          Ask your documents anything,
          <span class="gradient-text">get the source back</span>.
        </h2>

        <p class="hero-lead">
          Upload a PDF or Word file and it becomes searchable in seconds — every answer cites the
          passage it came from.
        </p>

        <div class="hero-actions">
          <RouterLink class="btn btn-primary btn-lg" to="/upload">
            <AppIcon name="upload" :size="16" />
            Upload a document
          </RouterLink>
          <RouterLink v-if="hasDocuments" class="btn btn-secondary btn-lg" to="/chat">
            <AppIcon name="chat" :size="16" />
            Ask a question
          </RouterLink>
        </div>
      </div>

      <!-- An illustration of the output, not a real answer. -->
      <figure class="preview" aria-label="Illustration of a cited answer">
        <figcaption class="preview-tag">Example</figcaption>

        <div class="bubble question">
          <AppIcon name="chat" :size="13" />
          Which clause covers early termination?
        </div>

        <div class="bubble answer">
          <span class="line w-90" />
          <span class="line w-100" />
          <span class="line w-72" />

          <div class="citation">
            <span class="citation-mark">1</span>
            <div class="citation-text">
              <span class="citation-name">Services Agreement.pdf</span>
              <span class="citation-loc">Termination · pages 11–12</span>
            </div>
          </div>
        </div>
      </figure>
    </section>

    <!-- Live numbers ----------------------------------------------------- -->
    <section class="tiles" aria-label="Library at a glance">
      <StatTile
        v-for="tile in tiles"
        :key="tile.key"
        :label="tile.label"
        :value="tile.value"
        :caption="tile.caption"
        :icon="tile.icon"
        :tone="tile.tone"
        :loading="statsLoading && !stats"
      />
    </section>

    <p v-if="stats?.sampled" class="tiles-note">
      <AppIcon name="info" :size="13" />
      Pages and words are summed from the 100 most recent documents.
    </p>

    <!-- Workflow --------------------------------------------------------- -->
    <section class="block">
      <h3 class="block-title">How it works</h3>
      <WorkflowShowcase />
    </section>

    <!-- Recent work or a way in ------------------------------------------ -->
    <section class="block">
      <header class="block-header">
        <h3 class="block-title">{{ hasDocuments ? 'Recent documents' : 'Get started' }}</h3>
        <RouterLink v-if="hasDocuments" class="btn btn-secondary btn-sm" to="/library">
          All documents
          <AppIcon name="arrow-right" :size="14" />
        </RouterLink>
      </header>

      <ul v-if="hasDocuments" class="recent">
        <li v-for="item in recent" :key="item.id" class="card card-interactive recent-item">
          <button class="recent-open" type="button" @click="open(item)">
            <span class="recent-glyph" :class="item.file_type">
              <AppIcon name="file-text" :size="16" />
            </span>
            <span class="recent-text">
              <span class="recent-name" :title="item.filename">{{ item.filename }}</span>
              <span class="recent-sub">{{ formatRelative(item.created_at) }}</span>
            </span>
          </button>

          <div class="recent-foot">
            <FileTypeBadge :file-type="item.file_type" />
            <StatusBadge :status="item.status" />
            <div class="spacer" />
            <button
              v-if="item.status === 'completed'"
              class="btn btn-ghost btn-sm"
              type="button"
              @click="ask(item)"
            >
              <AppIcon name="chat" :size="14" />
              Ask
            </button>
          </div>
        </li>
      </ul>

      <div v-else class="card start">
        <span class="glyph-tile brand">
          <AppIcon name="upload" :size="17" />
        </span>
        <p class="start-text">
          Upload one document to see the whole flow — parsed, indexed and answering questions in
          seconds.
        </p>
        <RouterLink class="btn btn-primary" to="/upload">Upload a document</RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.overview {
  max-width: 1180px;
}

/* Hero -------------------------------------------------------------------- */

.hero {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
  gap: 40px;
  align-items: center;
  padding: 34px 36px;
  border: 1px solid var(--border);
  border-radius: var(--radius-2xl);
  background: var(--brand-wash), var(--bg-surface);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}

.hero::before {
  content: '';
  position: absolute;
  inset: -40% 40% 40% -20%;
  background: radial-gradient(closest-side, rgba(99, 102, 241, 0.18), transparent);
  pointer-events: none;
}

.hero-copy {
  position: relative;
  min-width: 0;
}

.hero-title {
  font-size: 30px;
  font-weight: 680;
  line-height: 1.18;
  letter-spacing: -0.03em;
  max-width: 16ch;
}

.hero-lead {
  margin-top: 13px;
  max-width: 48ch;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 22px;
}

/* Answer illustration */
.preview {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 11px;
  padding: 17px;
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  background: var(--bg-surface);
  box-shadow: var(--shadow-lg);
}

.preview-tag {
  position: absolute;
  top: -9px;
  right: 14px;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--bg-muted);
  border: 1px solid var(--border);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-tertiary);
}

.bubble {
  border-radius: var(--radius-md);
  font-size: 12.5px;
}

.bubble.question {
  display: flex;
  align-items: center;
  gap: 8px;
  align-self: flex-end;
  max-width: 92%;
  padding: 9px 12px;
  background: var(--brand-gradient);
  color: #fff;
  box-shadow: var(--brand-glow);
}

.bubble.answer {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
}

.line {
  height: 7px;
  border-radius: 999px;
  background: var(--bg-muted);
}

[data-theme='dark'] .line {
  background: var(--border);
}

.w-100 { width: 100%; }
.w-90 { width: 90%; }
.w-72 { width: 72%; }

.citation {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-top: 5px;
  padding: 9px 11px;
  border-radius: var(--radius);
  background: var(--bg-surface);
  border: 1px solid var(--accent-soft-border);
}

.citation-mark {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  border-radius: 5px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 10.5px;
  font-weight: 600;
}

.citation-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.citation-name {
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.citation-loc {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* Stat tiles -------------------------------------------------------------- */

.tiles {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.tiles-note {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  font-size: 11.5px;
  color: var(--text-tertiary);
}

/* Sections ---------------------------------------------------------------- */

.block {
  margin-top: 40px;
}

.block-title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.015em;
  margin-bottom: 18px;
}

.block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.block-header .block-title {
  margin-bottom: 0;
}

/* Recent ------------------------------------------------------------------ */

.recent {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.recent-item {
  display: flex;
  flex-direction: column;
  padding: 15px;
  min-width: 0;
}

.recent-open {
  display: flex;
  align-items: center;
  gap: 11px;
  text-align: left;
  min-width: 0;
}

.recent-glyph {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 9px;
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-tertiary);
}

.recent-glyph.pdf { color: var(--red-600); }
.recent-glyph.docx { color: var(--blue-600); }

.recent-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.recent-name {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-sub {
  font-size: 11.5px;
  color: var(--text-tertiary);
}

.recent-foot {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 13px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

/* Start card -------------------------------------------------------------- */

.start {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  flex-wrap: wrap;
}

.start-text {
  flex: 1;
  min-width: 240px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}

/* Responsive -------------------------------------------------------------- */

@media (max-width: 1080px) {
  .hero {
    grid-template-columns: 1fr;
    gap: 28px;
    padding: 28px 24px;
  }

  .hero-title {
    font-size: 27px;
    max-width: none;
  }

  .tiles,
  .recent {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .hero {
    padding: 24px 18px;
  }

  .hero-title {
    font-size: 24px;
  }

  .tiles,
  .recent {
    grid-template-columns: 1fr;
  }
}
</style>
