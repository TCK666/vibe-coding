<template>
  <div class="login-entry">
    <el-card class="login-card" shadow="hover">
      <h2 class="title">经营归因分析系统</h2>
      <p class="subtitle">请通过统一认证中心登录后使用</p>
      <el-button type="primary" size="large" class="login-btn" @click="handleLogin">
        通过认证中心登录
      </el-button>
    </el-card>
  </div>
</template>

<script setup>
import { LOGIN_ENTRY_URL } from '../api/auth'

function handleLogin() {
  window.location.href = LOGIN_ENTRY_URL
}
</script>

<style scoped>
.login-entry {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-card {
  width: 380px;
  text-align: center;
  padding: 16px 0;
}

.title {
  margin: 0 0 8px;
  font-size: 22px;
  color: #303133;
}

.subtitle {
  margin: 0 0 24px;
  font-size: 14px;
  color: #909399;
}

.login-btn {
  width: 80%;
}
</style>
