import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  closeChaoxingAuthSession,
  createChaoxingAuthSession,
  getChaoxingAuthQrCodeUrl,
  getChaoxingAuthSession,
} from '@/api/courseResourceImport'

const STORAGE_KEY = 'interactive-edu.chaoxing-auth'
const TERMINAL_STATUSES = new Set(['AUTHORIZED', 'EXPIRED', 'FAILED', 'CLOSED'])

function normalizeAuthSession(payload) {
  return {
    sessionId: payload?.sessionId || payload?.session_id || '',
    status: String(payload?.status || 'CREATED').trim().toUpperCase(),
    qrCodeUrl: payload?.qrCodeUrl || payload?.qr_code_url || '',
    message: payload?.message || '',
    expiresAt: payload?.expiresAt || payload?.expires_at || '',
    authorizedAt: payload?.authorizedAt || payload?.authorized_at || '',
  }
}

function loadPersistedSession() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw ? normalizeAuthSession(JSON.parse(raw)) : null
  } catch {
    return null
  }
}

function persistSession(session) {
  if (!session?.sessionId) {
    window.localStorage.removeItem(STORAGE_KEY)
    return
  }

  const payload = {
    sessionId: session.sessionId,
    status: session.status,
    expiresAt: session.expiresAt,
    authorizedAt: session.authorizedAt,
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

export const useChaoxingAuthStore = defineStore('chaoxingAuth', () => {
  const session = ref(null)
  const loading = ref(false)
  const errorMessage = ref('')

  const sessionId = computed(() => session.value?.sessionId || '')
  const status = computed(() => String(session.value?.status || '').trim().toUpperCase())
  const isAuthorized = computed(() => status.value === 'AUTHORIZED')
  const qrCodeUrl = computed(() => {
    if (!sessionId.value) {
      return ''
    }
    return getChaoxingAuthQrCodeUrl(sessionId.value)
  })

  function setSession(payload) {
    session.value = normalizeAuthSession(payload)
    if (session.value.sessionId && status.value === 'AUTHORIZED') {
      persistSession(session.value)
    } else if (['EXPIRED', 'FAILED', 'CLOSED'].includes(status.value)) {
      persistSession(null)
    }
    return session.value
  }

  async function createSession(payload = {}) {
    loading.value = true
    errorMessage.value = ''
    try {
      const response = await createChaoxingAuthSession(payload)
      return setSession(response.data)
    } catch (error) {
      errorMessage.value = error?.message || '创建超星扫码授权失败。'
      throw error
    } finally {
      loading.value = false
    }
  }

  async function refreshSession(id = sessionId.value) {
    if (!id) {
      return null
    }

    loading.value = true
    errorMessage.value = ''
    try {
      const response = await getChaoxingAuthSession(id)
      return setSession(response.data)
    } catch (error) {
      clearSession()
      errorMessage.value = error?.message || '超星授权会话已失效，请重新扫码。'
      throw error
    } finally {
      loading.value = false
    }
  }

  async function restoreFromLocalStorage() {
    const persisted = loadPersistedSession()
    if (!persisted?.sessionId) {
      return null
    }

    session.value = persisted
    try {
      return await refreshSession(persisted.sessionId)
    } catch {
      return null
    }
  }

  async function closeSession() {
    const id = sessionId.value
    clearSession()
    if (!id) {
      return null
    }
    return closeChaoxingAuthSession(id)
  }

  function clearSession() {
    session.value = null
    errorMessage.value = ''
    persistSession(null)
  }

  return {
    session,
    loading,
    errorMessage,
    sessionId,
    status,
    isAuthorized,
    qrCodeUrl,
    terminalStatuses: TERMINAL_STATUSES,
    createSession,
    refreshSession,
    restoreFromLocalStorage,
    closeSession,
    clearSession,
    setSession,
  }
})

