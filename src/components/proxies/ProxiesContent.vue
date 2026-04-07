<script setup lang="ts">
import { useCalculateMaxProxies } from '@/composables/proxiesScroll'
import { handlerProxySelect } from '@/store/proxies'
import { proxiesSimpleView } from '@/store/settings'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import DialogWrapper from '../common/DialogWrapper.vue'
import TextInput from '../common/TextInput.vue'
import ProxyNodeCard from './ProxyNodeCard.vue'
import ProxyNodeGrid from './ProxyNodeGrid.vue'

const { t } = useI18n()

const props = defineProps<{
  name: string
  now?: string
  renderProxies: string[]
}>()

const pickerOpen = ref(false)
const filterText = ref('')

watch(pickerOpen, (open) => {
  if (!open) {
    filterText.value = ''
  }
})

const { maxProxies } = useCalculateMaxProxies(
  props.renderProxies.length,
  props.renderProxies.indexOf(props.now ?? ''),
)
const proxies = computed(() => props.renderProxies.slice(0, maxProxies.value))

const quickNodes = computed(() => {
  const list = props.renderProxies
  const out: string[] = []
  if (list.includes('DIRECT')) {
    out.push('DIRECT')
  }
  const cur = props.now
  if (cur && list.includes(cur) && cur !== 'DIRECT') {
    out.push(cur)
  }
  return out
})

const filteredAll = computed(() => {
  const q = filterText.value.trim().toLowerCase()
  if (!q) {
    return props.renderProxies
  }
  return props.renderProxies.filter((n) => n.toLowerCase().includes(q))
})

const onPickInModal = (node: string) => {
  handlerProxySelect(props.name, node)
  pickerOpen.value = false
}
</script>

<template>
  <div
    v-if="proxiesSimpleView"
    class="flex flex-col gap-2"
  >
    <ProxyNodeGrid>
      <ProxyNodeCard
        v-for="node in quickNodes"
        :key="node"
        :name="node"
        :group-name="name"
        :active="node === now"
        @click.stop="handlerProxySelect(name, node)"
      />
    </ProxyNodeGrid>
    <button
      type="button"
      class="btn btn-outline btn-sm w-full"
      @click="pickerOpen = true"
    >
      {{ t('proxiesMoreNodes') }}
    </button>
    <DialogWrapper
      v-model="pickerOpen"
      :title="t('proxiesPickNodeTitle')"
      box-class="max-w-lg"
    >
      <TextInput
        v-model="filterText"
        class="mb-2 w-full"
        :placeholder="t('proxiesFilterNodes')"
        :clearable="true"
      />
      <div class="max-h-[60vh] overflow-y-auto">
        <ProxyNodeGrid>
          <ProxyNodeCard
            v-for="node in filteredAll"
            :key="node"
            :name="node"
            :group-name="name"
            :active="node === now"
            @click.stop="onPickInModal(node)"
          />
        </ProxyNodeGrid>
      </div>
    </DialogWrapper>
  </div>
  <ProxyNodeGrid v-else>
    <ProxyNodeCard
      v-for="node in proxies"
      :key="node"
      :name="node"
      :group-name="name"
      :active="node === now"
      @click.stop="handlerProxySelect(name, node)"
    />
  </ProxyNodeGrid>
</template>
