import {
  MANUAL_PROTO_OPTIONS,
  defaultPortForProto,
  emptyManualDraft,
  type ManualNodeDraft,
  type ManualProto,
} from '@/helper/openclashManualNode'
import { defineComponent, type PropType } from 'vue'

const NETS = ['tcp', 'ws', 'http', 'h2', 'grpc'] as const

export default defineComponent({
  name: 'OpenClashManualNodeForm',
  props: {
    modelValue: {
      type: Object as PropType<ManualNodeDraft>,
      required: true,
    },
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const u = (patch: Partial<ManualNodeDraft>) => {
      emit('update:modelValue', { ...props.modelValue, ...patch })
    }
    const setType = (t: ManualProto) => {
      const { name, server, port } = props.modelValue
      emit('update:modelValue', {
        ...emptyManualDraft(t),
        name,
        server,
        port: port?.trim() ? port : String(defaultPortForProto(t)),
      })
    }

    return () => {
      const d = props.modelValue
      return (
        <div class="flex flex-col gap-2 text-xs sm:text-sm">
          <div class="rounded-box border border-base-300/30 bg-base-200/35 p-3">
            <div class="mb-2 flex flex-col gap-2 sm:flex-row sm:items-end sm:gap-3">
              <label class="flex min-w-0 flex-1 flex-col gap-0.5 sm:max-w-[13rem]">
                <span class="text-[11px] text-base-content/60">协议</span>
                <select
                  class="select select-bordered select-sm w-full"
                  value={d.type}
                  onChange={(e) => setType((e.target as HTMLSelectElement).value as ManualProto)}
                >
                  {MANUAL_PROTO_OPTIONS.map((o) => (
                    <option
                      key={o.value}
                      value={o.value}
                    >
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label class="flex flex-col gap-0.5">
                <span class="text-[11px] text-base-content/60">名称</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.name}
                  onInput={(e) => u({ name: (e.target as HTMLInputElement).value })}
                  placeholder="显示名"
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="text-[11px] text-base-content/60">端口</span>
                <input
                  class="input input-bordered input-sm"
                  type="number"
                  min={1}
                  max={65535}
                  value={d.port}
                  onInput={(e) => u({ port: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="text-[11px] text-base-content/60">服务器</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.server}
                  onInput={(e) => u({ server: (e.target as HTMLInputElement).value })}
                  placeholder="域名或 IP"
                />
              </label>
              {d.type === 'ss' && (
                <>
                  <label class="flex flex-col gap-0.5">
                    <span class="text-[11px] text-base-content/60">加密</span>
                    <input
                      class="input input-bordered input-sm"
                      value={d.ssCipher}
                      onInput={(e) => u({ ssCipher: (e.target as HTMLInputElement).value })}
                      placeholder="aes-256-gcm"
                    />
                  </label>
                  <label class="flex flex-col gap-0.5">
                    <span class="text-[11px] text-base-content/60">密码</span>
                    <input
                      class="input input-bordered input-sm"
                      type="password"
                      autocomplete="off"
                      value={d.ssPassword}
                      onInput={(e) => u({ ssPassword: (e.target as HTMLInputElement).value })}
                      placeholder="必填"
                    />
                  </label>
                </>
              )}
            </div>
          </div>

          <div
            tabindex={0}
            class="collapse collapse-arrow rounded-box border border-base-300/40 bg-base-200/50"
          >
            <div class="collapse-title min-h-10 px-2 py-2 text-sm font-medium sm:min-h-9">
              更多参数（插件、传输等）
            </div>
            <div class="collapse-content pb-2">
          {d.type === 'ss' && (
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">插件（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.ssPlugin}
                  onInput={(e) => u({ ssPlugin: (e.target as HTMLInputElement).value })}
                  placeholder="v2ray-plugin"
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">plugin-opts JSON（可选）</span>
                <textarea
                  class="textarea textarea-bordered textarea-sm min-h-14 font-mono"
                  value={d.ssPluginOptsJson}
                  onInput={(e) => u({ ssPluginOptsJson: (e.target as HTMLTextAreaElement).value })}
                  placeholder='{"mode": "websocket", "tls": true}'
                />
              </label>
              <label class="flex cursor-pointer items-center gap-2 sm:col-span-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.ssUdp}
                  onChange={(e) => u({ ssUdp: (e.target as HTMLInputElement).checked })}
                />
                UDP
              </label>
            </div>
          )}

          {d.type === 'vmess' && (
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">UUID</span>
                <input
                  class="input input-bordered input-sm font-mono"
                  value={d.vmessUuid}
                  onInput={(e) => u({ vmessUuid: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">alterId</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.vmessAlterId}
                  onInput={(e) => u({ vmessAlterId: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">cipher</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.vmessCipher}
                  onInput={(e) => u({ vmessCipher: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">传输 network</span>
                <select
                  class="select select-bordered select-sm"
                  value={d.vmessNetwork}
                  onChange={(e) => u({ vmessNetwork: (e.target as HTMLSelectElement).value })}
                >
                  {NETS.map((n) => (
                    <option
                      key={n}
                      value={n}
                    >
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">SNI（TLS 时）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.vmessSni}
                  onInput={(e) => u({ vmessSni: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">Host（WS 等）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.vmessHost}
                  onInput={(e) => u({ vmessHost: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">Path</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.vmessPath}
                  onInput={(e) => u({ vmessPath: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.vmessTls}
                  onChange={(e) => u({ vmessTls: (e.target as HTMLInputElement).checked })}
                />
                TLS
              </label>
              <label class="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.vmessUdp}
                  onChange={(e) => u({ vmessUdp: (e.target as HTMLInputElement).checked })}
                />
                UDP
              </label>
            </div>
          )}

          {d.type === 'vless' && (
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">UUID</span>
                <input
                  class="input input-bordered input-sm font-mono"
                  value={d.vlessUuid}
                  onInput={(e) => u({ vlessUuid: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">encryption</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.vlessEncryption}
                  onInput={(e) => u({ vlessEncryption: (e.target as HTMLInputElement).value })}
                  placeholder="none"
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">flow（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.vlessFlow}
                  onInput={(e) => u({ vlessFlow: (e.target as HTMLInputElement).value })}
                  placeholder="xtls-rprx-vision"
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">传输 network</span>
                <select
                  class="select select-bordered select-sm"
                  value={d.vlessNetwork}
                  onChange={(e) => u({ vlessNetwork: (e.target as HTMLSelectElement).value })}
                >
                  {NETS.map((n) => (
                    <option
                      key={n}
                      value={n}
                    >
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">TLS / Reality</span>
                <select
                  class="select select-bordered select-sm"
                  value={d.vlessTlsMode}
                  onChange={(e) =>
                    u({ vlessTlsMode: (e.target as HTMLSelectElement).value as ManualNodeDraft['vlessTlsMode'] })
                  }
                >
                  <option value="off">关闭</option>
                  <option value="tls">TLS</option>
                  <option value="reality">REALITY</option>
                </select>
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">SNI / servername</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.vlessSni}
                  onInput={(e) => u({ vlessSni: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">Host</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.vlessHost}
                  onInput={(e) => u({ vlessHost: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">Path</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.vlessPath}
                  onInput={(e) => u({ vlessPath: (e.target as HTMLInputElement).value })}
                />
              </label>
              {d.vlessTlsMode === 'reality' && (
                <>
                  <label class="flex flex-col gap-0.5 sm:col-span-2">
                    <span class="opacity-70">Reality public-key (pbk)</span>
                    <input
                      class="input input-bordered input-sm font-mono text-[11px]"
                      value={d.vlessPublicKey}
                      onInput={(e) => u({ vlessPublicKey: (e.target as HTMLInputElement).value })}
                    />
                  </label>
                  <label class="flex flex-col gap-0.5 sm:col-span-2">
                    <span class="opacity-70">Reality short-id</span>
                    <input
                      class="input input-bordered input-sm font-mono"
                      value={d.vlessShortId}
                      onInput={(e) => u({ vlessShortId: (e.target as HTMLInputElement).value })}
                    />
                  </label>
                  <label class="flex flex-col gap-0.5 sm:col-span-2">
                    <span class="opacity-70">client-fingerprint（可选，默认可由后端补）</span>
                    <input
                      class="input input-bordered input-sm"
                      value={d.vlessClientFingerprint}
                      onInput={(e) => u({ vlessClientFingerprint: (e.target as HTMLInputElement).value })}
                      placeholder="chrome"
                    />
                  </label>
                </>
              )}
              {d.vlessTlsMode === 'tls' && (
                <label class="flex flex-col gap-0.5 sm:col-span-2">
                  <span class="opacity-70">client-fingerprint（可选）</span>
                  <input
                    class="input input-bordered input-sm"
                    value={d.vlessClientFingerprint}
                    onInput={(e) => u({ vlessClientFingerprint: (e.target as HTMLInputElement).value })}
                  />
                </label>
              )}
              <label class="flex cursor-pointer items-center gap-2 sm:col-span-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.vlessUdp}
                  onChange={(e) => u({ vlessUdp: (e.target as HTMLInputElement).checked })}
                />
                UDP
              </label>
            </div>
          )}

          {d.type === 'trojan' && (
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">密码</span>
                <input
                  class="input input-bordered input-sm"
                  type="password"
                  autocomplete="off"
                  value={d.trojanPassword}
                  onInput={(e) => u({ trojanPassword: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">SNI（默认同服务器）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.trojanSni}
                  onInput={(e) => u({ trojanSni: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">传输 network</span>
                <select
                  class="select select-bordered select-sm"
                  value={d.trojanNetwork}
                  onChange={(e) => u({ trojanNetwork: (e.target as HTMLSelectElement).value })}
                >
                  {NETS.map((n) => (
                    <option
                      key={n}
                      value={n}
                    >
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">Host</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.trojanHost}
                  onInput={(e) => u({ trojanHost: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">Path</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.trojanPath}
                  onInput={(e) => u({ trojanPath: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.trojanSkipCert}
                  onChange={(e) => u({ trojanSkipCert: (e.target as HTMLInputElement).checked })}
                />
                skip-cert-verify
              </label>
              <label class="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.trojanUdp}
                  onChange={(e) => u({ trojanUdp: (e.target as HTMLInputElement).checked })}
                />
                UDP
              </label>
            </div>
          )}

          {d.type === 'hysteria' && (
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">auth 认证串</span>
                <input
                  class="input input-bordered input-sm font-mono"
                  value={d.hyAuth}
                  onInput={(e) => u({ hyAuth: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">SNI</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hySni}
                  onInput={(e) => u({ hySni: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">protocol</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hyProtocol}
                  onInput={(e) => u({ hyProtocol: (e.target as HTMLInputElement).value })}
                  placeholder="udp"
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">obfs（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hyObfs}
                  onInput={(e) => u({ hyObfs: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">obfs-password</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hyObfsPass}
                  onInput={(e) => u({ hyObfsPass: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">up 限速（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hyUp}
                  onInput={(e) => u({ hyUp: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">down 限速（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hyDown}
                  onInput={(e) => u({ hyDown: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex cursor-pointer items-center gap-2 sm:col-span-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.hySkipCert}
                  onChange={(e) => u({ hySkipCert: (e.target as HTMLInputElement).checked })}
                />
                skip-cert-verify
              </label>
            </div>
          )}

          {d.type === 'hysteria2' && (
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">密码</span>
                <input
                  class="input input-bordered input-sm"
                  type="password"
                  autocomplete="off"
                  value={d.hy2Password}
                  onInput={(e) => u({ hy2Password: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">SNI</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hy2Sni}
                  onInput={(e) => u({ hy2Sni: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">obfs（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hy2Obfs}
                  onInput={(e) => u({ hy2Obfs: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">obfs-password</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hy2ObfsPass}
                  onInput={(e) => u({ hy2ObfsPass: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">up（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hy2Up}
                  onInput={(e) => u({ hy2Up: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">down（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hy2Down}
                  onInput={(e) => u({ hy2Down: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">ALPN（可选，逗号分隔）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.hy2Alpn}
                  onInput={(e) => u({ hy2Alpn: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex cursor-pointer items-center gap-2 sm:col-span-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.hy2Insecure}
                  onChange={(e) => u({ hy2Insecure: (e.target as HTMLInputElement).checked })}
                />
                insecure（跳过证书校验）
              </label>
            </div>
          )}

          {d.type === 'tuic' && (
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">UUID</span>
                <input
                  class="input input-bordered input-sm font-mono"
                  value={d.tuicUuid}
                  onInput={(e) => u({ tuicUuid: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">password（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  type="password"
                  autocomplete="off"
                  value={d.tuicPassword}
                  onInput={(e) => u({ tuicPassword: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">SNI</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.tuicSni}
                  onInput={(e) => u({ tuicSni: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">congestion-controller</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.tuicCongestion}
                  onInput={(e) => u({ tuicCongestion: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">udp-relay-mode</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.tuicUdpRelay}
                  onInput={(e) => u({ tuicUdpRelay: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">ALPN（逗号分隔）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.tuicAlpn}
                  onInput={(e) => u({ tuicAlpn: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex cursor-pointer items-center gap-2 sm:col-span-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.tuicSkipCert}
                  onChange={(e) => u({ tuicSkipCert: (e.target as HTMLInputElement).checked })}
                />
                skip-cert-verify
              </label>
            </div>
          )}

          {d.type === 'wireguard' && (
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">公钥 public-key（对端）</span>
                <input
                  class="input input-bordered input-sm font-mono text-[11px]"
                  value={d.wgPub}
                  onInput={(e) => u({ wgPub: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">私钥 private-key（本机，可选若由内核管理）</span>
                <input
                  class="input input-bordered input-sm font-mono text-[11px]"
                  type="password"
                  autocomplete="off"
                  value={d.wgPrivate}
                  onInput={(e) => u({ wgPrivate: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">DNS</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.wgDns}
                  onInput={(e) => u({ wgDns: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">ip（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.wgIp}
                  onInput={(e) => u({ wgIp: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">allowed-ips（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.wgAllowed}
                  onInput={(e) => u({ wgAllowed: (e.target as HTMLInputElement).value })}
                  placeholder="0.0.0.0/0"
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">MTU（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.wgMtu}
                  onInput={(e) => u({ wgMtu: (e.target as HTMLInputElement).value })}
                />
              </label>
            </div>
          )}

          {d.type === 'socks5' && (
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">用户名（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.skUser}
                  onInput={(e) => u({ skUser: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5">
                <span class="opacity-70">密码（可选）</span>
                <input
                  class="input input-bordered input-sm"
                  type="password"
                  autocomplete="off"
                  value={d.skPass}
                  onInput={(e) => u({ skPass: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex flex-col gap-0.5 sm:col-span-2">
                <span class="opacity-70">SNI / servername（SOCKS over TLS 时）</span>
                <input
                  class="input input-bordered input-sm"
                  value={d.skSni}
                  onInput={(e) => u({ skSni: (e.target as HTMLInputElement).value })}
                />
              </label>
              <label class="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.skUdp}
                  onChange={(e) => u({ skUdp: (e.target as HTMLInputElement).checked })}
                />
                UDP
              </label>
              <label class="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.skTls}
                  onChange={(e) => u({ skTls: (e.target as HTMLInputElement).checked })}
                />
                TLS
              </label>
              <label class="flex cursor-pointer items-center gap-2 sm:col-span-2">
                <input
                  type="checkbox"
                  class="checkbox checkbox-sm"
                  checked={d.skSkipCert}
                  onChange={(e) => u({ skSkipCert: (e.target as HTMLInputElement).checked })}
                />
                skip-cert-verify
              </label>
            </div>
          )}
            </div>
          </div>
        </div>
      )
    }
  },
})
