import request from './request'

// 认证说明：登录采用认证中心整页跳转，无需 axios 封装。
// - 登录入口：window.location.href = '/auth/login'（由 vite 代理到后端认证中心）
// - 回调解析：见 src/views/AuthCallback.vue，token 存入 localStorage('baas_token')

export const LOGIN_ENTRY_URL = '/auth/login'

export function goAuthLogin() {
  window.location.href = LOGIN_ENTRY_URL
}

export const getMe = () => request.get('/api/auth/me').then((r) => r.data.data)
