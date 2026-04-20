import request from './request'

export interface LoginParams {
  username: string
  password: string
}

export interface UserInfo {
  id: number
  username: string
  real_name: string
  role: string
  department?: string
  phone?: string
}

export function login(data: LoginParams) {
  return request.post<{ access_token: string; token_type: string; user: UserInfo }>(
    '/auth/login',
    data,
  )
}

export function getUserInfo() {
  return request.get<UserInfo>('/auth/info')
}
