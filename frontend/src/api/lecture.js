import request from '@/utils/request'
import { LECTURE_API } from '@/constants/api'

export function startLecture({ coursewareId } = {}) {
  return request.post(LECTURE_API.START, { coursewareId })
}

export function pauseLecture(sessionId) {
  return request.post(LECTURE_API.PAUSE(sessionId))
}

export function resumeLecture({ sessionId } = {}) {
  return request.post(LECTURE_API.RESUME, { sessionId })
}
