<script lang="ts">
import { defineComponent } from 'vue'
import { mapState } from 'pinia'

import UploadDropzone from '@/components/upload/UploadDropzone.vue'
import UploadQueueItem from '@/components/upload/UploadQueueItem.vue'
import AlertPanel from '@/components/ui/AlertPanel.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import WorkflowRail from '@/components/workflow/WorkflowRail.vue'
import type { PipelineStepKey } from '@/components/workflow/pipeline'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import { useHealthStore } from '@/stores/health'
import { useToastStore } from '@/stores/toasts'
import { useUploadStore, type UploadItem } from '@/stores/uploads'
import { MAX_UPLOAD_MB } from '@/utils/files'

export default defineComponent({
  name: 'UploadPage',
  components: { AlertPanel, AppIcon, UploadDropzone, UploadQueueItem, WorkflowRail },
  data() {
    return {
      maxMb: MAX_UPLOAD_MB,
    }
  },
  computed: {
    ...mapState(useUploadStore, ['items', 'running', 'pendingCount']),
    ...mapState(useHealthStore, ['isOffline']),

    finishedCount(): number {
      return this.items.filter((item) => item.state === 'completed' || item.state === 'duplicate')
        .length
    },

    /**
     * The backend extracts and indexes in one synchronous request, so the rail
     * only distinguishes the transfer from the work that follows it.
     */
    activeStage(): PipelineStepKey | null {
      if (this.items.some((item) => item.state === 'processing')) return 'extract'
      if (this.items.some((item) => item.state === 'uploading' || item.state === 'queued')) {
        return 'upload'
      }
      return null
    },

    batchComplete(): boolean {
      return this.finishedCount > 0 && this.pendingCount === 0
    },

    railCaption(): string {
      if (this.activeStage === 'upload') return 'Sending files…'
      if (this.activeStage === 'extract') return 'Extracting and indexing…'
      if (this.batchComplete) {
        return `${this.finishedCount} document${this.finishedCount > 1 ? 's' : ''} ready to query`
      }
      return 'Drop a file below to start.'
    },
  },
  methods: {
    async addFiles(files: File[]) {
      const store = useUploadStore()
      store.enqueue(files)

      const documents = useDocumentsStore()
      await store.processQueue((document) => {
        documents.cacheDetail(document)
      })
      // Refresh the library once, after the whole batch, rather than per file.
      await documents.fetch()
      void documents.fetchStats()

      const failed = store.items.filter((item) => item.state === 'failed')
      if (failed.length) {
        useToastStore().error(
          `${failed.length} document${failed.length > 1 ? 's' : ''} could not be processed`,
          'Check the details below.',
        )
      }
    },

    remove(id: string) {
      useUploadStore().remove(id)
    },

    retry(id: string) {
      const documents = useDocumentsStore()
      useUploadStore().retry(id, (document) => documents.cacheDetail(document))
    },

    clearFinished() {
      useUploadStore().clearFinished()
    },

    open(item: UploadItem) {
      if (item.document) void this.$router.push(`/documents/${item.document.id}`)
    },

    ask(item: UploadItem) {
      if (!item.document) return
      useChatStore().startThread(item.document.id, item.document.filename)
      void this.$router.push({ path: '/chat', query: { document_id: String(item.document.id) } })
    },
  },
})
</script>

<template>
  <div class="page upload-page">
    <header class="page-header">
      <h2 class="page-title">Upload documents</h2>
      <p class="page-subtitle">
        Files are parsed on arrival and can be questioned as soon as they complete.
      </p>
    </header>

    <AlertPanel v-if="isOffline" tone="danger" title="Uploads are unavailable" class="page-alert">
      The backend is not reachable, so files cannot be processed.
    </AlertPanel>

    <section class="surface rail-card" aria-label="Pipeline progress">
      <WorkflowRail :active="activeStage" :complete="batchComplete" />
      <p class="rail-caption" :class="{ live: activeStage !== null }">{{ railCaption }}</p>
    </section>

    <UploadDropzone :disabled="isOffline" @files="addFiles" />

    <ul class="rules">
      <li><AppIcon name="check" :size="13" /> PDF and Word .docx</li>
      <li><AppIcon name="check" :size="13" /> Up to {{ maxMb }} MB per file</li>
      <li><AppIcon name="check" :size="13" /> Duplicates are detected by content, not filename</li>
      <li class="excluded"><AppIcon name="close" :size="13" /> Legacy .doc is not supported</li>
    </ul>

    <section v-if="items.length" class="queue">
      <div class="queue-header">
        <h3 class="section-label">
          Queue
          <span v-if="pendingCount" class="pending">· {{ pendingCount }} in progress</span>
        </h3>
        <button
          v-if="finishedCount"
          class="btn btn-ghost btn-sm"
          type="button"
          :disabled="running"
          @click="clearFinished"
        >
          Clear finished
        </button>
      </div>

      <TransitionGroup name="queue" tag="ul" class="queue-list">
        <UploadQueueItem
          v-for="item in items"
          :key="item.id"
          :item="item"
          @remove="remove"
          @retry="retry"
          @open="open"
          @ask="ask"
        />
      </TransitionGroup>
    </section>
  </div>
</template>

<style scoped>
.upload-page {
  max-width: 820px;
}

.page-alert {
  margin-bottom: 16px;
}

.rail-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
  padding: 15px 18px;
  margin-bottom: 16px;
}

.rail-caption {
  font-size: 12.5px;
  color: var(--text-tertiary);
  text-align: right;
  flex: 1;
  min-width: 200px;
}

.rail-caption.live {
  color: var(--accent);
  font-weight: 500;
}

.rules {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  margin-top: 14px;
}

.rules li {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: var(--text-tertiary);
}

.rules li svg {
  color: var(--green-600);
}

.rules li.excluded svg {
  color: var(--text-tertiary);
}

.queue {
  margin-top: 32px;
}

.queue-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 11px;
}

.pending {
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
  color: var(--accent);
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.queue-enter-active,
.queue-leave-active {
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
}

.queue-enter-from {
  opacity: 0;
  transform: translateY(-6px);
}

.queue-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

@media (max-width: 720px) {
  .rail-card {
    justify-content: flex-start;
  }

  .rail-caption {
    text-align: left;
  }
}
</style>
