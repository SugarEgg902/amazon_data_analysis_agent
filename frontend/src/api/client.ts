import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

// 后端统一响应 { data, error }，这里解包出 data
export function unwrap<T>(p: Promise<{ data: { data: T } }>): Promise<T> {
  return p.then((r) => r.data.data)
}
