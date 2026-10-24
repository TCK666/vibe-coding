<template>
  <div class="page">
    <div class="page-header">
      <h2 class="page-title">运行日志</h2>
    </div>
    <p class="page-tip">运行日志数据（占位，接口接入后展示）</p>
    <el-table :data="[]" border empty-text="暂无日志数据">
      <el-table-column prop="time" label="时间" min-width="180" />
      <el-table-column prop="level" label="级别" min-width="100" />
      <el-table-column prop="type" label="类型" min-width="140" />
      <el-table-column prop="content" label="内容" min-width="300" />
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
