import request from './request'

export interface UserItem {
  id: number
  username: string
  real_name: string
  role: string
  department?: string
  phone?: string
}

export interface UserCreateParams {
  username: string
  password: string
  real_name?: string
  role: string
  department?: string
  phone?: string
}

export function listUsers() {
  return request.get<UserItem[]>('/user/manage')
}

export function createUser(data: UserCreateParams) {
  return request.post<UserItem>('/user/manage', data)
}
