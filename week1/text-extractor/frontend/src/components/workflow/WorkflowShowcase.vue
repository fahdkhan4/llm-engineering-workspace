<script lang="ts">
import { defineComponent } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'

import { PIPELINE_STEPS } from './pipeline'

/** The four stages, one line each. */
export default defineComponent({
  name: 'WorkflowShowcase',
  components: { AppIcon },
  data() {
    return {
      steps: PIPELINE_STEPS,
    }
  },
})
</script>

<template>
  <ol class="flow">
    <li v-for="(step, index) in steps" :key="step.key" class="stage">
      <div class="track" aria-hidden="true">
        <span class="node">
          <AppIcon :name="step.icon" :size="15" :stroke-width="1.9" />
        </span>
        <span class="line" />
      </div>

      <p class="label">
        <span class="ordinal">{{ index + 1 }}</span>
        {{ step.label }}
      </p>
      <p class="description">{{ step.description }}</p>
    </li>
  </ol>
</template>

<style scoped>
.flow {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 20px;
}

.stage {
  min-width: 0;
}

.track {
  display: flex;
  align-items: center;
  gap: 12px;
}

.node {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--brand-gradient);
  color: #fff;
  box-shadow: var(--brand-glow);
}

.line {
  flex: 1;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent-soft-border), transparent);
}

.stage:last-child .line {
  display: none;
}

.label {
  display: flex;
  align-items: baseline;
  gap: 7px;
  margin-top: 14px;
  font-size: 13.5px;
  font-weight: 600;
}

.ordinal {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
}

.description {
  margin-top: 5px;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text-secondary);
}

@media (max-width: 860px) {
  .flow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .stage:nth-child(2n) .line {
    display: none;
  }
}

@media (max-width: 520px) {
  .flow {
    grid-template-columns: 1fr;
    gap: 16px;
  }

  .stage:nth-child(2n) .line,
  .stage .line {
    display: none;
  }
}
</style>
