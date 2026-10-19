import request from './request'
import type { UserInfo } from '@/types'

export interface SliderCaptchaData {
  captcha_id: string
  bg_image: string
  slider_image: string
  y: number
  block_width: number
  block_height: number
}

export interface SliderVerifyResult {
  success: boolean
  captcha_token?: string
  elapsed_time?: number
  message: string
}

export function getSliderCaptchaApi() {
  return request<SliderCaptchaData>({
    url: '/auth/captcha/slider',
    method: 'GET'
  })
}

export function verifySliderCaptchaApi(data: {
  captcha_id: string
  x: number
  track: Array<[number, number, number]>
}) {
  return request<SliderVerifyResult>({
    url: '/auth/captcha/verify',
    method: 'POST',
    data
  })
}

export function loginApi(data: { username: string; password: string; captcha_token?: string }) {
  return request<{
    token: string
    token_type: string
    expires_in: number
    user: Partial<UserInfo>
  }>({
    url: '/auth/login',
    method: 'POST',
    data
  })
}

export function getUserInfoApi() {
  return request<UserInfo>({
    url: '/auth/user_info',
    method: 'GET'
  })
}

export function logoutApi() {
  return request<null>({
    url: '/auth/logout',
    method: 'POST'
  })
}
