<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import AlertPanel from '@/components/ui/AlertPanel.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import type { SourceRef } from '@/types/api'
import type { ChatMessage } from '@/types/chat'
import { parseAnswer, type AnswerBlock } from '@/utils/citations'

import CitationMark from './CitationMark.vue'
import SourceCard from './SourceCard.vue'

const HIGHLIGHT_MS = 2400

export default defineComponent({
  name: 'ChatTurn',
  components: { AlertPanel, AppIcon, CitationMark, EmptyState, SourceCard },
  props: {
    message: { type: Object as PropType<ChatMessage>, required: true },
  },
  data() {
    return { focusedChunkId: null as number | null, highlightTimer: 0 }
  },
  computed: {
    isUser(): boolean {
      return this.message.role === 'user'
    },

    sources(): SourceRef[] {
      return this.message.sources ?? []
    },

    /**
     * `llm_configured: false` means `answer` holds the stub's explanation, not
     * a generated answer. Retrieval still ran, so the sources are real.
     */
    llmMissing(): boolean {
      return this.message.llmConfigured === false
    },

    noResults(): boolean {
      return !this.message.error && !this.llmMissing && this.sources.length === 0
    },

    /**
     * The answer as paragraphs, bullets and citation markers. Every `[n]` the
     * model wrote becomes a link to the passage it came from.
     */
    blocks(): AnswerBlock[] {
      return parseAnswer(this.message.content, this.sources)
    },

    cited(): Set<number> {
      const ids = new Set<number>()
      for (const block of this.blocks) {
        const lines = block.kind === 'list' ? block.items : [block.tokens]
        for (const tokens of lines) {
          for (const token of tokens) {
            if (token.source) ids.add(token.source.chunk_id)
          }
        }
      }
      return ids
    },
  },
  beforeUnmount() {
    window.clearTimeout(this.highlightTimer)
  },
  methods: {
    anchorId(source: SourceRef): string {
      return `cite-${this.message.id}-${source.chunk_id}`
    },

    /** Clicking a marker in the prose scrolls to its card and flashes it. */
    focusSource(source: SourceRef) {
      this.focusedChunkId = source.chunk_id
      void this.$nextTick(() => {
        document
          .getElementById(this.anchorId(source))
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      })
      window.clearTimeout(this.highlightTimer)
      this.highlightTimer = window.setTimeout(() => {
        this.focusedChunkId = null
      }, HIGHLIGHT_MS)
    },
  },
})
</script>

<template>
  <div class="turn" :class="isUser ? 'user' : 'assistant'">
    <div v-if="isUser" class="user-bubble">{{ message.content }}</div>

    <div v-else class="answer">
      <div class="answer-head">
        <span class="avatar">
          <AppIcon name="sparkle" :size="14" />
        </span>
        <span class="answer-label">Answer</span>
        <span v-if="message.model" class="model-tag mono">{{ message.model }}</span>
      </div>

      <AlertPanel v-if="message.error" tone="danger" title="This question could not be answered">
        {{ message.error }}
      </AlertPanel>

      <AlertPanel
        v-else-if="llmMissing"
        tone="warning"
        title="No answer was generated — the LLM layer is not configured"
      >
        Retrieval ran and found the passages below, but
        <span class="mono">llm/llm_client.py</span> is still a stub. The sources are real.
      </AlertPanel>

      <EmptyState
        v-else-if="noResults"
        icon="search"
        compact
        title="No relevant passages were found"
        tone="neutral"
        description="Try rephrasing the question or widening the scope."
      />

      <div v-else class="answer-body">
        <template v-for="(block, blockIndex) in blocks" :key="blockIndex">
          <ul v-if="block.kind === 'list'" class="answer-list">
            <li v-for="(item, itemIndex) in block.items" :key="itemIndex">
              <template v-for="(token, tokenIndex) in item" :key="tokenIndex">
                <CitationMark
                  v-if="token.source"
                  :source="token.source"
                  :active="focusedChunkId === token.source.chunk_id"
                  @select="focusSource"
                />
                <span v-else>{{ token.text }}</span>
              </template>
            </li>
          </ul>

          <p v-else class="answer-para" :class="{ caveat: block.kind === 'caveat' }">
            <AppIcon v-if="block.kind === 'caveat'" name="info" :size="13" class="caveat-icon" />
            <template v-for="(token, tokenIndex) in block.tokens" :key="tokenIndex">
              <CitationMark
                v-if="token.source"
                :source="token.source"
                :active="focusedChunkId === token.source.chunk_id"
                @select="focusSource"
              />
              <span v-else>{{ token.text }}</span>
            </template>
          </p>
        </template>
      </div>

      <section v-if="sources.length" class="sources">
        <div class="sources-head">
          <AppIcon name="quote" :size="13" />
          <span class="section-label">
            {{ sources.length }} source{{ sources.length > 1 ? 's' : '' }}
          </span>
          <span class="sources-hint">
            {{ cited.size ? 'click any number in the answer to jump to its passage' : 'grounding this answer' }}
          </span>
        </div>
        <div class="source-list">
          <SourceCard
            v-for="source in sources"
            :key="source.chunk_id"
            :source="source"
            :siblings="sources"
            :index="source.index"
            :anchor-id="anchorId(source)"
            :highlighted="focusedChunkId === source.chunk_id"
            :quoted="cited.has(source.chunk_id)"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.turn {
  display: flex;
  flex-direction: column;
}

.turn.user {
  align-items: flex-end;
}

.user-bubble {
  max-width: min(560px, 88%);
  padding: 10px 14px;
  border-radius: var(--radius-lg) var(--radius-lg) 4px var(--radius-lg);
  background: var(--brand-gradient);
  color: #fff;
  font-size: 13.5px;
  line-height: 1.6;
  overflow-wrap: anywhere;
  box-shadow: var(--brand-glow);
}

.answer {
  width: 100%;
}

.answer-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.avatar {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--brand-gradient);
  border: 1px solid transparent;
  color: #fff;
  box-shadow: var(--brand-glow);
}

.answer-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.model-tag {
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-muted);
  border: 1px solid var(--border);
  font-size: 10.5px;
  color: var(--text-tertiary);
}

.answer-body {
  font-size: 14px;
  line-height: 1.75;
  overflow-wrap: anywhere;
}

.answer-body > * + * {
  margin-top: 11px;
}

.answer-list {
  padding-left: 2px;
  list-style: none;
}

.answer-list li {
  position: relative;
  padding-left: 17px;
}

.answer-list li + li {
  margin-top: 6px;
}

.answer-list li::before {
  content: '';
  position: absolute;
  top: 0.72em;
  left: 3px;
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: var(--accent);
  opacity: 0.55;
}

.answer-para.caveat {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  padding: 8px 11px;
  border-left: 2px solid var(--border-strong);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  background: var(--bg-subtle);
  font-size: 13px;
  color: var(--text-tertiary);
}

.caveat-icon {
  flex-shrink: 0;
  margin-top: 4px;
}

.sources {
  margin-top: 18px;
  padding-top: 15px;
  border-top: 1px dashed var(--border);
}

.sources-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 11px;
  color: var(--text-tertiary);
  flex-wrap: wrap;
}

.sources-hint {
  font-size: 11.5px;
  color: var(--text-tertiary);
}

.source-list {
  display: flex;
  flex-direction: column;
  gap: 9px;
}
</style>
