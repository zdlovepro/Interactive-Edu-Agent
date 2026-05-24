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
  GENERATE: coursewareId => `/courseware/${coursewareId}/script/generate`,
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

export const VIDEO_ASSET_API = {
  LIST: '/video-assets',
  DETAIL: assetId => `/video-assets/${assetId}`,
  UPLOAD: '/video-assets/upload',
  IMPORT_SAMPLE: '/video-assets/import-sample',
  TRANSCODE: assetId => `/video-assets/${assetId}/transcode`,
}

export const OTHER_API = {}
