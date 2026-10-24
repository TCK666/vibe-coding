<template>
  <div class="admin-page">
    <div class="page-header">
      <h2>系统配置管理</h2>
      <div class="header-btns">
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" :loading="reloading" @click="handleReload">重载配置（热更新）</el-button>
        <el-button @click="router.push('/workbench')">返回工作台</el-button>
      </div>
    </div>

    <el-table :data="configs" size="small" border v-loading="loading">
      <el-table-column prop="config_group" label="分组" width="110" />
      <el-table-column prop="config_key" label="配置项" min-width="220" />
      <el-table-column prop="config_value" label="值" min-width="240" show-overflow-tooltip />
      <el-table-column label="更新时间" width="160">
        <template #default="{ row }">{{ fmt(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openEdit(row)">修改</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="editVisible" title="修改配置" width="480px">
      <div class="edit-key">{{ editKey }}</div>
      <el-input v-model="editValue" placeholder="配置值" />
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="doSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMe } from '../../api/auth'
import { listConfigs, reloadConfig, setConfig } from '../../api/admin'

const router = useRouter()
const configs = ref([])
const loading = ref(false)
const reloading = ref(false)
const editVisible = ref(false)
const editKey = ref('')
const editValue = ref('')

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
    const data = await listConfigs()
    configs.value = data.configs
  } catch (e) {
    authErr(e)
  } finally {
    loading.value = false
  }
}

function openEdit(row) {
  editKey.value = row.config_key
  editValue.value = row.config_value || ''
  editVisible.value = true
}

async function doSave() {
  try {
    await setConfig(editKey.value, editValue.value)
    editVisible.value = false
    ElMessage.success('已保存并即时生效')
    await load()
  } catch (e) {
    authErr(e)
  }
}

async function handleReload() {
  reloading.value = true
  try {
    const data = await reloadConfig()
    ElMessage.success(data.message || '已重载')
    await load()
  } catch (e) {
    authErr(e)
  } finally {
    reloading.value = false
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
}

.edit-key {
  font-family: monospace;
  color: #909399;
  margin-bottom: 8px;
}
</style>
