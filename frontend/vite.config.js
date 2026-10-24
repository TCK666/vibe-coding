import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true
      },
      // 只代理后端登录入口；/auth/callback 是前端 SPA 路由，不能被代理吃掉
      '/auth/login': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
