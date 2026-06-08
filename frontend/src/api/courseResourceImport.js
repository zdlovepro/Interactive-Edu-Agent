import request from '@/utils/request'
import { CHAOXING_AUTH_API, COURSE_RESOURCE_IMPORT_API } from '@/constants/api'

export function createChaoxingAuthSession(payload = {}, config = {}) {
  return request.post(CHAOXING_AUTH_API.CREATE_SESSION, payload, {
    timeout: 45000,
    ...config,
  })
}

export function getChaoxingAuthSession(sessionId, config = {}) {
  return request.get(CHAOXING_AUTH_API.DETAIL(sessionId), config)
}

export function getChaoxingAuthQrCodeUrl(sessionId) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  return `${baseUrl}${CHAOXING_AUTH_API.QRCODE(sessionId)}`
}

export function closeChaoxingAuthSession(sessionId, config = {}) {
  return request.delete(CHAOXING_AUTH_API.CLOSE(sessionId), config)
}

export function createCourseResourceImportTask(payload, config = {}) {
  return request.post(COURSE_RESOURCE_IMPORT_API.CREATE_TASK, payload, {
    timeout: 30000,
    ...config,
  })
}

export function getCourseResourceImportTask(taskId, config = {}) {
  return request.get(COURSE_RESOURCE_IMPORT_API.DETAIL(taskId), config)
}

export function getCourseResourceImportTaskFiles(taskId, config = {}) {
  return request.get(COURSE_RESOURCE_IMPORT_API.FILES(taskId), config)
}

export function retryCourseResourceImportTask(taskId, config = {}) {
  return request.post(COURSE_RESOURCE_IMPORT_API.RETRY(taskId), null, config)
}

export function cancelCourseResourceImportTask(taskId, config = {}) {
  return request.post(COURSE_RESOURCE_IMPORT_API.CANCEL(taskId), null, config)
}
