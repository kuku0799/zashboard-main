/** 与 openclash_node_server_stable.py 的 to_clash_node 手动 JSON 字段对齐 */

export type ManualProto =
  | 'ss'
  | 'vmess'
  | 'vless'
  | 'trojan'
  | 'hysteria'
  | 'hysteria2'
  | 'tuic'
  | 'wireguard'
  | 'socks5'

export const MANUAL_PROTO_OPTIONS: { value: ManualProto; label: string }[] = [
  { value: 'ss', label: 'Shadowsocks' },
  { value: 'vmess', label: 'VMess' },
  { value: 'vless', label: 'VLESS' },
  { value: 'trojan', label: 'Trojan' },
  { value: 'hysteria', label: 'Hysteria' },
  { value: 'hysteria2', label: 'Hysteria2' },
  { value: 'tuic', label: 'TUIC' },
  { value: 'wireguard', label: 'WireGuard' },
  { value: 'socks5', label: 'SOCKS5' },
]

export function defaultPortForProto(type: ManualProto): number {
  if (type === 'ss') return 8388
  if (type === 'wireguard') return 51820
  return 443
}

export interface ManualNodeDraft {
  type: ManualProto
  name: string
  server: string
  port: string
  ssCipher: string
  ssPassword: string
  ssPlugin: string
  ssPluginOptsJson: string
  ssUdp: boolean
  vmessUuid: string
  vmessAlterId: string
  vmessCipher: string
  vmessNetwork: string
  vmessTls: boolean
  vmessSni: string
  vmessHost: string
  vmessPath: string
  vmessUdp: boolean
  vlessUuid: string
  vlessEncryption: string
  vlessFlow: string
  vlessNetwork: string
  vlessTlsMode: 'off' | 'tls' | 'reality'
  vlessSni: string
  vlessHost: string
  vlessPath: string
  vlessPublicKey: string
  vlessShortId: string
  vlessClientFingerprint: string
  vlessUdp: boolean
  trojanPassword: string
  trojanSni: string
  trojanNetwork: string
  trojanHost: string
  trojanPath: string
  trojanSkipCert: boolean
  trojanUdp: boolean
  hyAuth: string
  hySni: string
  hyProtocol: string
  hyObfs: string
  hyObfsPass: string
  hyUp: string
  hyDown: string
  hySkipCert: boolean
  hy2Password: string
  hy2Sni: string
  hy2Obfs: string
  hy2ObfsPass: string
  hy2Up: string
  hy2Down: string
  hy2Insecure: boolean
  hy2Alpn: string
  tuicUuid: string
  tuicPassword: string
  tuicSni: string
  tuicCongestion: string
  tuicUdpRelay: string
  tuicSkipCert: boolean
  tuicAlpn: string
  wgPub: string
  wgPrivate: string
  wgDns: string
  wgIp: string
  wgAllowed: string
  wgMtu: string
  skUser: string
  skPass: string
  skUdp: boolean
  skTls: boolean
  skSkipCert: boolean
  skSni: string
}

function parsePort(s: string, fallback: number): number {
  const n = parseInt(s, 10)
  if (!Number.isFinite(n) || n < 1 || n > 65535) return fallback
  return n
}

export function emptyManualDraft(type: ManualProto): ManualNodeDraft {
  const p = String(defaultPortForProto(type))
  return {
    type,
    name: '',
    server: '',
    port: p,
    ssCipher: 'aes-256-gcm',
    ssPassword: '',
    ssPlugin: '',
    ssPluginOptsJson: '',
    ssUdp: true,
    vmessUuid: '',
    vmessAlterId: '0',
    vmessCipher: 'auto',
    vmessNetwork: 'tcp',
    vmessTls: false,
    vmessSni: '',
    vmessHost: '',
    vmessPath: '',
    vmessUdp: true,
    vlessUuid: '',
    vlessEncryption: 'none',
    vlessFlow: '',
    vlessNetwork: 'tcp',
    vlessTlsMode: 'off',
    vlessSni: '',
    vlessHost: '',
    vlessPath: '',
    vlessPublicKey: '',
    vlessShortId: '',
    vlessClientFingerprint: '',
    vlessUdp: true,
    trojanPassword: '',
    trojanSni: '',
    trojanNetwork: 'tcp',
    trojanHost: '',
    trojanPath: '',
    trojanSkipCert: false,
    trojanUdp: true,
    hyAuth: '',
    hySni: '',
    hyProtocol: 'udp',
    hyObfs: '',
    hyObfsPass: '',
    hyUp: '',
    hyDown: '',
    hySkipCert: false,
    hy2Password: '',
    hy2Sni: '',
    hy2Obfs: '',
    hy2ObfsPass: '',
    hy2Up: '',
    hy2Down: '',
    hy2Insecure: false,
    hy2Alpn: '',
    tuicUuid: '',
    tuicPassword: '',
    tuicSni: '',
    tuicCongestion: 'bbr',
    tuicUdpRelay: 'native',
    tuicSkipCert: false,
    tuicAlpn: '',
    wgPub: '',
    wgPrivate: '',
    wgDns: '1.1.1.1',
    wgIp: '',
    wgAllowed: '',
    wgMtu: '',
    skUser: '',
    skPass: '',
    skUdp: true,
    skTls: false,
    skSkipCert: false,
    skSni: '',
  }
}

