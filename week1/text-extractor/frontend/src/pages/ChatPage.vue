<script lang="ts">
import { defineComponent } from 'vue'
import { mapState } from 'pinia'

import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatTurn from '@/components/chat/ChatTurn.vue'
import ThreadSidebar from '@/components/chat/ThreadSidebar.vue'
import AlertPanel from '@/components/ui/AlertPanel.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import SpinnerDot from '@/components/ui/SpinnerDot.vue'
import { useChatStore } from '@/stores/chat'
import { useDocumentsStore } from '@/stores/documents'
import { useHealthStore } from '@/stores/health'

export default defineComponent({
  name: 'ChatPage',
  components: {
    AlertPanel,
    AppIcon,
    ChatComposer,
    ChatTurn,
    EmptyState,
    SpinnerDot,
    ThreadSidebar,
  },
  computed: {
    ...mapState(useChatStore, ['activeThread', 'activeThreadId', 'startedThreads', 'sending']),
    ...mapState(useDocumentsStore, ['searchableDocuments', 'loading', 'total']),
    ...mapState(useHealthStore, ['isOffline']),

    messages() {
      return this.activeThread?.messages ?? []
    },

    scopeName(): string {
      return this.activeThread?.documentName ?? 'Entire library'
    },

    isScoped(): boolean {
      return this.activeThread?.documentId !== null && this.activeThread?.documentId !== undefined
    },

    hasNoDocuments(): boolean {
      return !this.loading && this.total === 0
    },

    /** Scope is locked once a thread has turns, so citations stay coherent. */
    scopeLocked(): boolean {
      return this.messages.length > 0
    },

    suggestions(): string[] {
      return this.isScoped
        ? [
            'What is this document about?',
            'Summarise the key points.',
            'What decisions or recommendations does it make?',
          ]
        : [
            'What topics do my documents cover?',
            'Which document mentions pricing?',
            'Summarise what I have uploaded so far.',
          ]
    },
  },
  watch: {
    messages: {
      deep: true,
      handler() {
        this.$nextTick(this.scrollToBottom)
      },
    },
  },
  created() {
    const documents = useDocumentsStore()
    if (!documents.items.length) void documents.fetch()
    this.applyRouteScope()
  },
  mounted() {
    this.$nextTick(this.scrollToBottom)
  },
  methods: {
    /** `/chat?document_id=3` opens a thread already scoped to that document. */
    applyRouteScope() {
      const raw = this.$route.query.document_id
      if (typeof raw !== 'string') return

      const documentId = Number(raw)
      if (!Number.isFinite(documentId)) return
      if (this.activeThread?.documentId === documentId) return

      const chat = useChatStore()
      const known = useDocumentsStore().items.find((item) => item.id === documentId)
      chat.startThread(documentId, known?.filename ?? `Document #${documentId}`)
    },

    send(question: string) {
      void useChatStore().send(question)
    },

    useSuggestion(question: string) {
      this.send(question)
    },

    newThread() {
      useChatStore().startThread(null, null)
      void this.$router.replace({ path: '/chat' })
    },

    selectThread(id: string) {
      useChatStore().selectThread(id)
    },

    deleteThread(id: string) {
      useChatStore().deleteThread(id)
    },

    updateScope(documentId: number | null) {
      const name = documentId
        ? useDocumentsStore().items.find((item) => item.id === documentId)?.filename ?? null
        : null
      useChatStore().setScope(documentId, name)
    },

    updateTopK(value: number) {
      useChatStore().setTopK(value)
    },

    scrollToBottom() {
      const element = this.$refs.scroller as HTMLElement | undefined
      if (element) element.scrollTop = element.scrollHeight
    },
  },
})
</script>

