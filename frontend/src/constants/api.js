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

export const OTHER_API = {}