/** 生成 POST /add-nodes 的单条 node，与后端 to_clash_node 一致 */
export function manualDraftToNode(d: ManualNodeDraft): Record<string, unknown> {
  const name = d.name.trim()
  const server = d.server.trim()
  if (!name) throw new Error('请填写节点名称')
  if (!server) throw new Error('请填写服务器地址')
  const fb = defaultPortForProto(d.type)
  const port = parsePort(d.port, fb)

  switch (d.type) {
    case 'ss': {
      if (!d.ssPassword.trim()) throw new Error('请填写 SS 密码')
      const n: Record<string, unknown> = {
        name,
        type: 'ss',
        server,
        port,
        cipher: d.ssCipher.trim() || 'aes-256-gcm',
        password: d.ssPassword,
        udp: d.ssUdp,
      }
      if (d.ssPlugin.trim()) n.plugin = d.ssPlugin.trim()
      if (d.ssPluginOptsJson.trim()) {
        try {
          n['plugin-opts'] = JSON.parse(d.ssPluginOptsJson) as object
        } catch {
          throw new Error('SS 插件参数须为合法 JSON')
        }
      }
      return stripUndefined(n)
    }
    case 'vmess': {
      if (!d.vmessUuid.trim()) throw new Error('请填写 VMess UUID')
      return stripUndefined({
        name,
        type: 'vmess',
        server,
        port,
        uuid: d.vmessUuid.trim(),
        alterId: parseInt(d.vmessAlterId, 10) || 0,
        cipher: d.vmessCipher.trim() || 'auto',
        network: d.vmessNetwork.trim() || 'tcp',
        tls: d.vmessTls,
        sni: d.vmessSni.trim() || undefined,
        host: d.vmessHost.trim() || undefined,
        path: d.vmessPath.trim() || undefined,
        udp: d.vmessUdp,
      })
    }
    case 'vless': {
      if (!d.vlessUuid.trim()) throw new Error('请填写 VLESS UUID')
      const n: Record<string, unknown> = {
        name,
        type: 'vless',
        server,
        port,
        uuid: d.vlessUuid.trim(),
        network: d.vlessNetwork.trim() || 'tcp',
        udp: d.vlessUdp,
      }
      if (d.vlessEncryption.trim()) n.encryption = d.vlessEncryption.trim()
      if (d.vlessFlow.trim()) n.flow = d.vlessFlow.trim()
      if (d.vlessHost.trim()) n.host = d.vlessHost.trim()
      if (d.vlessPath.trim()) n.path = d.vlessPath.trim()
      if (d.vlessTlsMode === 'reality') {
        n.tls = true
        n.tls_type = 'reality'
        if (d.vlessSni.trim()) n.sni = d.vlessSni.trim()
        if (d.vlessPublicKey.trim()) n['public-key'] = d.vlessPublicKey.trim()
        if (d.vlessShortId.trim()) n['short-id'] = d.vlessShortId.trim()
        if (d.vlessClientFingerprint.trim()) n['client-fingerprint'] = d.vlessClientFingerprint.trim()
      } else if (d.vlessTlsMode === 'tls') {
        n.tls = true
        if (d.vlessSni.trim()) n.sni = d.vlessSni.trim()
        if (d.vlessClientFingerprint.trim()) n['client-fingerprint'] = d.vlessClientFingerprint.trim()
      } else {
        n.tls = false
      }
      return stripUndefined(n)
    }
    case 'trojan': {
      if (!d.trojanPassword.trim()) throw new Error('请填写 Trojan 密码')
      const n: Record<string, unknown> = {
        name,
        type: 'trojan',
        server,
        port,
        password: d.trojanPassword,
        sni: d.trojanSni.trim() || server,
        network: d.trojanNetwork.trim() || 'tcp',
        udp: d.trojanUdp,
      }
      if (d.trojanHost.trim()) n.host = d.trojanHost.trim()
      if (d.trojanPath.trim()) n.path = d.trojanPath.trim()
      if (d.trojanSkipCert) n['skip-cert-verify'] = true
      return stripUndefined(n)
    }
    case 'hysteria': {
      if (!d.hyAuth.trim()) throw new Error('请填写 Hysteria 认证串 auth')
      const n: Record<string, unknown> = {
        name,
        type: 'hysteria',
        server,
        port,
        auth: d.hyAuth.trim(),
        sni: d.hySni.trim() || server,
        protocol: d.hyProtocol.trim() || 'udp',
      }
      if (d.hyObfs.trim()) n.obfs = d.hyObfs.trim()
      if (d.hyObfsPass.trim()) n['obfs-password'] = d.hyObfsPass.trim()
      if (d.hyUp.trim()) n.up = d.hyUp.trim()
      if (d.hyDown.trim()) n.down = d.hyDown.trim()
      if (d.hySkipCert) n['skip-cert-verify'] = true
      return stripUndefined(n)
    }
    case 'hysteria2': {
      if (!d.hy2Password.trim()) throw new Error('请填写 Hysteria2 密码')
      const n: Record<string, unknown> = {
        name,
        type: 'hysteria2',
        server,
        port,
        password: d.hy2Password,
        sni: d.hy2Sni.trim() || server,
      }
      if (d.hy2Obfs.trim()) n.obfs = d.hy2Obfs.trim()
      if (d.hy2ObfsPass.trim()) n['obfs-password'] = d.hy2ObfsPass.trim()
      if (d.hy2Up.trim()) n.up = d.hy2Up.trim()
      if (d.hy2Down.trim()) n.down = d.hy2Down.trim()
      if (d.hy2Insecure) n.insecure = true
      if (d.hy2Alpn.trim()) n.alpn = d.hy2Alpn.trim()
      return stripUndefined(n)
    }
    case 'tuic': {
      if (!d.tuicUuid.trim()) throw new Error('请填写 TUIC UUID')
      const n: Record<string, unknown> = {
        name,
        type: 'tuic',
        server,
        port,
        uuid: d.tuicUuid.trim(),
        sni: d.tuicSni.trim() || server,
      }
      if (d.tuicPassword.trim()) n.password = d.tuicPassword
      if (d.tuicCongestion.trim()) n['congestion-controller'] = d.tuicCongestion.trim()
      if (d.tuicUdpRelay.trim()) n['udp-relay-mode'] = d.tuicUdpRelay.trim()
      if (d.tuicSkipCert) n['skip-cert-verify'] = true
      if (d.tuicAlpn.trim()) {
        n.alpn = d.tuicAlpn.split(',').map((s) => s.trim()).filter(Boolean)
      }
      return stripUndefined(n)
    }
    case 'wireguard': {
      if (!d.wgPub.trim()) throw new Error('请填写 WireGuard 公钥 public-key')
      const n: Record<string, unknown> = {
        name,
        type: 'wireguard',
        server,
        port,
        public_key: d.wgPub.trim(),
      }
      if (d.wgPrivate.trim()) n.private_key = d.wgPrivate.trim()
      if (d.wgDns.trim()) n.dns = d.wgDns.trim()
      if (d.wgIp.trim()) n.ip = d.wgIp.trim()
      if (d.wgAllowed.trim()) n['allowed-ips'] = d.wgAllowed.trim()
      if (d.wgMtu.trim()) {
        const m = parseInt(d.wgMtu, 10)
        if (Number.isFinite(m)) n.mtu = m
      }
      return stripUndefined(n)
    }
    case 'socks5': {
      const n: Record<string, unknown> = {
        name,
        type: 'socks5',
        server,
        port,
        udp: d.skUdp,
      }
      if (d.skUser.trim()) n.username = d.skUser.trim()
      if (d.skPass.trim()) n.password = d.skPass.trim()
      if (d.skTls) n.tls = true
      if (d.skSkipCert) n['skip-cert-verify'] = true
      if (d.skSni.trim()) n.sni = d.skSni.trim()
      return stripUndefined(n)
    }
    default:
      throw new Error('未知协议')
  }
}

function stripUndefined<T extends Record<string, unknown>>(o: T): T {
  for (const k of Object.keys(o)) {
    if (o[k] === undefined || o[k] === '') delete o[k]
  }
  return o
}
