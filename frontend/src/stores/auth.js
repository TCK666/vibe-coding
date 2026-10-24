import { ref } from 'vue'
import { defineStore } from 'pinia'

const TOKEN_KEY = 'baas_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref(null)

  function login(newToken, newUser) {
    token.value = newToken
    user.value = newUser || null
    localStorage.setItem(TOKEN_KEY, newToken)
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  return { token, user, login, logout }
})
