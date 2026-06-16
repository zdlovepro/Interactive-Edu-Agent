import request from '@/utils/request'
import { USER_API } from '@/constants/api'

export function loginUser(payload) {
  return request.post(USER_API.LOGIN, payload)
}

export function registerUser(payload) {
  return request.post(USER_API.REGISTER, payload)
}

export function logoutUser() {
  return request.post(USER_API.LOGOUT)
}

export function getUserProfile() {
  return request.get(USER_API.PROFILE)
}
