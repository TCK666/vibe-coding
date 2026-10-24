<template>
  <el-container class="workbench">
    <el-header class="wb-header" height="56px">
      <span class="wb-title">经营归因分析系统</span>
      <div class="wb-header-right">
        <el-button size="small" :disabled="!conv.currentId" @click="attachVisible = true">
          附件（{{ attachments.length }}）
        </el-button>
        <span class="wb-user">{{ userDisplay }}</span>
        <el-button size="small" @click="handleLogout">退出登录</el-button>
      </div>
    </el-header>

    <el-container class="wb-body">
      <!-- 左侧：会话列表 -->
      <el-aside width="240px" class="wb-aside-left">
        <div class="aside-header">
          <el-button type="primary" class="new-chat-btn" @click="handleCreate">新建会话</el-button>
        </div>
        <div
          v-for="c in conv.conversations"
          :key="c.conversation_id"
          class="conv-item"
          :class="{ active: c.conversation_id === conv.currentId }"
          @click="handleSelect(c.conversation_id)"
        >
          <div class="conv-info">
            <div class="conv-title">{{ c.title }}</div>
            <div class="conv-time">{{ fmtTime(c.last_message_at) }}</div>
          </div>
          <div class="conv-ops" @click.stop>
            <el-icon title="重命名" @click="openRename(c)"><Edit /></el-icon>
            <el-icon title="删除" @click="handleDelete(c)"><Delete /></el-icon>
          </div>
        </div>
        <div v-if="!conv.conversations.length" class="empty-hint">暂无会话，点击上方新建</div>
      </el-aside>

      <!-- 中间：对话区 -->
      <el-main class="wb-main">
        <div class="chat-panel">
          <div v-if="conv.current" class="chat-title">{{ conv.current.title }}</div>
          <div class="msg-list">
            <template v-for="m in conv.messages" :key="m.message_id">
              <div v-if="m.message_type === 'tool_event'" class="tool-line">
                🔧 {{ m.tool_name }}：{{ m.content }}
              </div>
              <div v-else class="msg-row" :class="m.role">
                <div class="bubble">{{ m.content }}</div>
              </div>
            </template>

            <!-- 本轮流式输出 -->
            <template v-if="chat.taskState">
              <div v-for="(t, i) in chat.toolEvents" :key="'t' + i" class="tool-line">
                🔧 {{ t.name }}{{ t.status === 'running' ? '（执行中…）' : '：' + t.summary }}
              </div>
              <div v-if="chat.streamingText" class="msg-row assistant">
                <div class="bubble streaming">{{ chat.streamingText }}<span class="cursor">▍</span></div>
              </div>
            </template>

            <div v-if="!conv.messages.length && !chat.taskState" class="empty-hint">
              {{ conv.currentId ? '发送你的第一个分析问题吧' : '从左侧选择或新建会话' }}
            </div>
          </div>
          <div class="chat-input">
            <el-input
              v-model="draft"
              type="textarea"
              :rows="2"
              :disabled="!conv.currentId || !chat.connected"
              :placeholder="
                conv.currentId
                  ? chat.connected
                    ? '输入分析问题，Ctrl+Enter 发送'
                    : '实时通道连接中…'
                  : '先选择或新建会话'
              "
              @keydown.ctrl.enter.prevent="handleSend"
            />
            <el-button
              type="primary"
              class="send-btn"
              :disabled="!conv.currentId || !chat.connected || chat.taskState"
              @click="handleSend"
            >
              发送
            </el-button>
          </div>
        </div>
      </el-main>

      <!-- 右侧：实时任务 + 结果展示 -->
      <el-aside width="360px" class="wb-aside-right">
        <div class="panel">
          <h3 class="panel-title">实时任务</h3>
          <template v-if="chat.taskState">
            <div class="task-row">
              <el-tag size="small" :type="statusTagType(chat.taskState.status)">
                {{ chat.taskState.status }}
              </el-tag>
              <span class="task-step">{{ chat.taskState.currentStep || '…' }}</span>
            </div>
            <div class="task-tools">
              <div v-for="(t, i) in chat.toolEvents" :key="i" class="task-tool">
                <span :class="['tool-dot', t.status]"></span>
                {{ t.name }} {{ t.status === 'running' ? '执行中…' : '完成' }}
                <div v-if="t.summary" class="tool-summary">{{ t.summary }}</div>
              </div>
            </div>
            <el-button
              size="small"
              type="danger"
              plain
              class="cancel-btn"
              @click="handleCancel"
            >
              取消分析
            </el-button>
          </template>
          <div v-else class="placeholder-block small">暂无运行中的任务</div>
        </div>
        <div class="panel">
          <h3 class="panel-title">结果展示</h3>
          <div class="placeholder-block small">暂无分析结果</div>
        </div>
      </el-aside>
    </el-container>

    <!-- 附件抽屉 -->
    <el-drawer v-model="attachVisible" title="会话附件" size="480px">
      <div class="attach-upload">
        <input ref="fileRef" type="file" style="display: none" @change="handleUpload" />
        <el-button type="primary" :loading="uploading" @click="fileRef && fileRef.click()">
          {{ uploading ? `上传中 ${uploadPct}%` : '上传附件' }}
        </el-button>
        <span class="attach-hint">单文件 ≤ 50MB</span>
      </div>
      <el-table :data="attachments" size="small" empty-text="当前会话还没有附件">
        <el-table-column prop="file_name" label="文件名" min-width="140" show-overflow-tooltip />
        <el-table-column prop="file_type" label="类型" width="70" />
        <el-table-column label="大小" width="80">
          <template #default="{ row }">{{ fmtSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="解析状态" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.parse_status === 'success' ? 'success' : 'info'">
              {{ row.parse_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="90">
          <template #default="{ row }">{{ fmtDay(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleDownload(row)">下载</el-button>
            <el-button link type="danger" size="small" @click="handleDeleteAttachment(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <!-- 重命名对话框 -->
    <el-dialog v-model="renameVisible" title="重命名会话" width="420px">
      <el-input v-model="renameTitle" maxlength="256" placeholder="会话名称" @keyup.enter="doRename" />
      <template #footer>
        <el-button @click="renameVisible = false">取消</el-button>
        <el-button type="primary" @click="doRename">确定</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete, Edit } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { getMe as fetchMe } from '../api/auth'
import { useConversationStore } from '../stores/conversation'
import { useChatStore } from '../stores/chat'
import {
  deleteAttachment,
  downloadAttachment,
  listAttachments,
  uploadAttachment
} from '../api/attachment'

const router = useRouter()
const auth = useAuthStore()
const conv = useConversationStore()
const chat = useChatStore()

const draft = ref('')
const userDisplay = ref('当前用户')
const attachments = ref([])
const attachVisible = ref(false)
const uploading = ref(false)
const uploadPct = ref(0)
const fileRef = ref(null)
const renameVisible = ref(false)
const renameTitle = ref('')
const renameTarget = ref(null)

function authErr(e) {
  return ElMessage.error(e?.response?.data?.message || '请求失败')
}

onMounted(async () => {
  chat.setDoneHandler(onRoundDone)
  try {
    const me = await fetchMe()
    auth.user = me
    userDisplay.value = me.display_name || me.username
  } catch (e) {
    authErr(e)
  }
  try {
    await conv.loadConversations()
  } catch (e) {
    authErr(e)
  }
})

// 切换会话 → 重连实时通道
watch(
  () => conv.currentId,
  (id) => {
    if (id) {
      chat.connect(id)
      refreshAttachments()
    } else {
      chat.disconnect()
      attachments.value = []
    }
  }
)

// 一轮结束：刷新历史（含工具事件与结果消息）
async function onRoundDone(finished) {
  if (finished.error) ElMessage.error(finished.error)
  try {
    if (conv.currentId) await conv.select(conv.currentId)
  } catch (e) {
    authErr(e)
  }
}

async function refreshAttachments() {
  if (!conv.currentId) return
  try {
    const data = await listAttachments(conv.currentId)
    attachments.value = data.attachments
  } catch (e) {
    /* 静默 */
  }
}

async function handleSelect(id) {
  try {
    await conv.select(id)
  } catch (e) {
    authErr(e)
  }
}

async function handleCreate() {
  try {
    await conv.create()
    ElMessage.success('会话已创建')
  } catch (e) {
    authErr(e)
  }
}

function openRename(c) {
  renameTarget.value = c
  renameTitle.value = c.title
  renameVisible.value = true
}

async function doRename() {
  if (!renameTitle.value.trim()) return ElMessage.warning('名称不能为空')
  try {
    await conv.rename(renameTarget.value.conversation_id, renameTitle.value.trim())
    renameVisible.value = false
  } catch (e) {
    authErr(e)
  }
}

async function handleDelete(c) {
  try {
    await ElMessageBox.confirm(`删除会话「${c.title}」？其消息、附件、分析结果将一并删除。`, '删除会话', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }
  try {
    await conv.remove([c.conversation_id])
    if (!conv.currentId) attachments.value = []
    ElMessage.success('已删除')
  } catch (e) {
    authErr(e)
  }
}

function handleSend() {
  const content = draft.value.trim()
  if (!content) return
  if (chat.taskState) return ElMessage.warning('当前会话已有分析任务在运行')
  if (!chat.send(content)) return ElMessage.error('实时通道未连接，请稍候')
  // 乐观插入用户消息；一轮结束后由 onRoundDone 用服务端历史覆盖
  conv.messages.push({ message_id: `tmp-${Date.now()}`, role: 'user', message_type: 'text', content })
  draft.value = ''
}

function handleCancel() {
  if (chat.taskState?.taskId) chat.cancel(chat.taskState.taskId)
}

async function handleUpload(ev) {
  const file = ev.target.files && ev.target.files[0]
  ev.target.value = ''
  if (!file) return
  if (!conv.currentId) return ElMessage.warning('请先选择会话')
  uploading.value = true
  uploadPct.value = 0
  try {
    await uploadAttachment(conv.currentId, file, (pct) => (uploadPct.value = pct))
    await refreshAttachments()
    ElMessage.success('上传成功')
  } catch (e) {
    authErr(e)
  } finally {
    uploading.value = false
  }
}

async function handleDeleteAttachment(att) {
  try {
    await ElMessageBox.confirm(`删除附件「${att.file_name}」？`, '删除附件', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteAttachment(att.attachment_id)
    await refreshAttachments()
  } catch (e) {
    authErr(e)
  }
}

async function handleDownload(att) {
  try {
    await downloadAttachment(att)
  } catch (e) {
    authErr(e)
  }
}

function handleLogout() {
  auth.logout()
  conv.clear()
  chat.disconnect()
  router.push('/login')
}

function statusTagType(status) {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'cancelled') return 'info'
  return 'warning'
}

function fmtSize(n) {
  if (n == null) return '-'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

function fmtTime(t) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(5, 16)
}

function fmtDay(t) {
  if (!t) return '-'
  return String(t).replace('T', ' ').slice(0, 10)
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

.conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 2px;
}

.conv-item:hover {
  background: #f5f7fa;
}

.conv-item.active {
  background: #ecf5ff;
}

.conv-title {
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 150px;
}

.conv-time {
  font-size: 12px;
  color: #c0c4cc;
}

.conv-ops {
  display: flex;
  gap: 8px;
  color: #909399;
  visibility: hidden;
}

.conv-item:hover .conv-ops {
  visibility: visible;
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

.chat-title {
  font-weight: 600;
  color: #303133;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f0f0;
}

.msg-list {
  flex: 1;
  overflow: auto;
  padding: 12px 4px;
}

.msg-row {
  display: flex;
  margin-bottom: 10px;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 70%;
  padding: 8px 12px;
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-row.user .bubble {
  background: #409eff;
  color: #fff;
}

.msg-row.assistant .bubble {
  background: #f4f4f5;
  color: #303133;
}

.streaming {
  min-height: 20px;
}

.cursor {
  animation: blink 1s steps(2) infinite;
  color: #409eff;
}

@keyframes blink {
  to {
    visibility: hidden;
  }
}

.tool-line {
  text-align: center;
  color: #909399;
  font-size: 12px;
  margin-bottom: 10px;
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

.placeholder-block.small,
.placeholder-block {
  border: 1px dashed #dcdfe6;
  border-radius: 4px;
  min-height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
  font-size: 14px;
}

.placeholder-block.small {
  min-height: 80px;
}

.empty-hint {
  border: none;
  min-height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #c0c4cc;
  font-size: 14px;
}

.task-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.task-step {
  font-size: 13px;
  color: #606266;
}

.task-tools {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}

.task-tool {
  font-size: 13px;
  color: #303133;
}

.tool-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  background: #e6a23c;
}

.tool-dot.done {
  background: #67c23a;
}

.tool-summary {
  color: #909399;
  font-size: 12px;
  margin-left: 14px;
  word-break: break-all;
}

.cancel-btn {
  width: 100%;
}

.attach-upload {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.attach-hint {
  color: #c0c4cc;
  font-size: 12px;
}
</style>
