const TOKEN_KEY = 'token'
const PROFILE_KEY = 'iea_user_profile'
const LEGACY_COURSE_CODE_KEY = 'iea_shared_course_code'
const LEGACY_COURSE_CODES_KEY = 'iea_shared_course_codes'
const LEGACY_ACTIVE_COURSE_CODE_KEY = 'iea_active_course_code'
const COURSE_STATE_KEY_PREFIX = 'iea_shared_course_state'

function safeParse(rawValue, fallback = null) {
  if (!rawValue) {
    return fallback
  }

  try {
    return JSON.parse(rawValue)
  } catch {
    return fallback
  }
}

function normalizeCourseCode(courseCode) {
  return String(courseCode || '').trim().toUpperCase()
}

function normalizeCourseCodes(courseCodes) {
  const uniqueCodes = []
  const seen = new Set()

  for (const code of Array.isArray(courseCodes) ? courseCodes : []) {
    const normalized = normalizeCourseCode(code)
    if (!normalized || seen.has(normalized)) {
      continue
    }
    seen.add(normalized)
    uniqueCodes.push(normalized)
  }

  return uniqueCodes
}

function normalizeStorageUserKey(rawUserKey) {
  return String(rawUserKey || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '_')
}

function resolveCourseStateStorageUserKey() {
  const storedProfile = getStoredProfile()
  const rawUserKey = storedProfile?.id || storedProfile?.username || ''
  return normalizeStorageUserKey(rawUserKey)
}

function buildCourseStateKey(userKey) {
  return `${COURSE_STATE_KEY_PREFIX}:${userKey}`
}

function readLegacyCourseState() {
  const storedCourseCodes = safeParse(localStorage.getItem(LEGACY_COURSE_CODES_KEY), null)
  const normalizedCourseCodes = Array.isArray(storedCourseCodes)
    ? normalizeCourseCodes(storedCourseCodes)
    : normalizeCourseCodes([localStorage.getItem(LEGACY_COURSE_CODE_KEY)])
  const activeCourseCode = normalizeCourseCode(localStorage.getItem(LEGACY_ACTIVE_COURSE_CODE_KEY))

  return {
    courseCodes: normalizedCourseCodes,
    activeCourseCode,
  }
}

function clearLegacyCourseState() {
  localStorage.removeItem(LEGACY_COURSE_CODE_KEY)
  localStorage.removeItem(LEGACY_COURSE_CODES_KEY)
  localStorage.removeItem(LEGACY_ACTIVE_COURSE_CODE_KEY)
}

function resolveStoredCourseState(userKey = resolveCourseStateStorageUserKey()) {
  if (!userKey) {
    const legacyState = readLegacyCourseState()
    return {
      courseCodes: legacyState.courseCodes,
      activeCourseCode: legacyState.courseCodes.includes(legacyState.activeCourseCode)
        ? legacyState.activeCourseCode
        : legacyState.courseCodes[0] || '',
    }
  }

  const persistedState = safeParse(localStorage.getItem(buildCourseStateKey(userKey)), null)
  if (persistedState && typeof persistedState === 'object') {
    const courseCodes = normalizeCourseCodes(persistedState.courseCodes)
    const activeCourseCode = normalizeCourseCode(persistedState.activeCourseCode)
    return {
      courseCodes,
      activeCourseCode: courseCodes.includes(activeCourseCode) ? activeCourseCode : courseCodes[0] || '',
    }
  }

  const legacyState = readLegacyCourseState()
  if (legacyState.courseCodes.length) {
    const migratedState = syncStoredCourseCodes(legacyState.courseCodes, legacyState.activeCourseCode, userKey)
    clearLegacyCourseState()
    return migratedState
  }

  return {
    courseCodes: [],
    activeCourseCode: '',
  }
}

function syncStoredCourseCodes(
  courseCodes,
  preferredActiveCourseCode = '',
  userKey = resolveCourseStateStorageUserKey(),
) {
  const normalizedCodes = normalizeCourseCodes(courseCodes)
  const normalizedPreferred = normalizeCourseCode(preferredActiveCourseCode)
  const resolvedActiveCourseCode =
    normalizedPreferred && normalizedCodes.includes(normalizedPreferred)
      ? normalizedPreferred
      : normalizedCodes[0] || ''

  if (userKey) {
    const storageKey = buildCourseStateKey(userKey)
    if (normalizedCodes.length) {
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          courseCodes: normalizedCodes,
          activeCourseCode: resolvedActiveCourseCode,
        }),
      )
    } else {
      localStorage.removeItem(storageKey)
    }
  } else if (normalizedCodes.length) {
    localStorage.setItem(LEGACY_COURSE_CODES_KEY, JSON.stringify(normalizedCodes))
    if (resolvedActiveCourseCode) {
      localStorage.setItem(LEGACY_COURSE_CODE_KEY, resolvedActiveCourseCode)
      localStorage.setItem(LEGACY_ACTIVE_COURSE_CODE_KEY, resolvedActiveCourseCode)
    }
  } else {
    clearLegacyCourseState()
  }

  return {
    courseCodes: normalizedCodes,
    activeCourseCode: resolvedActiveCourseCode,
  }
}

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function getStoredProfile() {
  return safeParse(localStorage.getItem(PROFILE_KEY), null)
}

export function hasStoredSession() {
  return Boolean(getStoredToken())
}

export function setStoredSession({ token, user } = {}) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  }
  if (user) {
    localStorage.setItem(PROFILE_KEY, JSON.stringify(user))
  }
}

export function clearStoredSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(PROFILE_KEY)
}

export function getStoredCourseCodes() {
  return resolveStoredCourseState().courseCodes
}

export function getStoredCourseCode() {
  return resolveStoredCourseState().activeCourseCode
}

export function setStoredCourseCode(courseCode) {
  const normalized = normalizeCourseCode(courseCode)
  if (!normalized) {
    return syncStoredCourseCodes([], '').activeCourseCode
  }

  const currentState = resolveStoredCourseState()
  const nextCourseCodes = [
    normalized,
    ...currentState.courseCodes.filter(existingCode => existingCode !== normalized),
  ]
  return syncStoredCourseCodes(nextCourseCodes, normalized).activeCourseCode
}

export function setActiveStoredCourseCode(courseCode) {
  const normalized = normalizeCourseCode(courseCode)
  if (!normalized) {
    return resolveStoredCourseState().activeCourseCode
  }

  const currentState = resolveStoredCourseState()
  const nextCourseCodes = currentState.courseCodes.includes(normalized)
    ? currentState.courseCodes
    : [normalized, ...currentState.courseCodes]
  return syncStoredCourseCodes(nextCourseCodes, normalized).activeCourseCode
}

export function removeStoredCourseCode(courseCode) {
  const normalized = normalizeCourseCode(courseCode)
  if (!normalized) {
    return getStoredCourseCode()
  }

  const currentState = resolveStoredCourseState()
  const nextCourseCodes = currentState.courseCodes.filter(existingCode => existingCode !== normalized)
  const preferredActiveCourseCode =
    currentState.activeCourseCode === normalized ? nextCourseCodes[0] || '' : currentState.activeCourseCode
  return syncStoredCourseCodes(nextCourseCodes, preferredActiveCourseCode).activeCourseCode
}

export function clearStoredCourseCode() {
  syncStoredCourseCodes([], '')
}
