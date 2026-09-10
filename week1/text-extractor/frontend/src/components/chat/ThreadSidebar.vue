<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'
import type { ChatThread } from '@/types/chat'
import { formatRelative, truncate } from '@/utils/format'

export default defineComponent({
  name: 'ThreadSidebar',
  components: { AppIcon },
  props: {
    threads: { type: Array as PropType<ChatThread[]>, required: true },
    activeId: { type: String as PropType<string | null>, default: null },
  },
  emits: ['select', 'delete', 'new'],
  methods: {
    formatRelative,

    lastQuestion(thread: ChatThread): string {
      const questions = thread.messages.filter((message) => message.role === 'user')
      const last = questions[questions.length - 1]
      return last ? truncate(last.content, 72) : 'No questions yet'
    },
  },
})
</script>

<template>
  <aside class="threads">
    <div class="threads-head">
      <p class="section-label">Conversations</p>
      <button class="btn btn-secondary btn-sm" type="button" @click="$emit('new')">
        <AppIcon name="plus" :size="14" />
        New
      </button>
    </div>

    <ul v-if="threads.length" class="thread-list">
      <li v-for="thread in threads" :key="thread.id">
        <button
          type="button"
          class="thread"
          :class="{ active: thread.id === activeId }"
          @click="$emit('select', thread.id)"
        >
          <span class="thread-title">{{ thread.title }}</span>
          <span class="thread-question">{{ lastQuestion(thread) }}</span>
          <span class="thread-foot">
            <span class="scope" :class="{ scoped: thread.documentId !== null }">
              <AppIcon :name="thread.documentId !== null ? 'file-text' : 'library'" :size="11" />
              {{ thread.documentName || 'Entire library' }}
            </span>
            <span class="time">{{ formatRelative(thread.updatedAt) }}</span>
          </span>
        </button>
        <button
          class="delete"
          type="button"
          :aria-label="`Delete conversation ${thread.title}`"
          @click.stop="$emit('delete', thread.id)"
        >
          <AppIcon name="close" :size="13" />
        </button>
      </li>
    </ul>

    <p v-else class="threads-empty">
      Conversations you start will be listed here.
    </p>

    <p class="threads-note">
      <AppIcon name="info" :size="12" />
      <span>
        Stored in this browser. The backend keeps the server-side thread but exposes no endpoint
        to list past conversations.
      </span>
    </p>
  </aside>
</template>

<style scoped>
.threads {
  display: flex;
  flex-direction: column;
  width: 244px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  background: var(--bg-subtle);
}

.threads-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 13px 12px;
  border-bottom: 1px solid var(--border);
}

.thread-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.thread-list li {
  position: relative;
}

.thread {
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: 100%;
  padding: 9px 10px;
  padding-right: 26px;
  border-radius: var(--radius);
  text-align: left;
  border: 1px solid transparent;
  transition: background var(--transition), border-color var(--transition);
}

.thread:hover {
  background: var(--bg-hover);
}

.thread.active {
  background: var(--bg-surface);
  border-color: var(--border);
  box-shadow: var(--shadow-xs);
}

.thread-title {
  font-size: 12.5px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thread-question {
  font-size: 11.5px;
  color: var(--text-tertiary);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.thread-foot {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 3px;
  font-size: 10.5px;
  color: var(--text-tertiary);
  min-width: 0;
}

.scope {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scope.scoped {
  color: var(--accent);
}

.time {
  margin-left: auto;
  flex-shrink: 0;
}

.delete {
  position: absolute;
  top: 8px;
  right: 6px;
  padding: 3px;
  border-radius: 4px;
  color: var(--text-tertiary);
  opacity: 0;
  transition: opacity var(--transition), color var(--transition);
}

li:hover .delete,
.delete:focus-visible {
  opacity: 1;
}

.delete:hover {
  color: var(--red-600);
  background: var(--red-50);
}

.threads-empty {
  flex: 1;
  padding: 20px 14px;
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.55;
}

.threads-note {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 11px 12px;
  border-top: 1px solid var(--border);
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-tertiary);
}

.threads-note svg {
  margin-top: 2px;
}

@media (max-width: 900px) {
  .threads {
    display: none;
  }
}
</style>
