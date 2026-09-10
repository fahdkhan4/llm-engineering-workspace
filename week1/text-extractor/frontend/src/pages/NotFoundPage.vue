<script lang="ts">
import { defineComponent } from 'vue'

import EmptyState from '@/components/ui/EmptyState.vue'

export default defineComponent({
  name: 'NotFoundPage',
  components: { EmptyState },
})
</script>

<template>
  <div class="page">
    <div class="surface">
      <EmptyState
        icon="search"
        title="Page not found"
        description="That page does not exist in this workspace."
      >
        <template #actions>
          <RouterLink class="btn btn-primary" to="/library">Back to library</RouterLink>
        </template>
      </EmptyState>
    </div>
  </div>
</template>
