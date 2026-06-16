import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  clearStoredCourseCode,
  clearStoredSession,
  getStoredCourseCodes,
  getStoredCourseCode,
  getStoredProfile,
  getStoredToken,
  removeStoredCourseCode,
  setActiveStoredCourseCode,
  setStoredCourseCode,
  setStoredSession,
} from '@/utils/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getStoredToken())
  const user = ref(getStoredProfile())
  const sharedCourseCodes = ref(getStoredCourseCodes())
  const sharedCourseCode = ref(getStoredCourseCode())

  const isAuthenticated = computed(() => Boolean(token.value))
  const role = computed(() => String(user.value?.role || 'STUDENT').trim().toUpperCase())
  const isTeacher = computed(() => role.value === 'TEACHER' || role.value === 'ADMIN')
  const isStudent = computed(() => role.value === 'STUDENT')
  const displayName = computed(() => user.value?.realName || user.value?.username || 'User')
  const connectedCourseCount = computed(() => sharedCourseCodes.value.length)

  function restore() {
    token.value = getStoredToken()
    user.value = getStoredProfile()
    sharedCourseCodes.value = getStoredCourseCodes()
    sharedCourseCode.value = getStoredCourseCode()
  }

  function applySession(session) {
    token.value = session?.token || ''
    user.value = session?.user || null
    setStoredSession({ token: token.value, user: user.value })
    sharedCourseCodes.value = getStoredCourseCodes()
    sharedCourseCode.value = getStoredCourseCode()
  }

  function clearSession() {
    token.value = ''
    user.value = null
    sharedCourseCodes.value = []
    sharedCourseCode.value = ''
    clearStoredSession()
  }

  function updateProfile(profile) {
    user.value = profile || null
    setStoredSession({ token: token.value, user: user.value })
    sharedCourseCodes.value = getStoredCourseCodes()
    sharedCourseCode.value = getStoredCourseCode()
  }

  function setCourseCode(courseCode) {
    sharedCourseCode.value = setStoredCourseCode(courseCode)
    sharedCourseCodes.value = getStoredCourseCodes()
    return sharedCourseCode.value
  }

  function setActiveCourseCode(courseCode) {
    sharedCourseCode.value = setActiveStoredCourseCode(courseCode)
    sharedCourseCodes.value = getStoredCourseCodes()
    return sharedCourseCode.value
  }

  function removeCourseCode(courseCode) {
    sharedCourseCode.value = removeStoredCourseCode(courseCode)
    sharedCourseCodes.value = getStoredCourseCodes()
    return sharedCourseCode.value
  }

  function clearCourseCode() {
    sharedCourseCodes.value = []
    sharedCourseCode.value = ''
    clearStoredCourseCode()
  }

  return {
    token,
    user,
    sharedCourseCodes,
    sharedCourseCode,
    isAuthenticated,
    role,
    isTeacher,
    isStudent,
    displayName,
    connectedCourseCount,
    restore,
    applySession,
    clearSession,
    updateProfile,
    setCourseCode,
    setActiveCourseCode,
    removeCourseCode,
    clearCourseCode,
  }
})
