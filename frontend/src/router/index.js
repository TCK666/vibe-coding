import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginEntry.vue')
  },
  {
    path: '/auth/callback',
    name: 'auth-callback',
    component: () => import('../views/AuthCallback.vue')
  },
  {
    path: '/workbench',
    name: 'workbench',
    component: () => import('../views/Workbench.vue')
  },
  {
    path: '/admin/config',
    name: 'admin-config',
    component: () => import('../views/admin/ConfigPage.vue')
  },
  {
    path: '/admin/logs',
    name: 'admin-logs',
    component: () => import('../views/admin/LogPage.vue')
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/login'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局前置守卫：除登录入口与认证回调外，未登录一律跳转 /login
const PUBLIC_PATHS = ['/login', '/auth/callback']

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('baas_token')
  if (!PUBLIC_PATHS.includes(to.path) && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
