<template>
  <div class="auth-callback">
    <el-card class="callback-card" shadow="hover">
      <template v-if="error">
        <h2 class="title error">登录失败</h2>
        <p class="message">{{ error }}</p>
        <el-button type="primary" @click="goLogin">返回重新登录</el-button>
      </template>
      <template v-else>
        <h2 class="title">登录成功</h2>
        <p class="message">正在进入工作台…</p>
      </template>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const error = ref('')

onMounted(() => {
  const accessToken = route.query.access_token
  const expiresIn = route.query.expires_in

  if (!accessToken) {
    error.value = '未从认证中心获取到访问令牌（access_token），请重新登录。'
    return
  }

  localStorage.setItem('baas_token', String(accessToken))
  if (expiresIn) {
    localStorage.setItem('baas_expires_in', String(expiresIn))
  }

  router.push('/workbench')
})

function goLogin() {
  window.location.href = '/auth/login'
}
</script>

<style scoped>
.auth-callback {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.callback-card {
  width: 380px;
  text-align: center;
  padding: 16px 0;
}

.title {
  margin: 0 0 8px;
  font-size: 20px;
  color: #303133;
}

.title.error {
  color: #f56c6c;
}

.message {
  margin: 0 0 20px;
  font-size: 14px;
  color: #909399;
}
</style>
