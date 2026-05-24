import request from '@/utils/request'
import { COURSE_RESOURCE_IMPORT_API } from '@/constants/api'

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
