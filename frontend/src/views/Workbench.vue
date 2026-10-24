<template>
  <el-container class="workbench">
    <el-header class="wb-header" height="56px">
      <span class="wb-title">经营归因分析系统</span>
      <div class="wb-header-right">
        <span class="wb-user">{{ userDisplay }}</span>
        <el-button size="small" @click="handleLogout">退出登录</el-button>
      </div>
    </el-header>

    <el-container class="wb-body">
      <!-- 左侧：会话列表 -->
      <el-aside width="240px" class="wb-aside-left">
        <div class="aside-header">
          <el-button type="primary" class="new-chat-btn">新建会话</el-button>
        </div>
        <div class="placeholder-block">会话列表（占位）</div>
      </el-aside>

      <!-- 中间：对话区 -->
      <el-main class="wb-main">
        <div class="chat-panel">
          <div class="msg-list placeholder-block">消息列表（占位）</div>
          <div class="chat-input">
            <el-input
              v-model="draft"
              type="textarea"
              :rows="2"
              placeholder="请输入您的问题（功能建设中）"
              disabled
            />
            <el-button type="primary" class="send-btn" disabled>发送</el-button>
          </div>
        </div>
      </el-main>

      <!-- 右侧：实时任务 + 结果展示 -->
      <el-aside width="360px" class="wb-aside-right">
        <div class="panel">
          <h3 class="panel-title">实时任务</h3>
          <div class="placeholder-block">暂无运行中的任务（占位）</div>
        </div>
        <div class="panel">
          <h3 class="panel-title">结果展示</h3>
          <div class="placeholder-block">暂无分析结果（占位）</div>
        </div>
      </el-aside>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const draft = ref('')

const userDisplay = computed(() => {
  if (auth.user && (auth.user.username || auth.user.name)) {
    return auth.user.username || auth.user.name
  }
  return '当前用户（占位）'
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.workbench {
  height: 100vh;
}

.wb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.wb-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.wb-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.wb-user {
  font-size: 14px;
  color: #606266;
}

.wb-body {
  height: calc(100vh - 56px);
}

.wb-aside-left,
.wb-aside-right {
  background: #fff;
  padding: 12px;
  box-sizing: border-box;
  overflow: auto;
}

.wb-aside-left {
  border-right: 1px solid #e4e7ed;
}

.wb-aside-right {
  border-left: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.aside-header {
  margin-bottom: 12px;
}

.new-chat-btn {
  width: 100%;
}

.wb-main {
  padding: 12px;
  display: flex;
}

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px;
  box-sizing: border-box;
}

.msg-list {
  flex: 1;
}

.chat-input {
  margin-top: 12px;
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.send-btn {
  height: 52px;
}

.panel {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px;
}

.panel-title {
  margin: 0 0 12px;
  font-size: 15px;
  color: #303133;
}

.panel:first-child {
  flex: 1;
}

.panel:last-child {
  flex: 1.2;
}

.placeholder-block {
  border: 1px dashed #dcdfe6;
  border-radius: 4px;
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
  font-size: 14px;
}
</style>
