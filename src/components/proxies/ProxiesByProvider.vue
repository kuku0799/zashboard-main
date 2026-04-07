<script setup lang="ts">
import { useCalculateMaxProxies } from '@/composables/proxiesScroll'
import { handlerProxySelect, proxyMap, proxyProviederList } from '@/store/proxies'
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
  now: string
  renderProxies: string[]
}>()

const pickerOpen = ref(false)
const filterText = ref('')

watch(pickerOpen, (open) => {
  if (!open) {
    filterText.value = ''
  }
})

const groupedProxies = computed(() => {
  const groupdProixes: Record<string, string[]> = {}
  const providerKeys: string[] = []

  for (const proxy of props.renderProxies) {
    const proxyNode = proxyMap.value[proxy]
    const providerName =
      proxyNode['provider-name'] ||
      (proxyProviederList.value.find((group) => group.proxies.find((node) => node.name === proxy))
        ?.name ??
        '')

    if (groupdProixes[providerName]) {
      groupdProixes[providerName].push(proxy)
    } else {
      if (providerName === '') {
        providerKeys.unshift('')
      } else {
        providerKeys.push(providerName)
      }

      groupdProixes[providerName] = [proxy]
    }
  }

  return providerKeys.map((providerName) => ({
    providerName,
    proxies: groupdProixes[providerName],
  }))
})

const activeIndex = computed(() =>
  groupedProxies.value.reduce((acc, { proxies }) => {
    const index = proxies.indexOf(props.now)

    if (index !== -1) {
      return acc + index
    }
    return acc + proxies.length
  }, 0),
)

const { maxProxies } = useCalculateMaxProxies(props.renderProxies.length, activeIndex.value)

const truncatedProxies = computed(() => {
  let displayCount = 0
  const truncatedProxies: { providerName: string; proxies: string[] }[] = []

  for (const { providerName, proxies } of groupedProxies.value) {
    if (displayCount + proxies.length > maxProxies.value) {
      truncatedProxies.push({
        providerName,
        proxies: proxies.slice(0, maxProxies.value - displayCount),
      })
      break
    } else {
      truncatedProxies.push({ providerName, proxies })
      displayCount += proxies.length
    }
  }
  return truncatedProxies
})

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

const filteredGrouped = computed(() => {
  const q = filterText.value.trim().toLowerCase()
  const groups = groupedProxies.value
  if (!q) {
    return groups
  }
  return groups
    .map(({ providerName, proxies }) => ({
      providerName,
      proxies: proxies.filter((n) => n.toLowerCase().includes(q)),
    }))
    .filter((g) => g.proxies.length > 0)
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
        <div
          v-for="({ providerName, proxies }, index) in filteredGrouped"
          :key="index"
        >
          <p
            v-if="providerName !== ''"
            class="my-2 text-sm font-semibold"
          >
            {{ providerName }}
          </p>
          <ProxyNodeGrid>
            <ProxyNodeCard
              v-for="node in proxies"
              :key="node"
              :name="node"
              :group-name="name"
              :active="node === now"
              @click.stop="onPickInModal(node)"
            />
          </ProxyNodeGrid>
        </div>
      </div>
    </DialogWrapper>
  </div>
  <div
    v-else
    class="flex flex-col gap-2"
  >
    <div
      v-for="({ providerName, proxies }, index) in truncatedProxies"
      :key="index"
    >
      <p
        class="my-2 text-sm font-semibold"
        v-if="providerName !== ''"
      >
        {{ providerName }}
      </p>
      <ProxyNodeGrid>
        <ProxyNodeCard
          v-for="node in proxies"
          :key="node"
          :name="node"
          :group-name="name"
          :active="node === now"
          @click.stop="handlerProxySelect(name, node)"
        />
      </ProxyNodeGrid>
    </div>
  </div>
</template>
