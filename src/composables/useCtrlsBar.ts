import { useCurrentElement, useElementSize } from '@vueuse/core'
import { computed } from 'vue'

export function useCtrlsBar(width: number = 720) {
  const element = useCurrentElement()
  const { width: ctrlsBarWidth } = useElementSize(element)
  const isLargeCtrlsBar = computed(() => {
    return ctrlsBarWidth.value > width
  })

  return {
    isLargeCtrlsBar,
  }
}
