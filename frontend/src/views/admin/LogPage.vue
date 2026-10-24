<template>
  <div class="admin-page">
    <div class="page-header">
      <h2>运行日志</h2>
      <div class="header-btns">
        <el-input
          v-model="taskFilter"
          placeholder="按 task_id 过滤"
          style="width: 160px"
          clearable
          @keyup.enter="load"
        />
        <el-button @click="load">查询</el-button>
        <el-button @click="router.push('/workbench')">返回工作台</el-button>
      </div>
    </div>

    <el-table :data="logs" size="small" border v-loading="loading" max-height="640">
      <el-table-column label="时间" width="160">
        <template #default="{ row }">{{ fmt(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="级别" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="row.log_level === 'ERROR' ? 'danger' : row.log_level === 'WARNING' ? 'warning' : 'info'">
            {{ row.log_level }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="log_type" label="类型" width="140" />
      <el-table-column prop="task_id" label="task_id" width="90" />
      <el-table-column prop="log_content" label="内容" min-width="400" show-overflow-tooltip />
    </el-table>
    <div v-if="!logs.length && !loading" class="empty-hint">暂无日志</div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMe } from '../../api/auth'
import { listLogs } from '../../api/admin'

const router = useRouter()
const logs = ref([])
const loading = ref(false)
const taskFilter = ref('')

function authErr(e) {
  return ElMessage.error(e?.response?.data?.message || '请求失败')
}

onMounted(async () => {
  try {
    const me = await getMe()
    if (me.role !== 'admin') {
      ElMessage.warning('需要系统管理员权限')
      return router.push('/workbench')
    }
    await load()
  } catch (e) {
    authErr(e)
  }
})

async function load() {
  loading.value = true
  try {
    const params = {}
    const tid = parseInt(taskFilter.value)
    if (!Number.isNaN(tid) && taskFilter.value) params.task_id = tid
    const data = await listLogs(params)
    logs.value = data.logs
  } catch (e) {
    authErr(e)
  } finally {
    loading.value = false
  }
}

function fmt(t) {
  if (!t) return '-'
  return String(t).replace('T', ' ').slice(0, 19)
}
</script>

<style scoped>
.admin-page {
  padding: 20px;
  max-width: 1100px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.header-btns {
  display: flex;
  gap: 8px;
  align-items: center;
}

.empty-hint {
  text-align: center;
  color: #c0c4cc;
  padding: 40px 0;
}
</style>
