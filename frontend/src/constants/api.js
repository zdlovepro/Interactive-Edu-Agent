export const USER_API = {
  LOGIN: '/user/login',
  LOGOUT: '/user/logout',
  PROFILE: '/user/profile',
  UPDATE: '/user/update',
}

export const COURSEWARE_API = {
  UPLOAD: '/courseware/upload',
  IMPORT_URL: '/courseware/import-url',
  URL_IMPORT_TASK: taskId => `/courseware/import-url/tasks/${taskId}`,
  LIST: '/courseware',
  DETAIL: id => `/courseware/${id}`,
}

export const SCRIPT_API = {
  GET: coursewareId => `/courseware/${coursewareId}/script`,
  UPDATE: coursewareId => `/courseware/${coursewareId}/script`,
  GENERATE: coursewareId => `/courseware/${coursewareId}/script/generate`,
}

export const COURSEWARE_VIDEO_API = {
  RENDER: coursewareId => `/courseware/${coursewareId}/video/render`,
  SOURCE: coursewareId => `/courseware/${coursewareId}/video/source`,
}

export const LECTURE_API = {
  START: '/lecture/start',
  PAUSE: sessionId => `/lecture/${sessionId}/pause`,
  RESUME: '/lecture/resume',
}

export const QA_API = {
  ASK_TEXT: '/qa/ask-text',
  STREAM: '/qa/stream',
}

export const ASR_API = {
  RECOGNIZE: '/asr/recognize',
}

export const COURSE_RESOURCE_IMPORT_API = {
  CREATE_TASK: '/course-resource-import/tasks',
  DETAIL: taskId => `/course-resource-import/tasks/${taskId}`,
  FILES: taskId => `/course-resource-import/tasks/${taskId}/files`,
  RETRY: taskId => `/course-resource-import/tasks/${taskId}/retry`,
  CANCEL: taskId => `/course-resource-import/tasks/${taskId}/cancel`,
}

export const CHAOXING_AUTH_API = {
  CREATE_SESSION: '/chaoxing/auth/sessions',
  DETAIL: sessionId => `/chaoxing/auth/sessions/${sessionId}`,
  QRCODE: sessionId => `/chaoxing/auth/sessions/${sessionId}/qrcode`,
  CLOSE: sessionId => `/chaoxing/auth/sessions/${sessionId}`,
}

export const OTHER_API = {}
