import request from '@/utils/request'
import { COURSEWARE_API, COURSEWARE_VIDEO_API, SCRIPT_API } from '@/constants/api'

export function uploadCourseware(file, name, config = {}) {
  const formData = new FormData()
  formData.append('file', file)
  if (name) {
    formData.append('name', name)
  }

  return request.post(COURSEWARE_API.UPLOAD, formData, {
    ...config,
    headers: {
      'Content-Type': 'multipart/form-data',
      ...(config.headers || {}),
    },
  })
}

export function importCoursewareFromUrl(payload) {
  return request.post(COURSEWARE_API.IMPORT_URL, payload)
}

export function getUrlImportTask(taskId) {
  return request.get(COURSEWARE_API.URL_IMPORT_TASK(taskId))
}

export function listCourseware(params = {}) {
  return request.get(COURSEWARE_API.LIST, { params })
}

export function getCoursewareDetail(coursewareId) {
  return request.get(COURSEWARE_API.DETAIL(coursewareId))
}

export function getCoursewareScript(coursewareId) {
  return request.get(SCRIPT_API.GET(coursewareId))
}

export function updateCoursewareScript(coursewareId, payload) {
  return request.put(SCRIPT_API.UPDATE(coursewareId), payload)
}

export function generateScript(coursewareId) {
  return request.post(SCRIPT_API.GENERATE(coursewareId))
}

export function renderCoursewareVideo(coursewareId) {
  return request.post(COURSEWARE_VIDEO_API.RENDER(coursewareId))
}

export function getCoursewareVideoRenderTask(coursewareId) {
  return request.get(COURSEWARE_VIDEO_API.RENDER(coursewareId))
}
