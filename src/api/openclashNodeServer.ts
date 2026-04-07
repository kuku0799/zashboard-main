import axios from 'axios'

export type OpenClashNodeInfo = {
  name: string
  type?: string
  server?: string
  port?: number
}

type ListNodesResponse = {
  ok: boolean
  nodes?: OpenClashNodeInfo[]
  count?: number
  error?: string
}

type AddNodesResponse = {
  ok: boolean
  injected?: number
  skipped_invalid?: number
  skipped_duplicate?: number
  parse_errors?: string[]
  error?: string
}

type DeleteNodesResponse = {
  ok: boolean
  deleted?: number
  not_found?: string[]
  groups_updated?: number
  error?: string
}

type UpdateSelfScriptResponse = {
  ok: boolean
  updated?: boolean
  script_url?: string
  script_path?: string
  backup_path?: string
  need_restart?: boolean
  message?: string
  error?: string
}

export type ChainProxyMode = 'relay' | 'dialer' | 'both'

export type AddChainRequest = {
  transit_name: string
  exit_name: string
  mode?: ChainProxyMode
  chain_group_name?: string
}

type AddChainResponse = {
  ok: boolean
  applied_mode?: ChainProxyMode
  relay_group_name?: string | null
  dialer_applied?: boolean
  warnings?: string[]
  error?: string
}

const normalizeBaseUrl = (baseUrl: string) => {
  return baseUrl.replace(/\/+$/, '')
}

const createClient = (baseUrl: string) => {
  return axios.create({
    baseURL: normalizeBaseUrl(baseUrl),
    headers: { 'Content-Type': 'application/json' },
    timeout: 30000,
  })
}

export const defaultOpenClashNodeServerBaseUrl = () => {
  return `http://${location.hostname}:8001`
}

export const listOpenClashNodes = async (baseUrl: string) => {
  const client = createClient(baseUrl)
  const { data } = await client.get<ListNodesResponse>('/list-nodes')
  return data
}

export const addOpenClashNodesByUrls = async (baseUrl: string, urls: string[]) => {
  const client = createClient(baseUrl)
  try {
    const { data } = await client.post<AddNodesResponse>('/add-nodes', { urls })
    return data
  } catch (e: unknown) {
    if (axios.isAxiosError<AddNodesResponse>(e) && e.response?.data) return e.response.data
    throw e
  }
}

/** 手动填写的节点 JSON，与 openclash_node_server_stable.py 的 to_clash_node 一致 */
export const addOpenClashNodesByNodes = async (
  baseUrl: string,
  nodes: Record<string, unknown>[],
) => {
  const client = createClient(baseUrl)
  try {
    const { data } = await client.post<AddNodesResponse>('/add-nodes', { nodes })
    return data
  } catch (e: unknown) {
    if (axios.isAxiosError<AddNodesResponse>(e) && e.response?.data) return e.response.data
    throw e
  }
}

export const deleteOpenClashNodes = async (baseUrl: string, node_names: string[]) => {
  const client = createClient(baseUrl)
  const { data } = await client.post<DeleteNodesResponse>('/delete-nodes', { node_names })
  return data
}

export const updateOpenClashNodeServerScript = async (baseUrl: string, script_url?: string) => {
  const client = createClient(baseUrl)
  const payload = script_url?.trim() ? { script_url: script_url.trim() } : {}
  const { data } = await client.post<UpdateSelfScriptResponse>('/update-self-script', payload)
  return data
}

/** 链式代理：relay 组 + 可选 dialer-proxy（需 Clash Meta） */
export const addOpenClashChainProxy = async (baseUrl: string, body: AddChainRequest) => {
  const client = createClient(baseUrl)
  const payload = {
    transit_name: body.transit_name,
    exit_name: body.exit_name,
    mode: body.mode ?? 'both',
    ...(body.chain_group_name?.trim() ? { chain_group_name: body.chain_group_name.trim() } : {}),
  }

  try {
    const { data } = await client.post<AddChainResponse>('/add-chain', payload)
    return data
  } catch (e: unknown) {
    if (axios.isAxiosError(e) && e.response?.status === 404) {
      try {
        const { data } = await client.post<AddChainResponse>('/chain-proxy', payload)
        return data
      } catch (e2: unknown) {
        if (axios.isAxiosError(e2) && e2.response?.status === 404) {
          throw new Error('后端不支持链式代理接口，请更新 openclash_node_server_stable.py')
        }
        throw e2
      }
    }
    throw e
  }
}