<template>
  <div class="chat-layout">
    <ThreadSidebar
      :threads="startedThreads"
      :active-id="activeThreadId"
      @select="selectThread"
      @delete="deleteThread"
      @new="newThread"
    />

    <section class="conversation">
      <header class="scope-bar">
        <span class="scope-chip" :class="{ scoped: isScoped }">
          <AppIcon :name="isScoped ? 'file-text' : 'library'" :size="13" />
          {{ scopeName }}
        </span>
        <span class="scope-hint">
          {{ isScoped ? 'Answers are limited to this document' : 'Answers can draw on every document' }}
        </span>
        <div class="spacer" />
        <RouterLink
          v-if="isScoped && activeThread?.documentId"
          class="btn btn-ghost btn-sm"
          :to="`/documents/${activeThread.documentId}`"
        >
          Open document
          <AppIcon name="chevron-right" :size="13" />
        </RouterLink>
      </header>

      <div ref="scroller" class="scroller">
        <div class="scroll-inner">
          <EmptyState
            v-if="hasNoDocuments"
            icon="upload"
            tone="accent"
            title="Upload a document to start asking questions"
            description="There is nothing to search yet."
          >
            <template #actions>
              <RouterLink class="btn btn-primary" to="/upload">
                <AppIcon name="upload" :size="15" />
                Upload a document
              </RouterLink>
            </template>
          </EmptyState>

          <EmptyState
            v-else-if="!messages.length"
            icon="chat"
            tone="accent"
            title="Ask anything about your documents"
            description="Every answer comes back with its sources."
          >
            <template #actions>
              <button
                v-for="suggestion in suggestions"
                :key="suggestion"
                class="btn btn-secondary btn-sm"
                type="button"
                @click="useSuggestion(suggestion)"
              >
                {{ suggestion }}
              </button>
            </template>
          </EmptyState>

          <div v-else class="turns">
            <ChatTurn v-for="message in messages" :key="message.id" :message="message" />

            <div v-if="sending" class="thinking">
              <SpinnerDot :size="15" />
              <span>Searching your documents…</span>
            </div>
          </div>
        </div>
      </div>

      <footer class="composer-bar">
        <AlertPanel v-if="isOffline" tone="danger" class="composer-alert">
          The backend is unreachable, so questions cannot be answered right now.
        </AlertPanel>

        <ChatComposer
          ref="composer"
          :documents="searchableDocuments"
          :document-id="activeThread?.documentId ?? null"
          :top-k="activeThread?.topK ?? 6"
          :sending="sending"
          :disabled="isOffline || hasNoDocuments"
          :scope-locked="scopeLocked"
          @send="send"
          @update:document-id="updateScope"
          @update:top-k="updateTopK"
        />
      </footer>
    </section>
  </div>
</template>

<style scoped>
.chat-layout {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.conversation {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.scope-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-surface);
}

.scope-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 320px;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  font-size: 12px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scope-chip.scoped {
  background: var(--accent-soft);
  border-color: var(--accent-soft-border);
  color: var(--accent);
}

.scope-hint {
  font-size: 11.5px;
  color: var(--text-tertiary);
}

.scroller {
  flex: 1;
  overflow-y: auto;
  scroll-behavior: smooth;
}

.scroll-inner {
  max-width: 780px;
  margin: 0 auto;
  padding: 24px 20px;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.turns {
  display: flex;
  flex-direction: column;
  gap: 26px;
  justify-content: flex-start;
  margin-top: auto;
}

.thinking {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  padding: 9px 13px;
  border-radius: var(--radius-md);
  background: var(--bg-muted);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 12.5px;
  align-self: flex-start;
}

.composer-bar {
  padding: 12px 20px 18px;
  border-top: 1px solid var(--border);
  background: var(--bg-surface);
}

.composer-alert {
  max-width: 780px;
  margin: 0 auto 10px;
}

.composer-bar > :deep(.composer) {
  max-width: 780px;
  margin: 0 auto;
}

@media (max-width: 640px) {
  .scope-hint {
    display: none;
  }

  .scroll-inner,
  .composer-bar {
    padding-left: 14px;
    padding-right: 14px;
  }
}
</style>
