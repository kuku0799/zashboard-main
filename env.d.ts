/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_UI_RELEASE_REPO?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

interface Window {
  ksu?: object
}
