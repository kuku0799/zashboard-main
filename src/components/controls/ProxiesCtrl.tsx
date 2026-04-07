import { disconnectByIdAPI, isSingBox, updateProxyProviderAPI } from '@/api'
import {
  addOpenClashChainProxy,
  addOpenClashNodesByNodes,
  addOpenClashNodesByUrls,
  defaultOpenClashNodeServerBaseUrl,
  deleteOpenClashNodes,
  listOpenClashNodes,
  updateOpenClashNodeServerScript,
  type OpenClashNodeInfo,
} from '@/api/openclashNodeServer'
import { renderGroups } from '@/composables/proxies'
import { useCtrlsBar } from '@/composables/useCtrlsBar'
import { PROXY_SORT_TYPE, PROXY_TAB_TYPE, ROUTE_NAME, SETTINGS_MENU_KEY } from '@/constant'
import { showNotification } from '@/helper/notification'
import {
  emptyManualDraft,
  manualDraftToNode,
  type ManualNodeDraft,
} from '@/helper/openclashManualNode'
import { getMinCardWidth } from '@/helper/utils'
import { configs, updateConfigs } from '@/store/config'
import { activeConnections } from '@/store/connections'
import {
  allProxiesLatencyTest,
  fetchProxies,
  hasSmartGroup,
  proxiesFilter,
  proxiesTabShow,
  proxyGroupList,
  proxyProviederList,
} from '@/store/proxies'
import {
  automaticDisconnection,
  collapseGroupMap,
  displayFinalOutbound,
  groupProxiesByProvider,
  hideUnavailableProxies,
  manageHiddenGroup,
  minProxyCardWidth,
  proxyCardSize,
  proxySortType,
  twoColumnProxyGroup,
  useSmartGroupSort,
} from '@/store/settings'
import {
  ArrowPathIcon,
  BoltIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  PlusIcon,
  TrashIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/vue/24/outline'
import { every } from 'lodash'
import { computed, defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import CtrlsBar from '../common/CtrlsBar.vue'
import DialogWrapper from '../common/DialogWrapper.vue'
import TextInput from '../common/TextInput.vue'
import OpenClashManualNodeForm from './OpenClashManualNodeForm'

export default defineComponent({
  name: 'ProxiesCtrl',
  setup() {
    const { t } = useI18n()
    const router = useRouter()
    const isUpgrading = ref(false)
    const isAllLatencyTesting = ref(false)
    const settingsModel = ref(false)
    const openClashNodeModal = ref(false)
    const nodeServerTab = ref<'add' | 'delete'>('add')
    const nodeServerBaseUrl = ref(
      localStorage.getItem('openclashNodeServer/baseUrl') || defaultOpenClashNodeServerBaseUrl(),
    )
    const nodeServerLoading = ref(false)
    const nodeServerUpdating = ref(false)
    const nodeServerNodes = ref<OpenClashNodeInfo[]>([])
    const selectedNodeNames = ref<string[]>([])
    const addUrlsText = ref('')
    const addSubscriptionUrl = ref('')
    const addMode = ref<'url' | 'manual' | 'chain'>('url')
    const chainTransitName = ref('')
    const chainExitName = ref('')
    const chainTransitFilter = ref('')
    const chainExitFilter = ref('')
    const chainApplyRelay = ref(false)
    const chainApplyDialer = ref(true)
    const manualDraft = ref<ManualNodeDraft>(emptyManualDraft('ss'))
    const lastAddResult = ref<{
      injected?: number
      skipped_invalid?: number
      skipped_duplicate?: number
      parse_errors?: string[]
    } | null>(null)

    const { isLargeCtrlsBar } = useCtrlsBar()
    const handlerClickUpdateAllProviders = async () => {
      if (isUpgrading.value) return
      isUpgrading.value = true
      try {
        await Promise.all(
          proxyProviederList.value.map((provider) => updateProxyProviderAPI(provider.name)),
        )
        await fetchProxies()
        isUpgrading.value = false
      } catch {
        await fetchProxies()
        isUpgrading.value = false
      }
    }

    const hasProviders = computed(() => {
      return proxyProviederList.value.length > 0
    })

    const defaultModes = ['direct', 'rule', 'global']
    const modeList = computed(() => {
      return configs.value?.['mode-list'] || configs.value?.['modes'] || defaultModes
    })
    const needTranslateModes = computed(() => {
      return every(modeList.value, (mode) => defaultModes.includes(mode.toLowerCase()))
    })

    const handlerModeChange = (e: Event) => {
      const mode = (e.target as HTMLSelectElement).value
      updateConfigs({ mode })
      if (isSingBox.value && automaticDisconnection.value) {
        activeConnections.value.forEach((connection) => {
          if (connection.rule.includes('clash_mode')) {
            disconnectByIdAPI(connection.id)
          }
        })
      }
    }

    const handlerClickLatencyTestAll = async () => {
      if (isAllLatencyTesting.value) return
      isAllLatencyTesting.value = true
      try {
        await allProxiesLatencyTest()
        isAllLatencyTesting.value = false
      } catch {
        isAllLatencyTesting.value = false
      }
    }

    const hasNotCollapsed = computed(() => {
      return renderGroups.value.some((name) => collapseGroupMap.value[name])
    })

    const handlerClickToggleCollapse = () => {
      collapseGroupMap.value = Object.fromEntries(
        renderGroups.value.map((name) => [name, !hasNotCollapsed.value]),
      )
    }

    const handlerResetProxyCardWidth = () => {
      minProxyCardWidth.value = getMinCardWidth(proxyCardSize.value)
    }

    const tabsWithNumbers = computed(() => {
      return Object.values(PROXY_TAB_TYPE).map((type) => {
        return {
          type,
          count:
            type === PROXY_TAB_TYPE.PROXIES
              ? proxyGroupList.value.length
              : proxyProviederList.value.length,
        }
      })
    })

    const persistNodeServerBaseUrl = () => {
      localStorage.setItem('openclashNodeServer/baseUrl', nodeServerBaseUrl.value.trim())
    }

    const refreshNodeServerNodes = async () => {
      nodeServerLoading.value = true
      try {
        persistNodeServerBaseUrl()
        const res = await listOpenClashNodes(nodeServerBaseUrl.value.trim())
        if (!res.ok) throw new Error(res.error || 'list nodes failed')
        nodeServerNodes.value = (res.nodes || []).filter((n) => n?.name)
      } finally {
        nodeServerLoading.value = false
      }
    }

    const filteredForChainTransit = computed(() => {
      const q = chainTransitFilter.value.trim().toLowerCase()
      const nodes = nodeServerNodes.value
      if (!q) return nodes
      return nodes.filter((n) => n.name.toLowerCase().includes(q))
    })
    const filteredForChainExit = computed(() => {
      const q = chainExitFilter.value.trim().toLowerCase()
      const nodes = nodeServerNodes.value
      if (!q) return nodes
      return nodes.filter((n) => n.name.toLowerCase().includes(q))
    })

    const openNodeManager = async (tab: 'add' | 'delete') => {
      nodeServerTab.value = tab
      openClashNodeModal.value = true
      lastAddResult.value = null
      if (tab === 'add') {
        addMode.value = 'url'
        addSubscriptionUrl.value = ''
        manualDraft.value = emptyManualDraft('ss')
        chainTransitName.value = ''
        chainExitName.value = ''
        chainTransitFilter.value = ''
        chainExitFilter.value = ''
        chainApplyRelay.value = false
        chainApplyDialer.value = true
      }
      if (tab === 'delete') {
        try {
          await refreshNodeServerNodes()
        } catch (e: unknown) {
          showNotification({
            content: errorMessage(e),
            type: 'alert-error',
          })
        }
      }
    }

    const parseUrlsFromText = (text: string) => {
      return text
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter(Boolean)
    }

    const errorMessage = (e: unknown) => {
      return String((e as { message?: string })?.message || e)
    }

    const formatNodeServerError = (e: unknown) => {
      const data = (e as { response?: { data?: { parse_errors?: string[]; error?: string } } })
        ?.response?.data
      const parseErrors =
        Array.isArray(data?.parse_errors) && data.parse_errors.length
          ? `\n${data.parse_errors.slice(0, 5).join('\n')}`
          : ''
      return String(data?.error || errorMessage(e)) + parseErrors
    }

    const handleAddByUrls = async () => {
      const urls = parseUrlsFromText(addUrlsText.value)
      if (urls.length === 0) {
        showNotification({ content: 'urls is empty', type: 'alert-warning' })
        return
      }
      nodeServerLoading.value = true
      lastAddResult.value = null
      try {
        persistNodeServerBaseUrl()
        const res = await addOpenClashNodesByUrls(nodeServerBaseUrl.value.trim(), urls)
        if (!res.ok) throw new Error(res.error || 'add nodes failed')
        lastAddResult.value = {
          injected: res.injected,
          skipped_invalid: res.skipped_invalid,
          skipped_duplicate: res.skipped_duplicate,
          parse_errors: res.parse_errors || [],
        }
        showNotification({
          content: `OK: injected ${res.injected ?? 0}, invalid ${res.skipped_invalid ?? 0}, dup ${
            res.skipped_duplicate ?? 0
          }`,
          type: 'alert-success',
          timeout: 4000,
        })
        addUrlsText.value = ''
        lastAddResult.value = null
        openClashNodeModal.value = false
        setTimeout(() => {
          fetchProxies()
        }, 1200)
      } catch (e: unknown) {
        showNotification({
          content: formatNodeServerError(e),
          type: 'alert-error',
          timeout: 5000,
        })
      } finally {
        nodeServerLoading.value = false
      }
    }

    const handleAddBySubscriptionUrl = async () => {
      const subUrl = addSubscriptionUrl.value.trim()
      if (!subUrl) {
        showNotification({ content: '??????', type: 'alert-warning' })
        return
      }
      nodeServerLoading.value = true
      lastAddResult.value = null
      try {
        persistNodeServerBaseUrl()
        const res = await addOpenClashNodesByUrls(nodeServerBaseUrl.value.trim(), [subUrl])
        if (!res.ok) {
          const detail = res.parse_errors?.length
            ? `\n${res.parse_errors.slice(0, 5).join('\n')}`
            : ''
          throw new Error((res.error || 'import subscription failed') + detail)
        }
        showNotification({
          content: `??????: injected ${res.injected ?? 0}, invalid ${res.skipped_invalid ?? 0}, dup ${res.skipped_duplicate ?? 0}`,
          type: 'alert-success',
          timeout: 4000,
        })
        addSubscriptionUrl.value = ''
        openClashNodeModal.value = false
        setTimeout(() => {
          fetchProxies()
        }, 1200)
      } catch (e: unknown) {
        showNotification({
          content: formatNodeServerError(e),
          type: 'alert-error',
          timeout: 5000,
        })
      } finally {
        nodeServerLoading.value = false
      }
    }

    const handleAddManual = async () => {
      nodeServerLoading.value = true
      lastAddResult.value = null
      try {
        const node = manualDraftToNode(manualDraft.value)
        persistNodeServerBaseUrl()
        const res = await addOpenClashNodesByNodes(nodeServerBaseUrl.value.trim(), [node])
        if (!res.ok) throw new Error(res.error || 'add nodes failed')
        lastAddResult.value = {
          injected: res.injected,
          skipped_invalid: res.skipped_invalid,
          skipped_duplicate: res.skipped_duplicate,
          parse_errors: res.parse_errors || [],
        }
        showNotification({
          content: `OK: injected ${res.injected ?? 0}, invalid ${res.skipped_invalid ?? 0}, dup ${
            res.skipped_duplicate ?? 0
          }`,
          type: 'alert-success',
          timeout: 4000,
        })
        const proto = manualDraft.value.type
        manualDraft.value = emptyManualDraft(proto)
        lastAddResult.value = null
        openClashNodeModal.value = false
        setTimeout(() => {
          fetchProxies()
        }, 1200)
      } catch (e: unknown) {
        showNotification({
          content: errorMessage(e),
          type: 'alert-error',
          timeout: 5000,
        })
      } finally {
        nodeServerLoading.value = false
      }
    }

    const handleAddChain = async () => {
      const tr = chainTransitName.value.trim()
      const ex = chainExitName.value.trim()
      if (!tr || !ex) {
        showNotification({ content: '??????????', type: 'alert-warning' })
        return
      }
      if (tr === ex) {
        showNotification({ content: '?????????', type: 'alert-warning' })
        return
      }
      if (!chainApplyRelay.value && !chainApplyDialer.value) {
        showNotification({ content: '???????????', type: 'alert-warning' })
        return
      }
      const mode = chainApplyRelay.value ? (chainApplyDialer.value ? 'both' : 'relay') : 'dialer'
      nodeServerLoading.value = true
      try {
        persistNodeServerBaseUrl()
        const res = await addOpenClashChainProxy(nodeServerBaseUrl.value.trim(), {
          transit_name: tr,
          exit_name: ex,
          mode,
        })
        if (!res.ok) throw new Error(res.error || 'add chain failed')
        showNotification({
          content:
            mode === 'both'
              ? 'relay ?? dialer-proxy ???'
              : mode === 'relay'
                ? 'relay ????'
                : res.dialer_applied
                  ? 'dialer-proxy ???'
                  : '?????',
          type: 'alert-success',
          timeout: 4000,
        })
        if (res.warnings?.length) {
          showNotification({
            content: res.warnings.join('\n'),
            type: 'alert-warning',
            timeout: 6000,
          })
        }
        lastAddResult.value = null
        openClashNodeModal.value = false
        setTimeout(() => {
          fetchProxies()
        }, 1200)
      } catch (e: unknown) {
        showNotification({
          content: errorMessage(e),
          type: 'alert-error',
          timeout: 5000,
        })
      } finally {
        nodeServerLoading.value = false
      }
    }

    const handleDeleteSelected = async () => {
      const names = selectedNodeNames.value.map((n) => n.trim()).filter(Boolean)
      if (names.length === 0) {
        showNotification({ content: 'no nodes selected', type: 'alert-warning' })
        return
      }
      nodeServerLoading.value = true
      try {
        persistNodeServerBaseUrl()
        const res = await deleteOpenClashNodes(nodeServerBaseUrl.value.trim(), names)
        if (!res.ok) throw new Error(res.error || 'delete nodes failed')
        showNotification({
          content: `OK: deleted ${res.deleted ?? 0}`,
          type: 'alert-success',
          timeout: 4000,
        })
        selectedNodeNames.value = []
        await refreshNodeServerNodes()
        setTimeout(() => {
          fetchProxies()
        }, 1200)
      } catch (e: unknown) {
        showNotification({
          content: errorMessage(e),
          type: 'alert-error',
          timeout: 5000,
        })
      } finally {
        nodeServerLoading.value = false
      }
    }

    const handleUpdateNodeServerScript = async () => {
      if (nodeServerUpdating.value) return
      nodeServerUpdating.value = true
      try {
        persistNodeServerBaseUrl()
        const res = await updateOpenClashNodeServerScript(nodeServerBaseUrl.value.trim())
        if (!res.ok) throw new Error(res.error || 'update script failed')
        showNotification({
          content: res.message || 'Script updated. Restart node server process to apply.',
          type: 'alert-success',
          timeout: 5000,
        })
      } catch (e: unknown) {
        showNotification({
          content: errorMessage(e),
          type: 'alert-error',
          timeout: 5000,
        })
      } finally {
        nodeServerUpdating.value = false
      }
    }

    return () => {
      const tabs = (
        <div
          role="tablist"
          class="tabs-box tabs tabs-xs"
        >
          {tabsWithNumbers.value.map(({ type, count }) => {
            return (
              <a
                role="tab"
                key={type}
                class={['tab', proxiesTabShow.value === type && 'tab-active']}
                onClick={() => (proxiesTabShow.value = type)}
              >
                {t(type)} ({count})
              </a>
            )
          })}
        </div>
      )
      const upgradeAllIcon = proxiesTabShow.value === PROXY_TAB_TYPE.PROVIDER && (
        <button
          class="btn btn-circle btn-sm"
          onClick={handlerClickUpdateAllProviders}
        >
          <ArrowPathIcon class={['h-4 w-4', isUpgrading.value && 'animate-spin']} />
        </button>
      )
      const modeSelect = configs.value && (
        <select
          class={['select select-sm', isLargeCtrlsBar.value ? 'min-w-40' : 'min-w-24']}
          v-model={configs.value.mode}
          onChange={handlerModeChange}
        >
          {modeList.value.map((mode) => {
            return (
              <option
                key={mode}
                value={mode}
              >
                {needTranslateModes.value ? t(mode.toLowerCase()) : mode}
              </option>
            )
          })}
        </select>
      )
      const sort = (
        <select
          class={['select select-sm']}
          v-model={proxySortType.value}
        >
          {Object.values(PROXY_SORT_TYPE).map((type) => {
            return (
              <option
                key={type}
                value={type}
              >
                {t(type)}
              </option>
            )
          })}
        </select>
      )

      const latencyTestAll = (
        <button
          class="btn btn-circle btn-sm"
          onClick={handlerClickLatencyTestAll}
        >
          {isAllLatencyTesting.value ? (
            <span class="loading loading-spinner loading-sm"></span>
          ) : (
            <BoltIcon class="h-4 w-4" />
          )}
        </button>
      )

      const toggleCollapseAll = (
        <button
          class={[
            'btn btn-circle btn-sm',
            twoColumnProxyGroup.value &&
              proxiesTabShow.value === PROXY_TAB_TYPE.PROXIES &&
              'max-sm:hidden',
          ]}
          onClick={handlerClickToggleCollapse}
        >
          {hasNotCollapsed.value ? (
            <ChevronUpIcon class="h-4 w-4" />
          ) : (
            <ChevronDownIcon class="h-4 w-4" />
          )}
        </button>
      )

      const searchInput = (
        <TextInput
          class={['w-32 flex-1', isLargeCtrlsBar.value && 'max-w-80']}
          v-model={proxiesFilter.value}
          placeholder={`${t('search')} | ${t('searchMultiple')}`}
          clearable={true}
        />
      )

      const settingsModal = (
        <>
          <button
            class="btn btn-circle btn-sm"
            onClick={() => (settingsModel.value = true)}
          >
            <WrenchScrewdriverIcon class="h-4 w-4" />
          </button>
          <DialogWrapper
            v-model={settingsModel.value}
            title={t('proxySettings')}
          >
            <div class="flex flex-col gap-4 p-2 text-sm">
              <div class="flex items-center gap-2">
                {t('sortBy')}
                {sort}
              </div>
              {hasSmartGroup.value && (
                <div class="flex items-center gap-2">
                  {t('useSmartGroupSort')}
                  <input
                    class="toggle"
                    type="checkbox"
                    v-model={useSmartGroupSort.value}
                  />
                </div>
              )}
              <div class="flex items-center gap-2">
                {t('groupProxiesByProvider')}
                <input
                  type="checkbox"
                  class="toggle"
                  v-model={groupProxiesByProvider.value}
                />
              </div>
              <div class="flex items-center gap-2">
                {t('unavailableProxy')}
                <input
                  type="checkbox"
                  class="toggle"
                  v-model={hideUnavailableProxies.value}
                />
              </div>
              <div class="flex items-center gap-2">
                {t('manageHiddenGroup')}
                <input
                  class="toggle"
                  type="checkbox"
                  v-model={manageHiddenGroup.value}
                />
              </div>
              <div class="flex items-center gap-2">
                {t('automaticDisconnection')}
                <input
                  class="toggle"
                  type="checkbox"
                  v-model={automaticDisconnection.value}
                />
              </div>
              <div class="flex items-center gap-2">
                {t('displayFinalOutbound')}
                <input
                  class="toggle"
                  type="checkbox"
                  v-model={displayFinalOutbound.value}
                />
              </div>
              <div class="flex items-center gap-2">
                {t('minProxyCardWidth')}
                <div class="join">
                  <input
                    class="input input-sm join-item w-20"
                    type="number"
                    v-model={minProxyCardWidth.value}
                  />
                  <button
                    class="btn join-item btn-sm"
                    onClick={handlerResetProxyCardWidth}
                  >
                    {t('reset')}
                  </button>
                </div>
              </div>
              <div class="divider m-0"></div>
              <button
                class="btn btn-block"
                onClick={() => {
                  settingsModel.value = false
                  router.push({
                    name: ROUTE_NAME.settings,
                    query: { scrollTo: SETTINGS_MENU_KEY.proxies },
                  })
                }}
              >
                {t('moreSettings')}
              </button>
            </div>
          </DialogWrapper>
        </>
      )

      const nodeManagerButtons = (
        <>
          <button
            class="btn btn-circle btn-sm"
            title="Add nodes (OpenClash)"
            onClick={() => openNodeManager('add')}
          >
            <PlusIcon class="h-4 w-4" />
          </button>
          <button
            class="btn btn-circle btn-sm"
            title="Delete nodes (OpenClash)"
            onClick={() => openNodeManager('delete')}
          >
            <TrashIcon class="h-4 w-4" />
          </button>
          <DialogWrapper
            v-model={openClashNodeModal.value}
            title="OpenClash Nodes"
            boxClass="max-w-xl w-[min(100vw-1rem,36rem)]"
          >
            <div class="flex flex-col gap-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] text-sm">
              <section class="rounded-box border-base-300/30 bg-base-200/35 border p-2.5 shadow-sm">
                <div class="text-base-content/50 mb-1.5 text-[11px] font-medium tracking-wide uppercase">
                  Node server
                </div>
                <div class="join join-vertical sm:join-horizontal w-full min-w-0">
                  <input
                    class="input input-bordered input-sm join-item min-h-11 w-full min-w-0 flex-1 sm:min-h-9"
                    value={nodeServerBaseUrl.value}
                    onInput={(e) =>
                      (nodeServerBaseUrl.value = (e.target as HTMLInputElement).value)
                    }
                    onBlur={() => persistNodeServerBaseUrl()}
                    placeholder={defaultOpenClashNodeServerBaseUrl()}
                    aria-label="OpenClash node server base URL"
                  />
                  <button
                    type="button"
                    class="btn btn-neutral btn-sm join-item min-h-11 px-4 sm:min-h-9"
                    disabled={nodeServerLoading.value || nodeServerUpdating.value}
                    onClick={() => refreshNodeServerNodes().catch(() => {})}
                    aria-label="Test connection to node server"
                  >
                    {nodeServerLoading.value ? (
                      <span class="loading loading-spinner loading-xs"></span>
                    ) : (
                      'Test'
                    )}
                  </button>
                  <button
                    type="button"
                    class="btn btn-secondary btn-sm join-item min-h-11 px-4 sm:min-h-9"
                    disabled={nodeServerLoading.value || nodeServerUpdating.value}
                    onClick={() => handleUpdateNodeServerScript()}
                    aria-label="Update openclash_node_server_stable.py"
                  >
                    {nodeServerUpdating.value ? (
                      <span class="loading loading-spinner loading-xs"></span>
                    ) : (
                      'Update Script'
                    )}
                  </button>
                </div>
              </section>

              <div
                role="tablist"
                class="tabs tabs-boxed tabs-sm w-full justify-start gap-0"
              >
                <a
                  role="tab"
                  class={[
                    'tab min-h-11 flex-1 px-3 sm:min-h-9 sm:flex-none',
                    nodeServerTab.value === 'add' && 'tab-active',
                  ]}
                  onClick={() => (nodeServerTab.value = 'add')}
                >
                  Add
                </a>
                <a
                  role="tab"
                  class={[
                    'tab min-h-11 flex-1 px-3 sm:min-h-9 sm:flex-none',
                    nodeServerTab.value === 'delete' && 'tab-active',
                  ]}
                  onClick={() => {
                    nodeServerTab.value = 'delete'
                    refreshNodeServerNodes().catch(() => {})
                  }}
                >
                  Delete
                </a>
              </div>

              {nodeServerTab.value === 'add' ? (
                <div class="flex flex-col gap-3">
                  <div class="tabs tabs-box tabs-sm w-full justify-start">
                    <a
                      role="tab"
                      class={[
                        'tab min-h-11 flex-1 sm:min-h-9 sm:flex-none',
                        addMode.value === 'url' && 'tab-active',
                      ]}
                      onClick={() => (addMode.value = 'url')}
                    >
                      URL ??
                    </a>
                    <a
                      role="tab"
                      class={[
                        'tab min-h-11 flex-1 sm:min-h-9 sm:flex-none',
                        addMode.value === 'manual' && 'tab-active',
                      ]}
                      onClick={() => (addMode.value = 'manual')}
                    >
                      ????
                    </a>
                    <a
                      role="tab"
                      class={[
                        'tab min-h-11 flex-1 sm:min-h-9 sm:flex-none',
                        addMode.value === 'chain' && 'tab-active',
                      ]}
                      onClick={() => {
                        addMode.value = 'chain'
                        refreshNodeServerNodes().catch(() => {})
                      }}
                    >
                      ????
                    </a>
                  </div>
                  {addMode.value === 'url' ? (
                    <>
                      <div class="rounded-box border-base-300/40 bg-base-200/40 border p-2">
                        <div class="text-base-content/70 mb-1 text-xs">??????</div>
                        <div class="join w-full">
                          <input
                            class="input input-bordered input-sm join-item flex-1"
                            value={addSubscriptionUrl.value}
                            onInput={(e) =>
                              (addSubscriptionUrl.value = (e.target as HTMLInputElement).value)
                            }
                            placeholder="https://example.com/sub?token=..."
                          />
                          <button
                            type="button"
                            class="btn btn-primary btn-sm join-item"
                            disabled={nodeServerLoading.value}
                            onClick={() => handleAddBySubscriptionUrl()}
                          >
                            ????
                          </button>
                        </div>
                      </div>
                      <textarea
                        class="textarea textarea-bordered min-h-32 w-full text-sm"
                        value={addUrlsText.value}
                        onInput={(e) =>
                          (addUrlsText.value = (e.target as HTMLTextAreaElement).value)
                        }
                        placeholder={'??????\nvless://? / vmess://? / ss://?'}
                        aria-label="Subscription URLs, one per line"
                      ></textarea>
                      <button
                        type="button"
                        class="btn btn-primary min-h-11 w-full sm:min-h-10"
                        disabled={nodeServerLoading.value}
                        onClick={() => handleAddByUrls()}
                      >
                        {nodeServerLoading.value ? (
                          <span class="loading loading-spinner loading-sm"></span>
                        ) : (
                          '??'
                        )}
                      </button>
                    </>
                  ) : addMode.value === 'manual' ? (
                    <>
                      <OpenClashManualNodeForm
                        modelValue={manualDraft.value}
                        onUpdate:modelValue={(v: ManualNodeDraft) => (manualDraft.value = v)}
                      />
                      <button
                        type="button"
                        class="btn btn-primary min-h-11 w-full sm:min-h-10"
                        disabled={nodeServerLoading.value}
                        onClick={() => handleAddManual()}
                      >
                        {nodeServerLoading.value ? (
                          <span class="loading loading-spinner loading-sm"></span>
                        ) : (
                          '??'
                        )}
                      </button>
                    </>
                  ) : (
                    <>
                      <p class="text-base-content/60 text-xs">
                        ?????? proxies ??????????????? relay ?? dialer-proxy?
                      </p>
                      <div class="rounded-box border-base-300/40 bg-base-200/40 border p-2">
                        <div class="text-base-content/70 mb-2 text-xs">????</div>
                        <label class="mb-2 flex items-center gap-2 text-sm">
                          <input
                            class="checkbox checkbox-sm"
                            type="checkbox"
                            checked={chainApplyRelay.value}
                            onChange={(e) =>
                              (chainApplyRelay.value = (e.target as HTMLInputElement).checked)
                            }
                          />
                          <span>?? relay ?</span>
                        </label>
                        <label class="flex items-center gap-2 text-sm">
                          <input
                            class="checkbox checkbox-sm"
                            type="checkbox"
                            checked={chainApplyDialer.value}
                            onChange={(e) =>
                              (chainApplyDialer.value = (e.target as HTMLInputElement).checked)
                            }
                          />
                          <span>?? dialer-proxy</span>
                        </label>
                      </div>
                      <div class="flex flex-col gap-1">
                        <span class="text-base-content/70 text-xs">??</span>
                        <input
                          class="input input-bordered input-sm"
                          value={chainTransitFilter.value}
                          onInput={(e) =>
                            (chainTransitFilter.value = (e.target as HTMLInputElement).value)
                          }
                          placeholder="?????"
                        />
                        <select
                          class="select select-bordered select-sm w-full"
                          value={chainTransitName.value}
                          onChange={(e) =>
                            (chainTransitName.value = (e.target as HTMLSelectElement).value)
                          }
                        >
                          <option value="">??????</option>
                          {filteredForChainTransit.value.map((n) => (
                            <option
                              key={`t-${n.name}`}
                              value={n.name}
                            >
                              {n.name}
                              {n.type ? ` (${n.type})` : ''}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div class="flex flex-col gap-1">
                        <span class="text-base-content/70 text-xs">??</span>
                        <input
                          class="input input-bordered input-sm"
                          value={chainExitFilter.value}
                          onInput={(e) =>
                            (chainExitFilter.value = (e.target as HTMLInputElement).value)
                          }
                          placeholder="?????"
                        />
                        <select
                          class="select select-bordered select-sm w-full"
                          value={chainExitName.value}
                          onChange={(e) =>
                            (chainExitName.value = (e.target as HTMLSelectElement).value)
                          }
                        >
                          <option value="">??????</option>
                          {filteredForChainExit.value.map((n) => (
                            <option
                              key={`e-${n.name}`}
                              value={n.name}
                            >
                              {n.name}
                              {n.type ? ` (${n.type})` : ''}
                            </option>
                          ))}
                        </select>
                      </div>
                      <button
                        type="button"
                        class="btn btn-primary min-h-11 w-full sm:min-h-10"
                        disabled={nodeServerLoading.value || nodeServerNodes.value.length === 0}
                        onClick={() => handleAddChain()}
                      >
                        {nodeServerLoading.value ? (
                          <span class="loading loading-spinner loading-sm"></span>
                        ) : (
                          '??????'
                        )}
                      </button>
                    </>
                  )}
                  {lastAddResult.value && (
                    <div class="flex flex-col gap-2">
                      <div class="alert alert-success text-sm shadow-none">
                        <div class="flex flex-col gap-0.5">
                          <span>injected: {lastAddResult.value.injected ?? 0}</span>
                          <span>invalid: {lastAddResult.value.skipped_invalid ?? 0}</span>
                          <span>duplicate: {lastAddResult.value.skipped_duplicate ?? 0}</span>
                        </div>
                      </div>
                      {lastAddResult.value.parse_errors?.length ? (
                        <div class="alert alert-warning text-sm shadow-none">
                          <div class="mb-1 text-xs font-medium">parse_errors</div>
                          <div class="bg-base-100/50 max-h-36 overflow-y-auto rounded-md p-2 font-mono text-xs break-all whitespace-pre-wrap">
                            {lastAddResult.value.parse_errors.join('\n')}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
              ) : (
                <div class="flex flex-col gap-4">
                  <div class="flex items-center justify-between gap-2">
                    <div class="text-base-content/70 text-xs font-medium">
                      Nodes ({nodeServerNodes.value.length})
                    </div>
                    <button
                      type="button"
                      class="btn btn-ghost btn-sm min-h-11 sm:min-h-9"
                      disabled={nodeServerLoading.value}
                      onClick={() => refreshNodeServerNodes().catch(() => {})}
                      aria-label="Refresh node list"
                    >
                      {nodeServerLoading.value ? (
                        <span class="loading loading-spinner loading-xs"></span>
                      ) : (
                        'Refresh'
                      )}
                    </button>
                  </div>
                  <div class="rounded-box border-base-300/40 bg-base-200/50 max-h-[min(50vh,18rem)] overflow-y-auto border p-2 sm:max-h-72">
                    {nodeServerNodes.value.length === 0 ? (
                      <div class="text-base-content/50 py-4 text-center text-sm">empty</div>
                    ) : (
                      <div class="flex flex-col">
                        {nodeServerNodes.value.map((n) => {
                          const checked = selectedNodeNames.value.includes(n.name)
                          return (
                            <label
                              key={n.name}
                              class="active:bg-base-300/30 flex min-h-11 cursor-pointer items-center gap-3 rounded-lg px-1 py-1 sm:min-h-9"
                            >
                              <input
                                type="checkbox"
                                class="checkbox checkbox-sm"
                                checked={checked}
                                onChange={(e) => {
                                  const isChecked = (e.target as HTMLInputElement).checked
                                  if (isChecked) {
                                    selectedNodeNames.value = Array.from(
                                      new Set([...selectedNodeNames.value, n.name]),
                                    )
                                  } else {
                                    selectedNodeNames.value = selectedNodeNames.value.filter(
                                      (x) => x !== n.name,
                                    )
                                  }
                                }}
                              />
                              <span class="min-w-0 flex-1 truncate text-sm">
                                {n.name}
                                {n.type ? ` (${n.type})` : ''}
                              </span>
                            </label>
                          )
                        })}
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    class="btn btn-error min-h-11 w-full sm:min-h-10"
                    disabled={nodeServerLoading.value || selectedNodeNames.value.length === 0}
                    onClick={() => handleDeleteSelected()}
                    aria-label={`Delete selected nodes, count ${selectedNodeNames.value.length}`}
                  >
                    {nodeServerLoading.value ? (
                      <span class="loading loading-spinner loading-sm"></span>
                    ) : (
                      `Delete (${selectedNodeNames.value.length})`
                    )}
                  </button>
                </div>
              )}
            </div>
          </DialogWrapper>
        </>
      )

      const content = !isLargeCtrlsBar.value ? (
        <div class="flex flex-col gap-2 p-2">
          {hasProviders.value && (
            <div class="flex gap-2">
              {tabs}
              {upgradeAllIcon}
            </div>
          )}
          <div class="flex w-full gap-2">
            {modeSelect}
            {searchInput}
            {nodeManagerButtons}
            {settingsModal}
            {toggleCollapseAll}
            {latencyTestAll}
          </div>
        </div>
      ) : (
        <div class="flex gap-2 p-2">
          {hasProviders.value && tabs}
          {modeSelect}
          <div class="flex flex-1">{searchInput}</div>
          {upgradeAllIcon}
          {nodeManagerButtons}
          {settingsModal}
          {toggleCollapseAll}
          {latencyTestAll}
        </div>
      )

      return <CtrlsBar>{content}</CtrlsBar>
    }
  },
})
