<template>
  <div class="relative size-full overflow-x-hidden">
    <VirtualScroller
      :data="renderLogs"
      :size="44"
    >
      <template v-slot:before>
        <LogsCtrl />
      </template>
      <template v-slot="{ item }: { item: LogWithSeq }">
        <LogsCard :log="item" />
      </template>
    </VirtualScroller>
  </div>
</template>

<script setup lang="ts">
import VirtualScroller from '@/components/common/VirtualScroller.vue'
import LogsCtrl from '@/components/controls/LogsCtrl.tsx'
import LogsCard from '@/components/logs/LogsCard.vue'
import { logFilter, logFilterEnabled, logFilterRegex, logTypeFilter, logs } from '@/store/logs'
import type { LogWithSeq } from '@/types'
import { computed } from 'vue'

const renderLogs = computed(() => {
  let renderLogs = logs.value

  if (logFilter.value || logTypeFilter.value) {
    const regex = new RegExp(logFilter.value, 'i')

    renderLogs = logs.value.filter((log) => {
      if (logFilter.value && ![log.payload, log.time, log.type].some((i) => regex.test(i))) {
        return false
      }

      if (
        logTypeFilter.value &&
        !(log.payload.includes(logTypeFilter.value) || log.type === logTypeFilter.value)
      ) {
        return false
      }

      return true
    })
  }

  if (logFilterEnabled.value && logFilterRegex.value) {
    const hideRegex = new RegExp(logFilterRegex.value, 'i')
    renderLogs = renderLogs.filter((log) => {
      return ![log.payload, log.time, log.type].some((i) => hideRegex.test(i))
    })
  }

  return renderLogs
})
</script>
