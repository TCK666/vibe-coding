import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import router from '../router'

// baseURL 留空，请求走 vite dev server 的 /api、/auth 代理
const request = axios.create({
  baseURL: '',
  timeout: 30000
})

// 请求拦截器：附加 Bearer token
request.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

// 响应拦截器：401 时清除 token 并跳转登录页
request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      const auth = useAuthStore()
      auth.logout()
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

export default request
