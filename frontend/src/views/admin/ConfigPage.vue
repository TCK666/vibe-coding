<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">系统配置</h2>
      <el-button type="primary" disabled>重载配置</el-button>
    </div>
    <p class="page-tip">配置项数据（占位，接口接入后展示）</p>
    <el-table :data="[]" border empty-text="暂无配置数据">
      <el-table-column prop="config_key" label="config_key" min-width="180" />
      <el-table-column prop="config_value" label="config_value" min-width="200" />
      <el-table-column prop="config_group" label="config_group" min-width="140" />
      <el-table-column prop="updated_at" label="updated_at" min-width="180" />
    </el-table>
  </div>
</template>

<script setup>
</script>

<style scoped>
.page {
  padding: 24px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.page-tip {
  margin: 0 0 16px;
  font-size: 13px;
  color: #909399;
}
</style>
