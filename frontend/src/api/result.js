import request from './request'

function unwrap(promise) {
  return promise.then((r) => r.data.data)
}

export const getResult = (taskId) => unwrap(request.get(`/api/results/${taskId}`))

export const getLatestResult = (conversationId) =>
  unwrap(request.get(`/api/results/latest/${conversationId}`))

// 鉴权下载导出文件（axios blob → 触发浏览器保存）
export async function downloadResultFile(taskId) {
  const resp = await request.get(`/api/results/${taskId}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `analysis_${taskId}.md`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
